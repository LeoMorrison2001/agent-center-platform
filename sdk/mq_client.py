"""
RabbitMQ 客户端 - SDK 端
职责：消费任务队列、发送结果、发送心跳
"""
import aio_pika
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class MQClient:
    """
    RabbitMQ 客户端

    供智能体 SDK 使用，用于：
    - 连接到 RabbitMQ
    - 消费任务队列
    - 发送结果到结果队列
    - 发送心跳
    """

    def __init__(
        self,
        agent_key: str,
        mq_url: str = "amqp://guest:guest@localhost:5672/",
        heartbeat_interval: int = 30
    ):
        """
        初始化 MQ 客户端

        Args:
            agent_key: 智能体服务标识
            mq_url: RabbitMQ 连接 URL
            heartbeat_interval: 心跳间隔（秒）
        """
        self.agent_key = agent_key
        self.mq_url = mq_url
        self.instance_id = f"inst_{uuid.uuid4().hex[:12]}"
        self.heartbeat_interval = heartbeat_interval

        # 连接相关
        self._connection: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.RobustChannel] = None
        self._task_queue: Optional[aio_pika.Queue] = None
        self._result_exchange: Optional[aio_pika.Exchange] = None
        self._heartbeat_exchange: Optional[aio_pika.Exchange] = None

        # 运行状态
        self._is_running = False
        self._is_connected = False

        # 消费者标签
        self._consumer_tag: Optional[str] = None

        # 任务处理回调
        self._task_callback: Optional[Callable] = None

        # 心跳任务
        self._heartbeat_task: Optional[asyncio.Task] = None

        logger.info(
            f"MQClient 初始化: {self.agent_key}/{self.instance_id}"
        )

    async def connect(self):
        """连接到 RabbitMQ"""
        if self._is_connected:
            logger.debug("RabbitMQ 已连接")
            return

        try:
            logger.info(f"正在连接 RabbitMQ: {self.mq_url}")
            self._connection = await aio_pika.connect_robust(
                self.mq_url,
                reconnect_interval=5,
                connect_timeout=30
            )
            self._channel = await self._connection.channel()

            # 设置 QoS - 限制未确认消息数（确保公平分发）
            await self._channel.set_qos(prefetch_count=1)

            # 声明任务队列（消费者只需声明队列，不需要声明交换机）
            queue_name = f"agent.{self.agent_key}.tasks"
            self._task_queue = await self._channel.declare_queue(
                queue_name,
                durable=True
            )

            # 声明结果交换机（用于发送结果）
            self._result_exchange = await self._channel.declare_exchange(
                "agent.results.direct",
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )

            # 声明心跳交换机（用于发送心跳）
            self._heartbeat_exchange = await self._channel.declare_exchange(
                "agent.heartbeat.fanout",
                aio_pika.ExchangeType.FANOUT,
                durable=False
            )

            self._is_connected = True
            logger.info(
                f"RabbitMQ 连接已建立: {queue_name}"
            )

        except Exception as e:
            logger.error(f"RabbitMQ 连接失败: {e}", exc_info=True)
            raise

    async def disconnect(self):
        """断开 RabbitMQ 连接"""
        self._is_running = False
        self._is_connected = False

        # 停止心跳任务
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # 取消消费者
        if self._consumer_tag and self._channel:
            try:
                await self._channel.cancel(self._consumer_tag)
            except Exception:
                pass

        # 关闭连接
        if self._connection:
            try:
                await self._connection.close()
            except Exception:
                pass

        logger.info("RabbitMQ 连接已关闭")

    async def start_consuming(self, callback: Callable):
        """
        开始消费任务队列

        Args:
            callback: 任务处理回调函数
                     签名: async def callback(task_id: str, task_content: str) -> str
                     返回: 任务结果字符串
        """
        if not self._is_connected:
            await self.connect()

        self._task_callback = callback
        self._is_running = True

        # 启动心跳任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # 开始消费
        async with self._task_queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self._is_running:
                    break

                await self._process_message(message)

        logger.info("消费循环已结束")

    async def _process_message(self, message: aio_pika.IncomingMessage):
        """处理接收到的消息"""
        async with message.process():
            try:
                # 解析消息
                data = json.loads(message.body.decode())
                message_type = data.get("message_type")

                if message_type == "task":
                    await self._handle_task(data)
                else:
                    logger.warning(f"未知消息类型: {message_type}")

            except Exception as e:
                logger.error(f"处理消息时出错: {e}", exc_info=True)

    async def _handle_task(self, data: dict):
        """处理任务消息"""
        task_id = data.get("task_id")
        task_content = data.get("task_content")

        logger.info(
            f"收到任务: {task_id} - {task_content[:50]}..."
        )

        start_time = datetime.utcnow()

        try:
            # 调用任务处理回调
            if self._task_callback:
                result = await self._task_callback(task_id, task_content)
            else:
                result = "错误: 没有注册任务处理器"

            # 发送结果
            end_time = datetime.utcnow()
            await self.send_result(
                task_id=task_id,
                result=result,
                start_time=start_time,
                end_time=end_time,
                success=True
            )

            logger.info(f"任务完成: {task_id}")

        except Exception as e:
            # 任务执行失败
            end_time = datetime.utcnow()
            await self.send_result(
                task_id=task_id,
                result=f"执行失败: {str(e)}",
                start_time=start_time,
                end_time=end_time,
                success=False
            )
            logger.error(f"任务执行失败: {e}", exc_info=True)

    async def send_result(
        self,
        task_id: str,
        result: str,
        start_time: datetime,
        end_time: datetime,
        success: bool = True
    ):
        """
        发送任务结果到结果队列

        Args:
            task_id: 任务ID
            result: 执行结果
            start_time: 开始时间
            end_time: 结束时间
            success: 是否成功
        """
        if not self._is_connected:
            logger.warning("未连接到 RabbitMQ，无法发送结果")
            return

        try:
            # 计算执行时长（毫秒）
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            message_body = {
                "message_type": "result",
                "task_id": task_id,
                "agent_key": self.agent_key,
                "instance_id": self.instance_id,
                "result": result,
                "success": success,
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "duration_ms": duration_ms
            }

            message = aio_pika.Message(
                body=json.dumps(message_body, ensure_ascii=False).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )

            await self._result_exchange.publish(
                message,
                routing_key="result"
            )

            logger.debug(f"结果已发送: {task_id}")

        except Exception as e:
            logger.error(f"发送结果失败: {e}", exc_info=True)

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._is_running and self._is_connected:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if self._is_connected:
                    await self._send_heartbeat()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳发送失败: {e}")
                break

    async def _send_heartbeat(self):
        """发送心跳消息"""
        try:
            message_body = {
                "message_type": "heartbeat",
                "agent_key": self.agent_key,
                "instance_id": self.instance_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "idle"  # TODO: 根据实际状态设置
            }

            message = aio_pika.Message(
                body=json.dumps(message_body, ensure_ascii=False).encode(),
                delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT
            )

            await self._heartbeat_exchange.publish(
                message,
                routing_key=""  # fanout 交换机不需要 routing key
            )

            logger.debug("心跳已发送")

        except Exception as e:
            logger.error(f"发送心跳失败: {e}", exc_info=True)

    async def send_busy_heartbeat(self, current_task_id: str):
        """发送忙碌状态心跳"""
        if not self._is_connected:
            return

        try:
            message_body = {
                "message_type": "heartbeat",
                "agent_key": self.agent_key,
                "instance_id": self.instance_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "busy",
                "current_task_id": current_task_id
            }

            message = aio_pika.Message(
                body=json.dumps(message_body, ensure_ascii=False).encode(),
                delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT
            )

            await self._heartbeat_exchange.publish(
                message,
                routing_key=""
            )

            logger.debug(f"忙碌心跳已发送: {current_task_id}")

        except Exception as e:
            logger.error(f"发送忙碌心跳失败: {e}", exc_info=True)

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running
