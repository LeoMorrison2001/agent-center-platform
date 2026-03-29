"""
数据模型定义 - 智能体服务通信契约
"""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


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
    working_count: int = Field(default=0, description="当前活跃实例数量")


class ToolDescription(BaseModel):
    """供星期日调用的工具描述"""
    agent_key: str
    name: str
    description: str
    type: str


class ServiceListResponse(BaseModel):
    """服务列表响应模型"""
    total: int
    services: list[AgentServiceResponse]


class AgentKeyValidationResponse(BaseModel):
    """智能体 KEY 校验响应"""
    valid: bool
    exists: bool
    message: str


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str


class PlatformStatistics(BaseModel):
    """平台统计信息"""
    total_services: int
    active_services: int
    total_instances: int
    running_tasks: int


class PlatformStatusResponse(BaseModel):
    """平台状态响应"""
    status: Literal["running"]
    timestamp: str
    statistics: PlatformStatistics
    active_services_list: list[str]


class TaskLogResponse(BaseModel):
    """任务日志响应模型"""
    id: int
    task_id: str
    agent_key: str
    instance_id: Optional[str] = None
    task_content: str
    status: Literal["queued", "completed", "failed"]
    result: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class TaskLogsResponse(BaseModel):
    """任务日志列表响应"""
    total: int
    logs: list[TaskLogResponse]


class TaskStatsResponse(BaseModel):
    """任务统计响应"""
    total: int
    completed: int
    failed: int
    queued: int
    success_rate: float


class DispatchTaskRequest(BaseModel):
    """任务分发请求"""
    agent_key: str = Field(..., description="智能体服务标识")
    task_content: str = Field(..., description="任务内容")


class DispatchTaskResponse(BaseModel):
    """任务分发响应"""
    task_id: str
    agent_key: str
    status: Literal["queued"]
    message: str


class ServiceInstance(BaseModel):
    """服务实例信息"""
    instance_id: str


class ServiceInstancesResponse(BaseModel):
    """服务实例列表响应"""
    agent_key: str
    instances: list[ServiceInstance]


class TestServiceRequest(BaseModel):
    """服务测试请求"""
    task_content: str = Field(default="测试任务", description="测试任务内容")


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
    status: str = "queued"  # queued, completed, failed
