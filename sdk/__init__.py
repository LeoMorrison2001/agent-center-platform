"""
智能体平台 SDK
供子智能体连接到平台的工具包
"""

from .client import AgentWorker, AgentWorkerSync
from .models import (
    MessageType,
    RegisterMessage,
    HeartbeatMessage,
    TaskResultMessage,
    RegisteredResponse,
    TaskReceivedMessage,
    ConnectionConfig
)

__version__ = "0.1.0"

__all__ = [
    "AgentWorker",
    "AgentWorkerSync",
    "MessageType",
    "RegisterMessage",
    "HeartbeatMessage",
    "TaskResultMessage",
    "RegisteredResponse",
    "TaskReceivedMessage",
    "ConnectionConfig",
]
