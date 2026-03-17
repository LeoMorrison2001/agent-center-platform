"""
结果消费者
职责：消费 RabbitMQ 结果队列，更新任务日志到数据库
"""
import aio_pika
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from .connection_manager import mq_manager
from .models import ResultMessage

logger = logging.getLogger(__name__)


class ResultConsumer:
    """结果消费者"""

    def __init__(self):
        """初始化结果消费者"""
        self._channel: Optional[aio_pika.RobustChannel] = None
        self._queue: Optional[aio_pika.Queue] = None
        self._consumer_tag: Optional[str] = None
        self._is_running = False

        # 结果处理回调（可选，用于推送监控事件）
        self._result_callback = None

    def set_result_callback(self, callback):
        """设置结果回调"""
        self._result_callback = callback

    async def start(self):
        """启动结果消费者"""
        if self._is_running:
            logger.warning("结果消费者已在运行中")
            return

        try:
            self._is_running = True
            self._channel = await mq_manager.get_channel()

            # 声明结果交换机
            exchange = await self._channel.declare_exchange(
                "agent.results.direct",
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )

            # 声明结果队列
            self._queue = await self._channel.declare_queue(
                "agent.results",
                durable=True
            )

            # 绑定队列到交换机
            await self._queue.bind(exchange, routing_key="result")

            logger.info("结果消费者已启动")

            # 开始消费
            await self._consume_loop()

        except Exception as e:
            logger.error(f"结果消费者启动失败: {e}", exc_info=True)
            self._is_running = False
            raise

    async def stop(self):
        """停止结果消费者"""
        self._is_running = False

        if self._consumer_tag and self._channel:
            try:
                await self._channel.cancel(self._consumer_tag)
            except Exception:
                pass

        logger.info("结果消费者已停止")

    async def _consume_loop(self):
        """消费循环"""
        async with self._queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self._is_running:
                    break

                await self._process_message(message)

        logger.info("结果消费循环已结束")

    async def _process_message(self, message: aio_pika.IncomingMessage):
        """处理结果消息"""
        async with message.process():
            try:
                # 解析消息
                data = json.loads(message.body.decode())
                result_msg = ResultMessage(**data)

                logger.debug(
                    f"收到结果: {result_msg.task_id} - "
                    f"success={result_msg.success}"
                )

                # 更新数据库中的任务日志
                await self._update_task_log(result_msg)

                # 调用结果回调（推送监控事件）
                if self._result_callback:
                    await self._result_callback(result_msg)

            except Exception as e:
                logger.error(f"处理结果消息时出错: {e}", exc_info=True)

    async def _update_task_log(self, result_msg: ResultMessage):
        """更新任务日志到数据库"""
        try:
            # 延迟导入避免循环依赖
            from common.database import TaskLogCRUD, get_db_session

            async with get_db_session() as db:
                TaskLogCRUD.update_task_result(
                    db=db,
                    task_id=result_msg.task_id,
                    instance_id=result_msg.instance_id,
                    result=result_msg.result,
                    success=result_msg.success,
                    started_at=datetime.fromisoformat(result_msg.started_at),
                    completed_at=datetime.fromisoformat(result_msg.completed_at),
                    duration_ms=result_msg.duration_ms
                )

            logger.info(f"任务日志已更新: {result_msg.task_id}")

        except Exception as e:
            logger.error(f"更新任务日志失败: {e}", exc_info=True)


# 全局单例
result_consumer = ResultConsumer()
