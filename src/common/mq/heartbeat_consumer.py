"""
心跳消费者
职责：消费 RabbitMQ 心跳队列，维护智能体实例活跃状态
"""
import aio_pika
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Set, Dict

from .connection_manager import mq_manager
from .models import HeartbeatMessage

logger = logging.getLogger(__name__)


class HeartbeatConsumer:
    """心跳消费者"""

    def __init__(self, timeout_seconds: int = 90):
        """
        初始化心跳消费者

        Args:
            timeout_seconds: 心跳超时时间（秒）
        """
        self._channel: Optional[aio_pika.RobustChannel] = None
        self._queue: Optional[aio_pika.Queue] = None
        self._consumer_tag: Optional[str] = None
        self._is_running = False
        self._timeout_seconds = timeout_seconds

        # 活跃实例记录 {instance_id: (agent_key, last_heartbeat_time)}
        self._active_instances: Dict[str, tuple] = {}

        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._instance_connected_callback = None
        self._instance_disconnected_callback = None

    def set_instance_callbacks(self, connected_callback=None, disconnected_callback=None):
        """设置实例上下线回调。"""
        self._instance_connected_callback = connected_callback
        self._instance_disconnected_callback = disconnected_callback

    async def start(self):
        """启动心跳消费者"""
        if self._is_running:
            logger.warning("心跳消费者已在运行中")
            return

        try:
            self._is_running = True
            self._channel = await mq_manager.get_channel()

            # 声明心跳交换机
            exchange = await self._channel.declare_exchange(
                "agent.heartbeat.fanout",
                aio_pika.ExchangeType.FANOUT,
                durable=False
            )

            # 声明心跳队列（非持久化，设置 TTL）
            self._queue = await self._channel.declare_queue(
                "agent.heartbeat.monitor",
                durable=False,
                arguments={
                    "x-message-ttl": 60000  # 消息 TTL 60 秒
                }
            )

            # 绑定队列到交换机
            await self._queue.bind(exchange, routing_key="")

            logger.info("心跳消费者已启动")

            # 启动清理任务
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            # 开始消费
            await self._consume_loop()

        except Exception as e:
            logger.error(f"心跳消费者启动失败: {e}", exc_info=True)
            self._is_running = False
            raise

    async def stop(self):
        """停止心跳消费者"""
        self._is_running = False

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._consumer_tag and self._channel:
            try:
                await self._channel.cancel(self._consumer_tag)
            except Exception:
                pass

        logger.info("心跳消费者已停止")

    async def _consume_loop(self):
        """消费循环"""
        async with self._queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self._is_running:
                    break

                await self._process_message(message)

        logger.info("心跳消费循环已结束")

    async def _process_message(self, message: aio_pika.IncomingMessage):
        """处理心跳消息"""
        async with message.process():
            try:
                # 解析消息
                data = json.loads(message.body.decode())
                heartbeat_msg = HeartbeatMessage(**data)
                is_new_instance = heartbeat_msg.instance_id not in self._active_instances

                # 更新活跃实例记录
                self._active_instances[heartbeat_msg.instance_id] = (
                    heartbeat_msg.agent_key,
                    datetime.utcnow()
                )

                if is_new_instance and self._instance_connected_callback:
                    await self._instance_connected_callback(
                        heartbeat_msg.agent_key,
                        heartbeat_msg.instance_id
                    )

                logger.debug(
                    f"收到心跳: {heartbeat_msg.agent_key}/"
                    f"{heartbeat_msg.instance_id} - {heartbeat_msg.status}"
                )

            except Exception as e:
                logger.error(f"处理心跳消息时出错: {e}", exc_info=True)

    async def _cleanup_loop(self):
        """清理超时实例"""
        while self._is_running:
            try:
                await asyncio.sleep(30)  # 每 30 秒清理一次

                now = datetime.utcnow()
                timeout_threshold = now - timedelta(seconds=self._timeout_seconds)

                # 找出超时的实例
                timeout_instances = []
                for instance_id, (_, last_heartbeat) in self._active_instances.items():
                    if last_heartbeat < timeout_threshold:
                        timeout_instances.append(instance_id)

                # 移除超时实例
                for instance_id in timeout_instances:
                    agent_key, _ = self._active_instances.pop(instance_id)
                    logger.warning(
                        f"实例超时: {agent_key}/{instance_id}"
                    )
                    if self._instance_disconnected_callback:
                        await self._instance_disconnected_callback(agent_key, instance_id)

                if timeout_instances:
                    logger.info(f"清理了 {len(timeout_instances)} 个超时实例")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理超时实例时出错: {e}", exc_info=True)

    def get_active_instances(self) -> Set[str]:
        """获取活跃实例 ID 集合"""
        return set(self._active_instances.keys())

    def get_active_instances_by_agent(self, agent_key: str) -> Set[str]:
        """获取指定智能体的活跃实例 ID 集合"""
        return {
            instance_id
            for instance_id, (ak, _) in self._active_instances.items()
            if ak == agent_key
        }

    def get_active_service_map(self) -> Dict[str, Set[str]]:
        """获取 agent_key -> 活跃实例 ID 集合映射。"""
        service_map: Dict[str, Set[str]] = {}
        for instance_id, (agent_key, _) in self._active_instances.items():
            service_map.setdefault(agent_key, set()).add(instance_id)
        return service_map

    def is_instance_active(self, instance_id: str) -> bool:
        """检查实例是否活跃"""
        return instance_id in self._active_instances


# 全局单例
heartbeat_consumer = HeartbeatConsumer()
