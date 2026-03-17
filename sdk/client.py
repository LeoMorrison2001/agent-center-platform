"""
星期日智能体 SDK - AgentWorker 核心类
提供极简 API 让子智能体连接到平台
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Callable, List

import websockets

from .models import (
    RegisterMessage, HeartbeatMessage, TaskResultMessage,
    RegisteredResponse, TaskReceivedMessage, MessageType,
    TaskHandler, ConnectionConfig, ErrorResponse
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentWorker:
    """
    智能体工作类 - 连接到星期日平台

    使用示例:
        worker = AgentWorker(
            agent_key="smart_home_agent",
            platform_url="ws://localhost:3150/ws/platform/agent"
        )

        @worker.on_task
        def handle_task(task: str) -> str:
            return f"已完成: {task}"

        worker.start()
    """

    def __init__(
        self,
        agent_key: str,
        platform_url: str = "ws://localhost:3150/ws/platform/agent",
        heartbeat_interval: int = 30,
        reconnect_interval: int = 5,
        max_reconnect_attempts: int = 10
    ):
        """
        初始化智能体工作类

        Args:
            agent_key: 智能体服务标识（在平台注册时获得的 key）
            platform_url: 平台 WebSocket 地址
            heartbeat_interval: 心跳间隔（秒）
            reconnect_interval: 重连间隔（秒）
            max_reconnect_attempts: 最大重连尝试次数
        """
        self.agent_key = agent_key
        self.platform_url = platform_url
        self.instance_id = f"inst_{uuid.uuid4().hex[:12]}"
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts

        # WebSocket 连接
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._is_running = False
        self._is_connected = False

        # 任务处理器
        self._task_handlers: List[TaskHandler] = []

        # 异步任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None

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

        连接到平台、注册、开始心跳和消息接收
        """
        if self._is_running:
            logger.warning("AgentWorker 已在运行中")
            return

        self._is_running = True
        reconnect_count = 0

        while self._is_running and reconnect_count < self.max_reconnect_attempts:
            try:
                await self._connect_and_run()
                reconnect_count = 0  # 连接成功，重置计数
            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.ConnectionClosedError,
                    OSError) as e:
                logger.warning(f"连接断开: {e}")
                if self._is_running and reconnect_count < self.max_reconnect_attempts - 1:
                    reconnect_count += 1
                    logger.info(
                        f"将在 {self.reconnect_interval} 秒后尝试重连 "
                        f"({reconnect_count}/{self.max_reconnect_attempts})"
                    )
                    await asyncio.sleep(self.reconnect_interval)
                else:
                    logger.error("达到最大重连次数，停止尝试")
                    break
            except Exception as e:
                logger.error(f"未知错误: {e}", exc_info=True)
                break

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

        # 停止心跳任务
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 关闭 WebSocket 连接
        if self._websocket:
            await self._websocket.close()

        logger.info("AgentWorker 已停止")

    async def _connect_and_run(self):
        """连接到平台并运行"""
        logger.info(f"连接到平台: {self.platform_url}")

        # 建立 WebSocket 连接（增加超时设置）
        self._websocket = await websockets.connect(
            self.platform_url,
            close_timeout=10,
            ping_timeout=20,
            ping_interval=10
        )
        self._is_connected = True
        logger.info("WebSocket 连接已建立")

        # 发送注册消息
        await self._register()

        # 启动心跳任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # 启动消息接收循环
        await self._receive_loop()

    async def _register(self):
        """向平台注册"""
        register_msg = RegisterMessage(
            agent_key=self.agent_key,
            instance_id=self.instance_id
        )

        await self._send_json(register_msg.dict())
        logger.info(
            f"注册请求已发送: {self.agent_key}/{self.instance_id}"
        )

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._is_running and self._is_connected:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if self._is_connected:
                    heartbeat_msg = HeartbeatMessage(
                        agent_key=self.agent_key,
                        instance_id=self.instance_id
                    )
                    await self._send_json(heartbeat_msg.dict())
                    logger.debug("心跳已发送")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳发送失败: {e}")
                break

    async def _receive_loop(self):
        """消息接收循环"""
        try:
            async for message in self._websocket:
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket 连接已关闭")
            self._is_connected = False
        except Exception as e:
            logger.error(f"接收消息时出错: {e}", exc_info=True)
            self._is_connected = False

    async def _handle_message(self, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            action = data.get("action")

            logger.debug(f"收到消息: {action}")

            if action == MessageType.REGISTERED.value:
                # 注册成功
                response = RegisteredResponse(**data)
                logger.info(
                    f"注册成功! 心跳间隔: {response.heartbeat_interval}秒"
                )

                # 调用注册成功钩子
                await self._on_registered()

            elif action == MessageType.ERROR.value:
                # 注册失败
                response = ErrorResponse(**data)
                logger.error(f"注册失败: {response.message}")
                # 停止运行
                self._is_running = False
                return

            elif action == MessageType.HEARTBEAT_ACK.value:
                # 心跳确认
                logger.debug("心跳确认")

            elif action == MessageType.EXECUTE_TASK.value:
                # 收到任务
                await self._handle_task_message(data)

            elif action == MessageType.RESULT_ACK.value:
                # 结果确认
                logger.debug(f"结果已确认: {data.get('task_id')}")

            else:
                logger.warning(f"未知消息类型: {action}")

        except Exception as e:
            logger.error(f"处理消息时出错: {e}", exc_info=True)

    async def _handle_task_message(self, data: dict):
        """处理任务消息"""
        task_msg = TaskReceivedMessage(**data)

        logger.info(
            f"收到任务: {task_msg.task_id} - {task_msg.task_content}"
        )

        start_time = datetime.utcnow()

        try:
            # 调用任务处理器
            result = await self._execute_task_handlers(task_msg.task_content)

            # 发送结果
            end_time = datetime.utcnow()
            await self._send_task_result(
                task_msg.task_id,
                result,
                start_time,
                end_time,
                success=True
            )

            logger.info(
                f"任务完成: {task_msg.task_id}, 结果: {result[:50]}..."
            )

        except Exception as e:
            # 任务执行失败
            end_time = datetime.utcnow()
            await self._send_task_result(
                task_msg.task_id,
                f"执行失败: {str(e)}",
                start_time,
                end_time,
                success=False
            )
            logger.error(f"任务执行失败: {e}", exc_info=True)

    async def _on_registered(self):
        """
        注册成功后的钩子方法

        子类可以覆盖此方法，在注册成功后进行初始化
        """
        pass

    async def _execute_task_handlers(self, task_content: str) -> str:
        """执行任务处理器"""
        if not self._task_handlers:
            return "错误: 没有注册任务处理器"

        # 使用第一个处理器（后续可支持多个处理器）
        handler = self._task_handlers[0]
        result = await handler.handle(task_content)
        return str(result)

    async def _send_task_result(
        self,
        task_id: str,
        result: str,
        start_time: datetime,
        end_time: datetime,
        success: bool = True
    ):
        """发送任务结果"""
        result_msg = TaskResultMessage(
            action=MessageType.TASK_RESULT,
            agent_key=self.agent_key,
            instance_id=self.instance_id,
            task_id=task_id,
            result=result,
            start_time=start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            end_time=end_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            success=success
        )

        await self._send_json(result_msg.dict())

    async def _send_json(self, data: dict):
        """发送 JSON 消息"""
        if self._websocket and self._is_connected:
            await self._websocket.send(json.dumps(data, ensure_ascii=False))

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected

    def run(self):
        """
        启动智能体（同步入口）

        自动处理事件循环、异常和中断信号。

        Example:
            worker = AgentWorker(agent_key="smart_home_agent")

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


# ==================== 同步封装（可选）====================

class AgentWorkerSync:
    """
    同步版本的 AgentWorker（简化使用）

    Note: 内部仍使用 asyncio，但封装了事件循环管理
    """

    def __init__(self, agent_key: str, platform_url: str = "ws://localhost:3150/ws/platform/agent"):
        self._worker = AgentWorker(agent_key, platform_url)
        self._loop = None

    def on_task(self, func: Callable[[str], str]) -> Callable[[str], str]:
        """注册任务处理函数"""
        return self._worker.on_task(func)

    def start(self):
        """启动（阻塞）"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._worker.start())

    def stop(self):
        """停止"""
        if self._loop:
            self._loop.run_until_complete(self._worker.stop())
            self._loop.close()
