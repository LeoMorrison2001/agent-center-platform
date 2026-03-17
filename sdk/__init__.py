"""
星期日智能体 SDK
供子智能体连接到平台的工具包
"""

from .client import AgentWorker, AgentWorkerSync
from .langchain import LangChainAgent
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
    "LangChainAgent",
    "MessageType",
    "RegisterMessage",
    "HeartbeatMessage",
    "TaskResultMessage",
    "RegisteredResponse",
    "TaskReceivedMessage",
    "ConnectionConfig",
]
