"""
任务生产者
职责：发布任务到 RabbitMQ 队列
"""
import aio_pika
import json
import logging
from typing import Optional
from datetime import datetime

from .connection_manager import mq_manager
from .models import TaskMessage

logger = logging.getLogger(__name__)


class TaskProducer:
    """任务生产者"""

    async def publish_task(
        self,
        agent_key: str,
        task_id: str,
        task_content: str,
        priority: int = 0
    ) -> bool:
        """
        发布任务到指定智能体的任务队列

        Args:
            agent_key: 智能体服务标识
            task_id: 任务ID
            task_content: 任务内容
            priority: 优先级（0-9，数字越小优先级越高）

        Returns:
            是否发布成功
        """
        try:
            channel = await mq_manager.get_channel()

            # 声明交换机
            exchange = await channel.declare_exchange(
                "agent.tasks.direct",
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )

            # 声明队列
            queue_name = f"agent.{agent_key}.tasks"
            queue = await channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-max-length": 10000,  # 最大队列长度
                    "x-overflow": "reject-publish"  # 满时拒绝新消息
                }
            )

            # 绑定队列到交换机
            await queue.bind(exchange, routing_key=agent_key)

            # 构造任务消息
            message_body = TaskMessage(
                task_id=task_id,
                agent_key=agent_key,
                task_content=task_content,
                priority=priority,
                created_at=datetime.utcnow().isoformat()
            )

            # 发布消息
            message = aio_pika.Message(
                body=json.dumps(message_body.dict(), ensure_ascii=False).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=priority
            )

            await exchange.publish(
                message,
                routing_key=agent_key
            )

            logger.info(f"任务已发布到队列: {task_id} -> {queue_name}")
            return True

        except Exception as e:
            logger.error(f"发布任务失败: {e}", exc_info=True)
            return False


# 全局单例
task_producer = TaskProducer()
