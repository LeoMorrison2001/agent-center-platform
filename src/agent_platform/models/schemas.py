"""
数据模型定义 - 智能体服务通信契约
根据文档中定义的JSON格式创建Pydantic模型
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class AgentType(str, Enum):
    """智能体类型枚举"""
    GENERAL = "通用"
    SMART_HOME = "智能家居"
    CODE_REVIEW = "代码审查"
    PC_CONTROL = "电脑控制"
    MESSAGING = "消息发送"
    CUSTOM = "自定义"


# ==================== API 请求/响应模型 ====================

class AgentServiceCreate(BaseModel):
    """创建智能体服务的请求模型"""
    agent_key: str = Field(..., description="智能体唯一标识符")
    name: str = Field(..., description="智能体服务名称")
    type: str = Field(..., description="智能体类型")
    description: str = Field(..., description="智能体能力描述")


class AgentServiceResponse(BaseModel):
    """智能体服务响应模型"""
    id: int
    agent_key: str
    name: str
    type: str
    description: str
    created_at: datetime
    working_count: int = Field(default=0, description="当前工作实例数量")


class ToolDescription(BaseModel):
    """供星期日调用的工具描述"""
    agent_key: str
    name: str
    description: str
    type: str


# ==================== WebSocket 通信模型 ====================

class WebSocketAction(str, Enum):
    """WebSocket 消息动作类型"""
    HEARTBEAT = "heartbeat"
    EXECUTE_TASK = "execute_task"
    TASK_RESULT = "task_result"
    REGISTER = "register"


class HeartbeatRequest(BaseModel):
    """智能体心跳请求"""
    action: WebSocketAction = WebSocketAction.HEARTBEAT
    agent_key: str
    instance_id: str


class RegisterRequest(BaseModel):
    """智能体注册请求（首次连接时发送）"""
    action: WebSocketAction = WebSocketAction.REGISTER
    agent_key: str
    instance_id: str


class TaskDispatchRequest(BaseModel):
    """主AI调度任务的请求"""
    task_id: str
    agent_key: str
    task_content: str


class TaskToAgent(BaseModel):
    """平台下发给子智能体的任务"""
    action: WebSocketAction = WebSocketAction.EXECUTE_TASK
    task_id: str
    task_content: str


class TaskResult(BaseModel):
    """智能体执行任务后返回的结果"""
    action: WebSocketAction = WebSocketAction.TASK_RESULT
    agent_key: str
    instance_id: str
    task_id: str
    result: str
    start_time: str
    end_time: str
    success: bool = True


# ==================== 内部模型 ====================

class ActiveInstance(BaseModel):
    """活跃实例信息（存储在内存池中）"""
    instance_id: str
    agent_key: str
    websocket_id: int  # WebSocket 连接ID
    last_heartbeat: datetime
    connected_at: datetime


class TaskInfo(BaseModel):
    """任务信息（用于追踪任务状态）"""
    task_id: str
    agent_key: str
    instance_id: Optional[str] = None
    task_content: str
    created_at: datetime
    status: str = "pending"  # pending, dispatched, completed, failed
