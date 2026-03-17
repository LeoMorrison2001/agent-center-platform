"""
天气智能体 Worker - 基于 AgentWorker
使用平台 SDK 连接，提供天气查询能力

数据来源: OpenMeteo (https://open-meteo.com/)
- 完全免费，无需 API Key
- 开源
"""

import sys
import os
import asyncio
import requests
from typing import Literal

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from sdk import AgentWorker
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

# ==========================================
# 模型配置 - 由智能体自己管理（从 .env 加载）
# ==========================================

MODEL_CONFIG = {
    "model_name": os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    "api_key": os.getenv("GOOGLE_API_KEY", ""),
    "temperature": float(os.getenv("MODEL_TEMPERATURE", "0.0"))
}

# ==========================================
# 城市坐标映射（中国主要城市）
# ==========================================

CITY_COORDS = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "南京": (32.0603, 118.7969),
    "成都": (30.5728, 104.0668),
    "重庆": (29.4316, 106.9123),
    "武汉": (30.5928, 114.3055),
    "西安": (34.3416, 108.9398),
    "天津": (39.3434, 117.3616),
    "苏州": (31.2989, 120.5853),
    "郑州": (34.7466, 113.6254),
    "长沙": (28.2278, 112.9388),
    "青岛": (36.0671, 120.3826),
    "大连": (38.9140, 121.6147),
    "厦门": (24.4798, 118.0894),
    "济南": (36.6512, 117.1205),
    "沈阳": (41.8057, 123.4328),
    "哈尔滨": (45.8038, 126.5340),
}

# 天气代码映射
WEATHER_CODES = {
    0: "晴",
    1: "多云",
    2: "阴",
    3: "小雨",
    45: "雾",
    48: "雾凇",
    51: "毛毛雨",
    53: "毛毛雨",
    55: "毛毛雨",
    61: "小雨",
    63: "小雨",
    65: "大雨",
    71: "小雪",
    73: "小雪",
    75: "大雪",
    77: "雪粒",
    80: "阵雨",
    81: "阵雨",
    82: "暴雨",
    85: "暴雨",
    86: "暴雨",
    95: "雷雨",
    96: "雷雨",
    99: "雷雨",
}


# ==========================================
# 天气查询工具
# ==========================================

@tool
def get_weather(city: str, detail: Literal["当前", "今天", "明天"] = "当前") -> str:
    """
    获取指定城市的天气信息

    Args:
        city: 城市名称（如：北京、上海、广州等）
        detail: 查询类型 - "当前"查询当前天气，"今天"查询今日预报，"明天"查询明日预报

    Returns:
        天气信息描述字符串

    Example:
        get_weather("北京", "当前")
        get_weather("上海", "明天")
    """
    # 查找城市坐标
    if city not in CITY_COORDS:
        # 尝试模糊匹配
        for city_name in CITY_COORDS:
            if city in city_name or city_name in city:
                city = city_name
                break
        else:
            return f"抱歉，暂不支持 '{city}' 的天气查询。支持的城市：{', '.join(list(CITY_COORDS.keys())[:10])}..."

    latitude, longitude = CITY_COORDS[city]

    try:
        if detail == "当前":
            # 获取当前天气
            url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
            response = requests.get(url, timeout=5)
            data = response.json()

            current = data.get("current_weather", {})
            temp = current.get("temperature", "N/A")
            code = current.get("weathercode", 0)
            wind = current.get("windspeed", 0)

            weather_desc = WEATHER_CODES.get(code, "未知")

            return f"{city}当前天气：{weather_desc}，温度 {temp}°C，风速 {wind} km/h"

        elif detail in ["今天", "明天"]:
            # 获取预报天气
            url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=auto"
            response = requests.get(url, timeout=5)
            data = response.json()

            daily = data.get("daily", {})
            times = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            codes = daily.get("weathercode", [])

            if detail == "今天":
                idx = 0
            else:  # 明天
                idx = 1 if len(times) > 1 else 0

            if idx < len(times):
                date = times[idx]
                max_temp = max_temps[idx] if idx < len(max_temps) else "N/A"
                min_temp = min_temps[idx] if idx < len(min_temps) else "N/A"
                code = codes[idx] if idx < len(codes) else 0
                weather_desc = WEATHER_CODES.get(code, "未知")

                return f"{city}{date}：{weather_desc}，温度 {min_temp}~{max_temp}°C"
            else:
                return f"{city}：暂无{detail}的天气预报数据"

    except requests.Timeout:
        return f"{city}天气查询超时，请稍后再试"
    except Exception as e:
        return f"{city}天气查询失败：{str(e)}"


