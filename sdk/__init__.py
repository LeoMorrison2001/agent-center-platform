"""
智能体平台 SDK
供子智能体连接到平台的工具包（基于 RabbitMQ）
"""

from .client import AgentWorker

__version__ = "0.2.0"

__all__ = [
    "AgentWorker",
]
