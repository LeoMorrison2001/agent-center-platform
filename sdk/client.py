"""
智能体 SDK - AgentWorker 核心类
提供极简 API 让子智能体连接到平台（基于 RabbitMQ）
"""

import asyncio
import logging
import uuid
from typing import Callable, List

from .mq_client import MQClient
from .models import TaskHandler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentWorker:
    """
    智能体工作类 - 连接到平台（RabbitMQ 模式）

    使用示例:
        worker = AgentWorker(
            agent_key="weather_agent",
            mq_url="amqp://guest:guest@localhost:5672/"
        )

        @worker.on_task
        def handle_task(task: str) -> str:
            return f"已完成: {task}"

        worker.start()
    """

    def __init__(
        self,
        agent_key: str,
        mq_url: str = "amqp://guest:guest@localhost:5672/",
        heartbeat_interval: int = 30
    ):
        """
        初始化智能体工作类

        Args:
            agent_key: 智能体服务标识（在平台注册时获得的 key）
            mq_url: RabbitMQ 连接 URL
            heartbeat_interval: 心跳间隔（秒）
        """
        self.agent_key = agent_key
        self.mq_url = mq_url
        self.instance_id = f"inst_{uuid.uuid4().hex[:12]}"
        self.heartbeat_interval = heartbeat_interval

        # 运行状态
        self._is_running = False
        self._is_connected = False

        # 任务处理器
        self._task_handlers: List[TaskHandler] = []

        # MQ 客户端
        self._mq_client: MQClient = None

        logger.info(
            f"AgentWorker 初始化: {self.agent_key}/{self.instance_id}"
        )

    def on_task(self, func: Callable[[str], str]) -> Callable[[str], str]:
        """
        注册任务处理函数（装饰器）

        Args:
            func: 处理任务的函数，接收任务内容字符串，返回结果字符串

        Returns:
            原函数（用于链式调用）

        Example:
            @worker.on_task
            def handle_task(task: str) -> str:
                return f"处理完成: {task}"
        """
        handler = TaskHandler(func)
        self._task_handlers.append(handler)
        logger.info(f"注册任务处理器: {handler.name}")
        return func

    @property
    def tools(self):
        """自动收集所有任务处理器（工具）"""
        return self._task_handlers

    async def start(self):
        """
        启动智能体工作类

        连接到 RabbitMQ，开始消费任务队列
        """
        if self._is_running:
            logger.warning("AgentWorker 已在运行中")
            return

        self._is_running = True

        # 创建 MQ 客户端
        self._mq_client = MQClient(
            agent_key=self.agent_key,
            mq_url=self.mq_url,
            heartbeat_interval=self.heartbeat_interval
        )

        # 连接到 RabbitMQ
        await self._mq_client.connect()
        self._is_connected = True

        logger.info(f"MQ 模式已启动: {self.agent_key}/{self.instance_id}")

        # 开始消费任务队列
        try:
            await self._mq_client.start_consuming(self._handle_mq_task)
        finally:
            await self.stop()

    async def stop(self):
        """
        停止智能体工作类

        优雅关闭：停止心跳、关闭连接、清理资源
        """
        if not self._is_running:
            return

        logger.info("正在停止 AgentWorker...")
        self._is_running = False
        self._is_connected = False

        # 关闭 MQ 连接
        if self._mq_client:
            await self._mq_client.disconnect()

        logger.info("AgentWorker 已停止")

    async def _handle_mq_task(self, task_id: str, task_content: str) -> str:
        """
        处理 MQ 任务

        Args:
            task_id: 任务ID
            task_content: 任务内容

        Returns:
            任务结果
        """
        logger.info(
            f"收到任务: {task_id} - {task_content[:50]}..."
        )

        try:
            # 调用任务处理器
            result = await self._execute_task_handlers(task_content)
            logger.info(
                f"任务完成: {task_id}, 结果: {result[:50]}..."
            )
            return result

        except Exception as e:
            error_msg = f"执行失败: {str(e)}"
            logger.error(f"任务执行失败: {e}", exc_info=True)
            return error_msg

    async def _execute_task_handlers(self, task_content: str) -> str:
        """执行任务处理器"""
        if not self._task_handlers:
            return "错误: 没有注册任务处理器"

        # 使用第一个处理器（后续可支持多个处理器）
        handler = self._task_handlers[0]
        result = await handler.handle(task_content)
        return str(result)

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected

    def run(self):
        """
        启动智能体（同步入口）

        自动处理事件循环、异常和中断信号。

        Example:
            worker = AgentWorker(agent_key="weather_agent")

            @worker.on_task
            async def handle_task(task: str) -> str:
                return f"已完成: {task}"

            worker.run()  # 阻塞运行，直到 Ctrl+C 或异常
        """
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            print("\n智能体已停止")
        except Exception as e:
            logger.error(f"发生错误: {e}", exc_info=True)
            print(f"\n发生错误: {e}")
            import traceback
            traceback.print_exc()
