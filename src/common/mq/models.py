"""
RabbitMQ 消息模型定义
定义任务、结果、心跳等消息的数据结构
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class BaseMQMessage(BaseModel):
    """RabbitMQ 消息基类"""
    message_type: Literal["task", "result", "heartbeat"]


class TaskMessage(BaseMQMessage):
    """任务消息"""
    message_type: Literal["task"] = "task"
    task_id: str = Field(..., description="任务唯一ID")
    agent_key: str = Field(..., description="智能体服务标识")
    task_content: str = Field(..., description="任务内容")
    priority: int = Field(default=0, ge=0, le=9, description="优先级（0-9，越小越高）")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    retry_count: int = Field(default=0, ge=0, description="重试次数")
    max_retries: int = Field(default=3, ge=0, description="最大重试次数")


class ResultMessage(BaseMQMessage):
    """任务结果消息"""
    message_type: Literal["result"] = "result"
    task_id: str = Field(..., description="任务唯一ID")
    agent_key: str = Field(..., description="智能体服务标识")
    instance_id: str = Field(..., description="智能体实例ID")
    result: str = Field(..., description="执行结果")
    success: bool = Field(default=True, description="是否成功")
    started_at: str = Field(..., description="开始时间")
    completed_at: str = Field(..., description="完成时间")
    duration_ms: int = Field(..., ge=0, description="执行时长（毫秒）")


class HeartbeatMessage(BaseMQMessage):
    """心跳消息"""
    message_type: Literal["heartbeat"] = "heartbeat"
    agent_key: str = Field(..., description="智能体服务标识")
    instance_id: str = Field(..., description="智能体实例ID")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status: Literal["idle", "busy"] = Field(default="idle", description="状态")
    current_task_id: Optional[str] = Field(default=None, description="当前任务ID")