@tool
def compare_weather(cities: str) -> str:
    """
    比较多个城市的当前天气

    Args:
        cities: 城市列表，用逗号分隔（如：北京,上海,广州）

    Returns:
        多城市天气对比信息

    Example:
        compare_weather("北京,上海,深圳")
    """
    city_list = [c.strip() for c in cities.split(",") if c.strip()]

    if len(city_list) > 5:
        return "一次最多比较5个城市"

    results = []
    for city in city_list:
        result = get_weather(city, "当前")
        results.append(f"• {result}")

    return "\n".join(results)


@tool
def list_supported_cities() -> str:
    """
    获取所有支持天气查询的城市列表

    Returns:
        支持的城市列表
    """
    cities = sorted(CITY_COORDS.keys())
    return f"支持天气查询的城市（共{len(cities)}个）：\n" + ", ".join(cities)


# ==========================================
# 创建天气智能体 Worker
# ==========================================

class WeatherAgent:
    """天气智能体 - 集成 LangChain Agent 和平台连接（MQ 模式）"""

    def __init__(self, agent_key: str = "weather"):
        self.agent_key = agent_key
        self.worker = None
        self.agent_executor = None
        self._model = None

        # LangChain 工具列表
        self._tools = [
            get_weather,
            compare_weather,
            list_supported_cities
        ]

    def _initialize_model(self):
        """初始化模型"""
        if not MODEL_CONFIG["api_key"]:
            raise ValueError(
                "请设置 GOOGLE_API_KEY 环境变量\n"
                "示例: export GOOGLE_API_KEY='your-api-key'"
            )

        self._model = ChatGoogleGenerativeAI(
            model=MODEL_CONFIG["model_name"],
            api_key=MODEL_CONFIG["api_key"],
            temperature=MODEL_CONFIG["temperature"]
        )

        # 创建 AgentExecutor
        self.agent_executor = create_agent(self._model, self._tools)

    async def handle_task(self, task: str) -> str:
        """处理任务"""
        if not self.agent_executor:
            self._initialize_model()

        # 转换为 LangChain 格式
        inputs = {"messages": [("user", task)]}

        # 执行 Agent
        final_content = ""
        for chunk in self.agent_executor.stream(inputs, stream_mode="values"):
            latest_msg = chunk["messages"][-1]
            if latest_msg.type == "ai" and not latest_msg.tool_calls:
                final_content = latest_msg.content

        return final_content or "处理完成"

    def start(self):
        """启动智能体"""
        # 创建平台连接 worker（MQ 模式）
        self.worker = AgentWorker(
            agent_key=self.agent_key,
            mq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        )

        # 注册任务处理器
        @self.worker.on_task
        async def on_task(task: str) -> str:
            return await self.handle_task(task)

        # 打印启动信息
        self._print_banner()

        # 启动
        self.worker.run()

    def _print_banner(self):
        """打印启动横幅"""
        print("=" * 50)
        print(f"🌤️  {self.agent_key} 天气智能体")
        print("-" * 50)
        print(f"Mode:     RabbitMQ")
        print(f"Model:    {MODEL_CONFIG['model_name']}")
        print(f"Tools:    {len(self._tools)}")
        print("=" * 50)


# ==========================================
# 启动 Worker
# ==========================================
if __name__ == "__main__":
    agent = WeatherAgent()
    agent.start()
