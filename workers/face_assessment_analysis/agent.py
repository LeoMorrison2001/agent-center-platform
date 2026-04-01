import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_community.chat_models import ChatOllama, ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import SecretStr

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sdk import AgentWorker


load_dotenv(CURRENT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


EMOTION_CONFIG = {
    "happy": {"label": "开心", "color": "#f59e0b"},
    "sad": {"label": "悲伤", "color": "#60a5fa"},
    "angry": {"label": "愤怒", "color": "#f87171"},
    "anxiety": {"label": "焦虑", "color": "#a78bfa"},
    "calm": {"label": "平静", "color": "#34d399"},
}

SECTION_TITLE = {
    "core": "核心生理心理状态分析",
    "risk": "潜在风险提示",
    "intervention": "个性化干预建议",
    "long_term": "长期健康管理建议",
}

PRECISION_LABELS = {
    "high": "高",
    "medium-high": "较高",
    "medium": "中等",
    "basic": "基础",
}


class FaceAssessmentAgent:
    def __init__(self) -> None:
        self.model_provider = os.getenv("MODEL_PROVIDER", "tongyi").lower()
        self.model_name = os.getenv("MODEL_NAME", "qwen3-max")
        self.temperature = float(os.getenv("MODEL_TEMPERATURE", "0.2"))
        self.executor = ThreadPoolExecutor(max_workers=5)

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        summary = payload.get("summaryData") or {}
        examinee_info = payload.get("examineeInfo") or {}
        assessment_info = payload.get("assessmentInfo") or {}
        record_id = assessment_info.get("recordId") or payload.get("recordId") or "unknown"

        logger.info(
            "start generating face assessment report, record_id=%s, examinee=%s, summary_keys=%s",
            record_id,
            examinee_info.get("name", ""),
            list(summary.keys()),
        )

        if not summary:
            logger.error("missing summaryData, record_id=%s", record_id)
            return {"success": False, "error": "missing summaryData"}

        emotion_spectrum = self._build_emotion_spectrum(summary)
        common_context = {
            "record_id": record_id,
            "summary": summary,
            "examinee_info": examinee_info,
            "assessment_info": assessment_info,
            "emotion_spectrum": emotion_spectrum,
        }

        logger.info("submit section tasks, record_id=%s", record_id)
        futures = {
            "profile": self.executor.submit(self._generate_profile_section, common_context),
            "core": self.executor.submit(self._generate_list_section, "core", common_context),
            "risk": self.executor.submit(self._generate_list_section, "risk", common_context),
            "intervention": self.executor.submit(self._generate_list_section, "intervention", common_context),
            "long_term": self.executor.submit(self._generate_list_section, "long_term", common_context),
        }

        profile = futures["profile"].result()
        core_analysis = futures["core"].result()
        risk_alerts = futures["risk"].result()
        intervention_advice = futures["intervention"].result()
        long_term_advice = futures["long_term"].result()
        logger.info("all sections generated, record_id=%s", record_id)

        physiological = summary.get("physiologicalSummary") or {}
        report = {
            "overallScore": summary.get("overallScore", 0),
            "healthLevel": profile.get("healthLevel", self._fallback_health_level(summary.get("overallScore", 0))),
            "healthDescription": profile.get("healthDescription", self._fallback_health_description(summary)),
            "dataPrecision": self._resolve_precision_label(summary.get("dataPrecision")),
            "deviceType": assessment_info.get("deviceType") or "固定双面屏终端",
            "vitalSigns": {
                "heartRate": {
                    "value": physiological.get("avgBpm", 0),
                    "unit": "bpm",
                    "note": "反映当前生理激活水平",
                },
                "spo2": {
                    "value": physiological.get("avgSpo2", 0),
                    "unit": "%",
                    "note": "用于观察基础循环状态",
                },
                "respiratoryRate": {
                    "value": summary.get("respiratoryRate", 0),
                    "unit": "次/分",
                    "note": "依据压力与生理信号综合估算",
                },
                "blinkRate": {
                    "value": summary.get("blinkRate", 0),
                    "unit": "次/分",
                    "note": "依据专注与情绪波动综合估算",
                },
            },
            "emotionSpectrum": emotion_spectrum,
            "dimensionInsights": self._normalize_dimension_insights(
                profile.get("dimensionInsights"),
                emotion_spectrum,
                summary,
            ),
            "regulationAdvice": profile.get("regulationAdvice", self._fallback_regulation_advice(summary)),
            "aiAnalysis": {
                "coreAnalysis": core_analysis,
                "riskAlerts": risk_alerts,
                "interventionAdvice": intervention_advice,
                "longTermAdvice": long_term_advice,
            },
            "meta": {
                "modelProvider": self.model_provider,
                "modelName": self.model_name,
            },
        }

        logger.info(
            "face assessment report generated successfully, record_id=%s, model=%s/%s",
            record_id,
            self.model_provider,
            self.model_name,
        )
        return {
            "success": True,
            "report": report,
            "meta": {
                "modelProvider": self.model_provider,
                "modelName": self.model_name,
            },
        }

    def _build_llm(self):
        if self.model_provider == "tongyi":
            return ChatTongyi(
                api_key=SecretStr(os.getenv("TONGYI_API_KEY", "")),
                model=self.model_name,
                temperature=self.temperature,
            )

        if self.model_provider == "ollama":
            return ChatOllama(
                model=self.model_name,
                base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                temperature=self.temperature,
            )

        return ChatTongyi(
            api_key=SecretStr(os.getenv("TONGYI_API_KEY", "")),
            model=self.model_name,
            temperature=self.temperature,
        )

    def _generate_profile_section(self, context: dict[str, Any]) -> dict[str, Any]:
        record_id = context["record_id"]
        summary = context["summary"]
        spectrum = context["emotion_spectrum"]
        logger.info("generate profile section, record_id=%s", record_id)
        prompt = f"""
你是一名心理健康报告专家。请根据以下数据输出 JSON，对应字段必须完整：
{{
  "healthLevel": "一句简短等级名称",
  "healthDescription": "1-2句贴合数据的说明",
  "dimensionInsights": [
    {{"key":"happy","label":"开心","value":18,"color":"#f59e0b","tag":"积极资源","detail":"..."}}
  ],
  "regulationAdvice": ["建议1","建议2","建议3","建议4","建议5"]
}}

要求：
1. 只输出 JSON
2. dimensionInsights 必须包含 happy、sad、angry、anxiety、calm 五项
3. regulationAdvice 返回 5 条
4. 内容要贴合以下数据，避免空泛

summaryData={json.dumps(summary, ensure_ascii=False)}
emotionSpectrum={json.dumps(spectrum, ensure_ascii=False)}
"""
        fallback = {
            "healthLevel": self._fallback_health_level(summary.get("overallScore", 0)),
            "healthDescription": self._fallback_health_description(summary),
            "dimensionInsights": self._fallback_dimension_insights(spectrum, summary),
            "regulationAdvice": self._fallback_regulation_advice(summary),
        }
        return self._invoke_json(prompt, fallback, record_id, "profile")

    def _generate_list_section(self, section: str, context: dict[str, Any]) -> list[str]:
        record_id = context["record_id"]
        summary = context["summary"]
        spectrum = context["emotion_spectrum"]
        logger.info("generate %s section, record_id=%s", section, record_id)
        prompt = f"""
你是一名心理健康报告专家。请基于以下数据，为“{SECTION_TITLE[section]}”生成 5 条分析或建议。

要求：
1. 只输出 JSON 数组，例如 ["...","...","...","...","..."]
2. 每条 30-80 字
3. 内容具体，贴合本次测评数据

summaryData={json.dumps(summary, ensure_ascii=False)}
emotionSpectrum={json.dumps(spectrum, ensure_ascii=False)}
"""
        fallback = self._fallback_section(section, summary, spectrum)
        return self._invoke_list(prompt, fallback, record_id, section)

    def _invoke_json(
        self,
        prompt: str,
        fallback: dict[str, Any],
        record_id: str | int,
        section: str,
    ) -> dict[str, Any]:
        try:
            llm = self._build_llm()
            response = llm.invoke(
                [
                    SystemMessage(content="你是一名严谨的心理健康报告生成助手，只输出合法 JSON。"),
                    HumanMessage(content=prompt),
                ]
            )
            content = self._strip_json_block((response.content or "").strip())
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                logger.info("llm section success, record_id=%s, section=%s", record_id, section)
                return parsed
            logger.warning("llm section returned non-dict, use fallback, record_id=%s, section=%s", record_id, section)
        except Exception as exc:
            logger.exception("llm section failed, record_id=%s, section=%s, error=%s", record_id, section, exc)
        return fallback

    def _invoke_list(
        self,
        prompt: str,
        fallback: list[str],
        record_id: str | int,
        section: str,
    ) -> list[str]:
        try:
            llm = self._build_llm()
            response = llm.invoke(
                [
                    SystemMessage(content="你是一名严谨的心理健康报告生成助手，只输出合法 JSON 数组。"),
                    HumanMessage(content=prompt),
                ]
            )
            content = self._strip_json_block((response.content or "").strip())
            parsed = json.loads(content)
            if isinstance(parsed, list) and parsed:
                logger.info("llm section success, record_id=%s, section=%s", record_id, section)
                return [str(item) for item in parsed][:5]
            logger.warning("llm list returned empty or invalid, use fallback, record_id=%s, section=%s", record_id, section)
        except Exception as exc:
            logger.exception("llm list failed, record_id=%s, section=%s, error=%s", record_id, section, exc)
        return fallback

    def _strip_json_block(self, content: str) -> str:
        if content.startswith("```"):
            lines = content.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return content

    def _build_emotion_spectrum(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        spectrum = summary.get("emotionSpectrum") or {}
        result: list[dict[str, Any]] = []
        for key, config in EMOTION_CONFIG.items():
            result.append(
                {
                    "key": key,
                    "label": config["label"],
                    "value": int(spectrum.get(key, 0) or 0),
                    "color": config["color"],
                }
            )
        return result

    def _normalize_dimension_insights(
        self,
        items: Any,
        spectrum: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> list[dict[str, Any]]:
        fallback_items = self._fallback_dimension_insights(spectrum, summary)
        fallback_map = {item["key"]: item for item in fallback_items}

        if not isinstance(items, list) or not items:
            return fallback_items

        normalized: list[dict[str, Any]] = []
        for spectrum_item in spectrum:
            key = spectrum_item["key"]
            fallback_item = fallback_map[key]
            raw_item = next(
                (
                    item
                    for item in items
                    if isinstance(item, dict) and str(item.get("key", "")).strip().lower() == key
                ),
                {},
            )
            normalized.append(
                {
                    "key": key,
                    "label": raw_item.get("label") or spectrum_item.get("label") or fallback_item["label"],
                    "value": int(raw_item.get("value") or spectrum_item.get("value") or fallback_item["value"]),
                    "color": raw_item.get("color") or spectrum_item.get("color") or fallback_item["color"],
                    "tag": raw_item.get("tag") or fallback_item["tag"],
                    "detail": raw_item.get("detail") or fallback_item["detail"],
                }
            )
        return normalized

    def _resolve_precision_label(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        return PRECISION_LABELS.get(text, str(value or "中等"))

    def _fallback_health_level(self, overall_score: int | float) -> str:
        if overall_score >= 85:
            return "心理健康度良好"
        if overall_score >= 72:
            return "心理状态整体稳定"
        if overall_score >= 60:
            return "心理状态轻度波动"
        return "建议重点关注"

    def _fallback_health_description(self, summary: dict[str, Any]) -> str:
        attention = summary.get("attentionLevel", 0)
        stress = summary.get("stressLevel", 0)
        overall = summary.get("overallScore", 0)
        if overall >= 85:
            return "当前结果显示整体情绪与专注状态较稳定，暂未见明显高压负荷迹象，可继续保持现有节律。"
        if overall >= 72:
            return f"整体状态基本稳定，但注意力 {attention}% 与压力 {stress}% 提示近期仍有一定任务负担，需要适度恢复。"
        if overall >= 60:
            return "本次数据提示存在轻度情绪波动与心理负荷，建议结合睡眠、学习压力和近期事件继续观察。"
        return "当前结果提示压力和情绪波动较明显，建议尽快结合教师或心理老师进行进一步评估。"

    def _fallback_dimension_insights(
        self,
        spectrum: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> list[dict[str, Any]]:
        stress = summary.get("stressLevel", 0)
        attention = summary.get("attentionLevel", 0)
        result: list[dict[str, Any]] = []
        for item in spectrum:
            key = item["key"]
            tag = "常规观察"
            detail = "该维度处于一般观察范围。"
            if key == "calm":
                tag = "稳定支撑" if attention >= 80 else "常规观察"
                detail = "平静维度较高说明具备一定自我稳定能力，面对刺激时仍能维持基础控制。"
            elif key == "anxiety":
                tag = "重点观察" if stress >= 30 or item["value"] >= 20 else "常规观察"
                detail = "焦虑维度升高时，通常提示对评价、速度要求或陌生环境更加敏感。"
            elif key == "happy":
                tag = "积极资源"
                detail = "积极情绪仍可见，说明愉悦体验和恢复资源并未完全缺失。"
            elif key == "sad":
                detail = "悲伤维度偏高时需留意疲惫、动力下降或压抑体验的累积。"
            elif key == "angry":
                detail = "愤怒维度偏高时更容易在高压情境下出现烦躁或急躁反应。"
            result.append({**item, "tag": tag, "detail": detail})
        return result

    def _fallback_regulation_advice(self, summary: dict[str, Any]) -> list[str]:
        stress = summary.get("stressLevel", 0)
        attention = summary.get("attentionLevel", 0)
        if stress >= 30 or attention < 75:
            return [
                "建议在测评后安排 5 到 10 分钟低刺激恢复时段，如安静坐息、缓慢呼吸或短时闭眼放松。",
                "学习或训练任务建议使用分段节律，避免长时间连续高负荷导致情绪和专注同步下滑。",
                "近期可增加轻运动、拉伸或步行等活动，帮助压力水平平稳回落。",
                "建议用具体观察替代评价式沟通，例如描述疲惫、分心或烦躁的变化，减少对抗感。",
                "若压力水平持续偏高或专注度继续下降，建议尽快安排复测并结合访谈进一步判断。",
            ]
        return [
            "当前状态整体可控，建议继续保持稳定作息与规律活动，巩固已有恢复能力。",
            "学习任务中可保留分段节律和短时休息，帮助专注优势转化为持续稳定表现。",
            "继续通过轻运动、舒缓音乐或深呼吸维持身心平衡，避免负荷累积后再集中恢复。",
            "建议记录近一周睡眠、课堂参与度和情绪波动，便于后续复测时判断趋势变化。",
            "后续若遇到明显压力事件，可优先采用先稳定情绪、再处理任务的节奏。",
        ]

    def _fallback_section(self, section: str, summary: dict[str, Any], spectrum: list[dict[str, Any]]) -> list[str]:
        overall = summary.get("overallScore", 0)
        attention = summary.get("attentionLevel", 0)
        stress = summary.get("stressLevel", 0)
        calm = next((item["value"] for item in spectrum if item["key"] == "calm"), 0)
        anxiety = next((item["value"] for item in spectrum if item["key"] == "anxiety"), 0)
        sad = next((item["value"] for item in spectrum if item["key"] == "sad"), 0)
        physiological = summary.get("physiologicalSummary") or {}
        bpm = physiological.get("avgBpm", 0)
        spo2 = physiological.get("avgSpo2", 0)

        if section == "core":
            return [
                f"综合评分为 {overall} 分，说明当前整体心理健康度处于{'较稳定' if overall >= 72 else '需要关注'}区间。",
                f"注意力水平 {attention}% 提示本次采集阶段具备{'较好' if attention >= 80 else '中等'}的持续投入能力。",
                f"压力水平 {stress}% 反映当前心理负荷{'已有一定积累' if stress >= 35 else '总体可控'}。",
                f"平静维度 {calm}% 是当前情绪底色的重要组成，说明仍保有一定自我稳定能力。",
                f"平均心率 {bpm} bpm、平均血氧 {spo2}% 可作为本次身心状态的辅助参考信号。",
            ]
        if section == "risk":
            return [
                "若近期同步出现睡眠不稳、疲惫增加或学习效率下降，建议结合本次结果尽快安排复测。",
                f"焦虑维度 {anxiety}% {'偏高，需重点关注对评价和任务压力的敏感性' if anxiety >= 20 else '暂未明显偏高，但仍需关注高压时段波动'}。",
                f"悲伤维度 {sad}% {'提示低落或动力下降的累积风险' if sad >= 18 else '暂未显示明显低落风险，但需关注连续疲劳后的回落'}。",
                f"压力水平 {stress}% {'偏高，需防范烦躁、退缩或回避行为增加' if stress >= 35 else '暂未提示显著高压，但仍要避免负荷叠加'}。",
                "单次测评不能替代长期观察，建议结合课堂表现、同伴互动和家庭反馈综合判断。",
            ]
        if section == "intervention":
            return [
                "建议采用先稳定、再沟通、后引导的支持顺序，避免在情绪紧绷时直接追问原因。",
                "可优先安排呼吸放松、短时步行或渐进式肌肉放松，帮助生理激活水平回落。",
                "学习支持上建议细化任务目标并增加即时反馈，降低长任务带来的挫败感。",
                "沟通时建议使用描述性语言反馈状态变化，减少标签化评价带来的防御反应。",
                "若后续复测仍提示压力上升或低落增强，建议转入心理老师一对一访谈。",
            ]
        return [
            "建议建立每周一次的情绪与睡眠记录，持续追踪状态变化而不是只看单次结果。",
            "将人脸测评结果与量表、教师观察和家长反馈联合使用，形成更稳定的长期画像。",
            "优先修复基础睡眠节律，固定入睡与起床时间，是改善情绪波动的重要底层条件。",
            "鼓励发展可复制的减压习惯，如步行、运动、呼吸训练或情绪书写。",
            "建议在 2 到 4 周后进行同条件复测，用趋势变化评估干预效果。",
        ]


worker = AgentWorker(
    agent_key="face_assessment_analysis",
    mq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
)

face_assessment_agent = FaceAssessmentAgent()


def unwrap_payload(task_obj: dict[str, Any]) -> dict[str, Any]:
    payload = task_obj.get("payload")
    if isinstance(payload, dict):
        return payload
    return task_obj


@worker.on_task
def handle_task(task: str) -> str:
    try:
        task_obj = json.loads(task)
    except json.JSONDecodeError as exc:
        logger.error("invalid task json: %s", exc)
        return json.dumps({"success": False, "error": f"invalid task json: {exc}"}, ensure_ascii=False)

    payload = unwrap_payload(task_obj)
    assessment_info = payload.get("assessmentInfo") or {}
    record_id = assessment_info.get("recordId") or payload.get("recordId") or "unknown"
    logger.info(
        "received task, record_id=%s, top_level_keys=%s, payload_keys=%s",
        record_id,
        list(task_obj.keys()) if isinstance(task_obj, dict) else [],
        list(payload.keys()) if isinstance(payload, dict) else [],
    )
    result = face_assessment_agent.invoke(payload)
    logger.info("return task result, record_id=%s, success=%s", record_id, result.get("success"))
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    logger.info("starting worker, agent_key=%s, model_provider=%s, model_name=%s", "face_assessment_analysis", os.getenv("MODEL_PROVIDER", "tongyi"), os.getenv("MODEL_NAME", "qwen3-max"))
    worker.run()
