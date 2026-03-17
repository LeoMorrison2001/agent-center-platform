"""RabbitMQ 消息队列模块"""
from .models import TaskMessage, ResultMessage, HeartbeatMessage

__all__ = [
    "TaskMessage",
    "ResultMessage",
    "HeartbeatMessage",
]
