"""
AI 报告解读与干预建议智能体。

基于当前仓库的 AgentWorker SDK 接入平台，接收结构化测评结果，
返回包含 interpretation 和 intervention 的 JSON 字符串。
"""

import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sdk import AgentWorker

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatOllama, ChatTongyi
from pydantic import SecretStr


load_dotenv(CURRENT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AnalysisAgent:

    def __init__(self) -> None:
        self.model_provider = os.getenv("MODEL_PROVIDER", "tongyi").lower()
        self.model_name = os.getenv("MODEL_NAME", "qwen3-max")
        self.temperature = float(os.getenv("MODEL_TEMPERATURE", "0.0"))
        self.executor = ThreadPoolExecutor(max_workers=2)

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get("examineeInfo") or not payload.get("scaleInfo") or not payload.get("dimensions"):
            return {
                "success": False,
                "interpretation": "",
                "intervention": "",
                "error": "缺少必要参数: examineeInfo, scaleInfo, dimensions",
            }

        interpretation_future = self.executor.submit(self._generate_interpretation, payload)
        intervention_future = self.executor.submit(self._generate_intervention, payload)

        interpretation = interpretation_future.result()
        intervention = intervention_future.result()
        return {
            "success": interpretation.get("success", False) and intervention.get("success", False),
            "interpretation": interpretation.get("interpretation", ""),
            "intervention": intervention.get("intervention", ""),
        }

    def _build_llm(self):
        if self.model_provider == "tongyi":
            api_key = os.getenv("TONGYI_API_KEY", "")
            return ChatTongyi(
                api_key=SecretStr(api_key),
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

    def _generate_interpretation(self, payload: dict[str, Any]) -> dict[str, Any]:
        examinee_info = payload.get("examineeInfo", {})
        scale_info = payload.get("scaleInfo", {})
        dimensions = payload.get("dimensions", {})

        system_prompt = "你是心理测评报告解读专家。请简洁、专业地分析测评结果。"
        user_prompt = f"""请解读以下心理测评报告：

【受测者】{examinee_info.get("name", "")}（{examinee_info.get("sex", "")}）
【量表】{scale_info.get("scaleName", "")}
【总分】{scale_info.get("totalScore", 0)}分

{self._format_dimensions_info(dimensions)}

请输出：
1. 测评有效性：简述测评是否可信
2. 整体评估：总分意义和整体状况（1-2句话）
3. 重点维度：列出需关注的维度及原因
4. 综合结论：总结建议方向（1-2句话）

保持简洁，每部分不超过100字。"""

        return self._invoke_llm(system_prompt, user_prompt, "interpretation")

    def _generate_intervention(self, payload: dict[str, Any]) -> dict[str, Any]:
        examinee_info = payload.get("examineeInfo", {})
        scale_info = payload.get("scaleInfo", {})
        dimensions = payload.get("dimensions", {})

        serious_issues = []
        for dim in dimensions.get("factorDimensions", []):
            level = dim.get("resultLevel", "")
            if any(keyword in level for keyword in ["重度", "严重", "显著"]):
                serious_issues.append(f"- {dim.get('dimName', '')}（{level}）")

        issues_text = "\n".join(serious_issues) if serious_issues else "无特别严重问题"
        system_prompt = "你是心理咨询师，擅长制定简洁可行的干预方案。"
        user_prompt = f"""请为以下测评结果制定干预建议：

【受测者】{examinee_info.get("name", "")}
【量表】{scale_info.get("scaleName", "")}
【严重问题】
{issues_text}

{self._format_dimensions_info(dimensions)}

请输出：
1. 优先事项：列出需优先处理的问题（3条以内）
2. 自我调节：情绪、认知、行为、生活各给1-2条具体建议
3. 社会支持：家庭、朋友、同伴支持建议
4. 专业帮助：是否需要专业帮助及具体方式
5. 后续跟进：复测时间和观察要点

保持简洁实用，每条建议不超过30字。"""

        return self._invoke_llm(system_prompt, user_prompt, "intervention")

    def _invoke_llm(self, system_prompt: str, user_prompt: str, field_name: str) -> dict[str, Any]:
        try:
            llm = self._build_llm()
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            content = (response.content or "").strip()
            return {
                "success": bool(content),
                field_name: content,
            }
        except Exception as exc:
            logger.exception("生成 %s 失败: %s", field_name, exc)
            return {
                "success": False,
                field_name: "" if field_name == "interpretation" else "干预建议生成失败，请稍后重试。",
            }

    def _format_dimensions_info(self, dimensions: dict[str, Any]) -> str:
        lines: list[str] = []

        total_dim = dimensions.get("totalScoreDimension")
        if total_dim:
            lines.append(f"【总分】{total_dim.get('score', 0)}分 - {total_dim.get('resultTitle', '')}")

        validity_dims = dimensions.get("validityDimensions", [])
        if validity_dims:
            lines.append("【效度维度】")
            for dim in validity_dims:
                lines.append(
                    f"- {dim.get('dimName', '')}: {dim.get('score', 0)}分 ({dim.get('resultLevel', '')})"
                )

        factor_dims = dimensions.get("factorDimensions", [])
        if factor_dims:
            lines.append("【因子维度】")
            for dim in factor_dims:
                lines.append(
                    f"- {dim.get('dimName', '')}: {dim.get('score', 0)}分 "
                    f"({dim.get('resultLevel', '')}) {dim.get('resultDesc', '')}".strip()
                )

        return "\n".join(lines)


worker = AgentWorker(
    agent_key="agent_analysis",
    mq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
)
analysis_agent = AnalysisAgent()


@worker.on_task
def handle_task(task: str) -> str:
    try:
        payload = json.loads(task)
    except json.JSONDecodeError as exc:
        logger.error("任务内容不是合法 JSON: %s", exc)
        return json.dumps({
            "success": False,
            "interpretation": "",
            "intervention": "",
            "error": f"任务内容不是合法 JSON: {exc}",
        }, ensure_ascii=False)

    result = analysis_agent.invoke(payload)
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    worker.run()
