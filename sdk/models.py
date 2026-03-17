"""
SDK 数据模型定义
定义智能体与平台通信时使用的数据结构
"""

from datetime import datetime
from typing import Optional, Callable, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum


class MessageType(str, Enum):
    """消息类型枚举"""
    REGISTER = "register"
    HEARTBEAT = "heartbeat"
    EXECUTE_TASK = "execute_task"
    TASK_RESULT = "task_result"
    REGISTERED = "registered"
    HEARTBEAT_ACK = "heartbeat_ack"
    RESULT_ACK = "result_ack"
    ERROR = "error"
    CONFIG_UPDATE = "config_update"  # 配置更新消息


# ==================== 发送到平台的消息 ====================

class RegisterMessage(BaseModel):
    """注册消息"""
    action: MessageType = MessageType.REGISTER
    agent_key: str
    instance_id: str


class HeartbeatMessage(BaseModel):
    """心跳消息"""
    action: MessageType = MessageType.HEARTBEAT
    agent_key: str
    instance_id: str


class TaskResultMessage(BaseModel):
    """任务结果消息"""
    action: MessageType = MessageType.TASK_RESULT
    agent_key: str
    instance_id: str
    task_id: str
    result: str
    start_time: str
    end_time: str
    success: bool = True


# ==================== 从平台接收的消息 ====================

class RegisteredResponse(BaseModel):
    """注册成功响应"""
    action: MessageType
    agent_key: str
    instance_id: str
    heartbeat_interval: int
    message: str
    model_settings: Optional[Dict[str, Any]] = Field(default=None, description="模型配置")


class ErrorResponse(BaseModel):
    """错误响应"""
    action: MessageType
    message: str


class HeartbeatAckResponse(BaseModel):
    """心跳确认响应"""
    action: MessageType
    timestamp: str


class TaskReceivedMessage(BaseModel):
    """接收到的任务消息"""
    action: MessageType
    task_id: str
    task_content: str


class ConfigUpdateMessage(BaseModel):
    """配置更新消息"""
    action: MessageType
    agent_key: str
    model_settings: Dict[str, Any]


# ==================== SDK 内部模型 ====================

class TaskContext(BaseModel):
    """任务执行上下文"""
    task_id: str
    task_content: str
    received_at: datetime


class ConnectionConfig(BaseModel):
    """连接配置"""
    agent_key: str
    platform_url: str
    heartbeat_interval: int = 30
    reconnect_interval: int = 5
    max_reconnect_attempts: int = 10


class TaskHandler:
    """任务处理器包装类"""
    def __init__(self, func: Callable[[str], str], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__

    async def handle(self, task: str) -> str:
        """处理任务"""
        # 如果是协程函数，用 await
        if hasattr(self.func, '__code__') and hasattr(self.func.__code__, 'co_flags'):
            import inspect
            if inspect.iscoroutinefunction(self.func):
                return await self.func(task)
        return self.func(task)


# ==================== 消息解析 ====================

def parse_message(data: dict) -> BaseModel:
    """解析接收到的消息"""
    action = data.get("action")

    if action == MessageType.REGISTERED.value:
        return RegisteredResponse(**data)
    elif action == MessageType.HEARTBEAT_ACK.value:
        return HeartbeatAckResponse(**data)
    elif action == MessageType.ERROR.value:
        return ErrorResponse(**data)
    elif action == MessageType.EXECUTE_TASK.value:
        return TaskReceivedMessage(**data)
    elif action == MessageType.RESULT_ACK.value:
        return BaseModel(**data)  # 简单确认，不需要详细解析
    else:
        # 未知消息类型，返回原始数据
        return BaseModel(**data)
