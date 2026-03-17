"""
RabbitMQ 连接管理器
职责：连接池管理、通道管理、重连机制
"""
import os
import aio_pika
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class RabbitMQConnectionManager:
    """RabbitMQ 连接管理器（单例模式）"""

    def __init__(self):
        self._connection: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.RobustChannel] = None
        self._url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        self._lock = asyncio.Lock()
        self._connected = False

    def set_url(self, url: str):
        """设置 RabbitMQ 连接 URL"""
        self._url = url

    async def connect(self):
        """建立 RabbitMQ 连接"""
        if self._connected:
            logger.debug("RabbitMQ 已连接")
            return

        async with self._lock:
            if self._connected:
                return

            try:
                logger.info(f"正在连接 RabbitMQ: {self._url}")
                self._connection = await aio_pika.connect_robust(
                    self._url,
                    reconnect_interval=5,
                    connect_timeout=30
                )
                self._channel = await self._connection.channel()

                # 设置 QoS - 限制未确认消息数
                await self._channel.set_qos(prefetch_count=10)

                self._connected = True
                logger.info("RabbitMQ 连接已建立")

            except Exception as e:
                logger.error(f"RabbitMQ 连接失败: {e}", exc_info=True)
                raise

    async def disconnect(self):
        """关闭 RabbitMQ 连接"""
        async with self._lock:
            if not self._connected:
                return

            self._connected = False

            if self._channel:
                try:
                    await self._channel.close()
                except Exception:
                    pass
                self._channel = None

            if self._connection:
                try:
                    await self._connection.close()
                except Exception:
                    pass
                self._connection = None

            logger.info("RabbitMQ 连接已关闭")

    async def get_channel(self) -> aio_pika.RobustChannel:
        """获取通道（自动重连）"""
        if not self._connected:
            await self.connect()

        if self._channel is None or self._channel.is_closed:
            await self.connect()

        return self._channel

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected

    @asynccontextmanager
    async def channel_context(self):
        """通道上下文管理器"""
        channel = await self.get_channel()
        try:
            yield channel
        except Exception as e:
            logger.error(f"通道操作失败: {e}", exc_info=True)
            raise


# 全局单例
mq_manager = RabbitMQConnectionManager()
