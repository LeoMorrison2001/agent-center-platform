"""
LangChain Agent - 自动处理模型、工具、执行
"""

import os
import asyncio
import logging
from typing import Callable, Any

from ..client import AgentWorker
from ..models import TaskHandler

logger = logging.getLogger(__name__)


class LangChainAgent(AgentWorker):
    """
    LangChain Agent - 自动处理模型、工具、执行

    开发者只需：
    1. 用 @tool 装饰器定义工具（自动收集）
    2. 用 @agent_tool 装饰器注册处理函数
    3. 直接调用 stream(inputs) 或 invoke(inputs)
    """

    def __init__(
        self,
        agent_key: str,
        platform_url: str = "ws://localhost:3150/ws/platform/agent",
    ):
        """
        初始化 LangChain Agent

        Args:
            agent_key: 智能体服务标识
            platform_url: 平台 WebSocket 地址

        注意：
            模型配置完全由平台管理，注册时会自动下发
        """
        # 调用父类初始化
        super().__init__(agent_key, platform_url)

        # LangChain 相关属性（配置由平台下发）
        self._model = None
        self._agent_executor = None

        # LangChain 工具列表
        self._langchain_tools = []

    async def start(self):
        """启动时连接平台，等待注册成功后初始化模型"""
        # 先连接平台，_on_registered 会在注册成功后调用
        await super().start()

    async def _on_registered(self):
        """
        注册成功后初始化 Model 和 AgentExecutor

        此时已经收到平台的模型配置
        """
        # 动态导入 LangChain 依赖
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain.agents import create_agent

        # 从平台配置获取模型参数（必须由平台配置，不提供默认值）
        model_name = self._model_config.get("model_name")
        api_key = self._model_config.get("api_key")
        temperature = self._model_config.get("temperature", 0.0)

        # 验证必需的配置项
        if not model_name:
            raise ValueError(
                "模型名称 (model_name) 未配置。请在平台服务管理中配置模型名称。"
            )
        if not api_key:
            raise ValueError(
                "API Key 未配置。请在平台服务管理中配置 API Key。"
            )

        logger.info(f"使用平台模型配置: {model_name}")

        self._model = ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            temperature=temperature
        )

        # 使用已注册的 LangChain 工具创建 AgentExecutor
        if not self._langchain_tools:
            logger.warning("没有注册任何工具，Agent 将无法调用函数")

        # 创建 AgentExecutor
        self._agent_executor = create_agent(self._model, self._langchain_tools)

        # 打印启动横幅
        self._print_banner()

    def _print_banner(self):
        """打印统一的启动横幅"""
        # 显示平台配置的模型
        model_display = self._model_config.get("model_name", "N/A") if self._model_config else "N/A"

        print("=" * 60)
        print(f"🤖  {self.agent_key}")
        print("-" * 60)
        print(f"Instance ID: {self.instance_id}")
        print(f"Platform:    {self.platform_url}")
        print(f"Model:       {model_display}")
        print(f"Tools:       {len(self._langchain_tools)}")
        print("=" * 60)

    async def _on_config_update(self, new_config: dict):
        """配置更新时重新初始化模型"""
        logger.info("配置已更新，重新初始化模型...")

        # 更新配置
        self._model_config = new_config

        # 重新创建模型
        await self._reinitialize_model()

        # 打印更新后的横幅
        self._print_config_update_banner()

    async def _reinitialize_model(self):
        """重新初始化模型和 AgentExecutor"""
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain.agents import create_agent

        # 从新配置获取模型参数（必须由平台配置，不提供默认值）
        model_name = self._model_config.get("model_name")
        api_key = self._model_config.get("api_key")
        temperature = self._model_config.get("temperature", 0.0)

        # 验证必需的配置项
        if not model_name:
            raise ValueError(
                "模型名称 (model_name) 未配置。请在平台服务管理中配置模型名称。"
            )
        if not api_key:
            raise ValueError(
                "API Key 未配置。请在平台服务管理中配置 API Key。"
            )

        self._model = ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            temperature=temperature
        )

        # 重新创建 AgentExecutor（使用现有工具）
        self._agent_executor = create_agent(self._model, self._langchain_tools)

        logger.info(f"模型已重新初始化: {model_name}")

    def _print_config_update_banner(self):
        """打印配置更新横幅"""
        model_name = self._model_config.get("model_name", "N/A")
        print("\n" + "=" * 50)
        print(f"🔄  配置已更新")
        print(f"Model: {model_name}")
        print("=" * 50 + "\n")

    @property
    def tools(self):
        """返回已注册的 LangChain 工具数量"""
        return len(self._langchain_tools)

    def register_langchain_tool(self, tool_func) -> None:
        """
        注册 LangChain @tool 装饰器定义的函数

        Args:
            tool_func: 被 @langchain_core.tools.tool 装饰的函数

        Example:
            from langchain_core.tools import tool

            @tool
            def my_calculator(x: float) -> str:
                return f"结果: {x * 2}"

            worker = LangChainAgent("calculator")
            worker.register_langchain_tool(my_calculator)
        """
        self._langchain_tools.append(tool_func)
        logger.info(f"已注册工具: {tool_func.name}")

    def agent_tool(self, func: Callable) -> Callable:
        """
        注册 LangChain 任务处理函数

        与 @worker.on_task 类似，但专门用于 LangChain Agent
        """
        handler = TaskHandler(func)
        self._task_handlers.append(handler)
        return func

    async def _execute_task_handlers(self, task: str) -> str:
        """
        执行任务（覆盖父类方法，使用 LangChain Agent）
        """
        # 转换为 LangChain 格式
        inputs = {"messages": [("user", task)]}

        # 执行 Agent
        final_content = ""
        for chunk in self._agent_executor.stream(inputs, stream_mode="values"):
            latest_msg = chunk["messages"][-1]
            if latest_msg.type == "ai" and not latest_msg.tool_calls:
                final_content = latest_msg.content

        return final_content or "处理完成"

    def stream(self, inputs: dict = None):
        """
        直接调用 LangChain Agent Executor

        供外部调用，实现 worker.stream(inputs)
        """
        if inputs is None:
            raise ValueError("inputs 不能为空")
        return self._agent_executor.stream(inputs)

    def invoke(self, inputs: dict = None):
        """
        直接调用 LangChain Agent Executor（单次调用）
        """
        if inputs is None:
            raise ValueError("inputs 不能为空")
        return self._agent_executor.invoke(inputs)

    def agent_with_tools(self):
        """
        返回带工具的 Agent（用于链式调用）

        Example:
            worker.agent_with_tools().stream(inputs)
        """
        return self._agent_executor
