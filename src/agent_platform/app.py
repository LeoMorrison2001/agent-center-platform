"""
Agent Platform API 路由 - /api/platform
"""
import logging
from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from common.database import get_db, AgentServiceCRUD, TaskLogCRUD, TaskLogDB
from agent_platform.models import (
    AgentServiceCreate, AgentServiceResponse, ToolDescription
)
from common.pool import connection_pool
from agent_platform.websocket.monitor import monitor_manager

# 创建平台路由器，带 /api/platform 前缀
router = APIRouter(
    prefix="/api/platform"
)

logger = logging.getLogger(__name__)


@router.get("/info", tags=["Platform"])
async def root():
    """平台信息接口"""
    return {
        "name": "星期日智能体服务平台",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "api_docs": "/docs",
            "api_tools": "/api/platform/tools",
            "api_services": "/api/platform/services",
            "websocket": "/ws/platform/agent"
        }
    }


@router.get("/tools", response_model=List[ToolDescription], tags=["Platform"])
async def get_available_tools(db: Session = Depends(get_db)):
    """
    获取可用工具列表

    供主控AI (星期日) 调用，返回当前所有在线的智能体服务及其描述
    """
    services = AgentServiceCRUD.get_all_services(db)
    active_services = connection_pool.get_all_active_services()

    tools = []
    for service in services:
        if service.agent_key in active_services:
            tools.append(ToolDescription(
                agent_key=service.agent_key,
                name=service.name,
                description=service.description,
                type=service.type
            ))

    logger.info(f"返回可用工具列表: {len(tools)} 个")
    return tools


@router.get("/services", tags=["Platform"])
async def get_services(
    skip: int = 0,
    limit: int = None,
    db: Session = Depends(get_db)
):
    """
    获取智能体服务列表

    - 不传参数或 limit=None: 返回全部
    - 传 skip 和 limit: 返回分页数据
    """
    if limit is None:
        services = AgentServiceCRUD.get_all_services(db)
        return {
            "total": len(services),
            "services": [AgentServiceCRUD.to_response(s) for s in services]
        }

    services, total = AgentServiceCRUD.get_services_paginated(db, skip=skip, limit=limit)
    return {
        "total": total,
        "services": [AgentServiceCRUD.to_response(s) for s in services]
    }


@router.get("/services/validate/{agent_key}", tags=["Platform"])
async def validate_agent_key(agent_key: str, db: Session = Depends(get_db)):
    """
    校验智能体KEY是否可用

    返回是否已存在，用于前端表单实时校验
    """
    import re
    if not re.match(r'^[a-z0-9_]+$', agent_key):
        return {
            "valid": False,
            "exists": False,
            "message": "只能包含小写字母、数字和下划线"
        }

    existing = AgentServiceCRUD.get_service_by_key(db, agent_key)
    if existing:
        return {
            "valid": False,
            "exists": True,
            "message": "该智能体KEY已存在"
        }

    return {
        "valid": True,
        "exists": False,
        "message": "可用"
    }


@router.post("/services", response_model=AgentServiceResponse, tags=["Platform"])
async def create_service(
    service_data: AgentServiceCreate,
    db: Session = Depends(get_db)
):
    """
    创建新的智能体服务

    生成唯一的 agent_key，供子智能体注册时使用
    """
    existing = AgentServiceCRUD.get_service_by_key(db, service_data.agent_key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent key '{service_data.agent_key}' 已存在"
        )

    service = AgentServiceCRUD.create_service(
        db=db,
        agent_key=service_data.agent_key,
        name=service_data.name,
        type=service_data.type,
        description=service_data.description,
        model_name=service_data.model_name,
        model_provider=service_data.model_provider,
        api_key=service_data.api_key,
        temperature=service_data.temperature,
        max_tokens=service_data.max_tokens
    )

    logger.info(f"创建服务: {service.agent_key} - {service.name}")
    return AgentServiceCRUD.to_response(service)


@router.put("/services/{agent_key}", response_model=AgentServiceResponse, tags=["Platform"])
async def update_service(
    agent_key: str,
    service_data: AgentServiceCreate,
    db: Session = Depends(get_db)
):
    """
    更新智能体服务信息

    只能更新 name、type、description，不能修改 agent_key
    """
    service = AgentServiceCRUD.update_service(
        db=db,
        agent_key=agent_key,
        name=service_data.name,
        type=service_data.type,
        description=service_data.description,
        model_name=service_data.model_name,
        model_provider=service_data.model_provider,
        api_key=service_data.api_key,
        temperature=service_data.temperature,
        max_tokens=service_data.max_tokens
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent key '{agent_key}' 不存在"
        )

    logger.info(f"更新服务: {service.agent_key} - {service.name}")

    # 构建配置更新消息（不提供默认值）
    config_update = {
        "action": "config_update",
        "agent_key": agent_key,
        "model_settings": {
            "model_name": service.model_name,
            "model_provider": service.model_provider,
            "api_key": service.api_key,
            "temperature": service.temperature if service.temperature is not None else 0.0,
            "max_tokens": service.max_tokens if service.max_tokens is not None else 65536,
        }
    }

    # 向所有活跃实例推送配置更新
    count = await connection_pool.broadcast_to_service(agent_key, config_update)
    logger.info(f"配置更新已推送到 {count} 个实例")

    return AgentServiceCRUD.to_response(service)


@router.delete("/services/{agent_key}", tags=["Platform"])
async def delete_service(agent_key: str, db: Session = Depends(get_db)):
    """
    删除智能体服务

    注意：如果有活跃实例连接，建议先断开连接
    """
    active_count = connection_pool.get_service_instance_count(agent_key)
    if active_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"服务仍有 {active_count} 个活跃实例，请先断开连接"
        )

    success = AgentServiceCRUD.delete_service(db, agent_key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent key '{agent_key}' 不存在"
        )

    logger.info(f"删除服务: {agent_key}")
    return {"message": f"服务 '{agent_key}' 已删除"}


@router.get("/status", tags=["Platform"])
async def get_platform_status(db: Session = Depends(get_db)):
    """获取平台运行状态"""
    all_services = AgentServiceCRUD.get_all_services(db)
    active_services = connection_pool.get_all_active_services()

    running_tasks = db.query(TaskLogDB).filter(
        TaskLogDB.status == "dispatched"
    ).count()

    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "statistics": {
            "total_services": len(all_services),
            "active_services": len(active_services),
            "total_instances": connection_pool.get_total_instance_count(),
            "running_tasks": running_tasks
        },
        "active_services_list": list(active_services)
    }


# ==================== 任务日志 API ====================

@router.get("/logs", tags=["Platform"])
async def get_task_logs(
    skip: int = 0,
    limit: int = 50,
    agent_key: str = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """
    获取任务执行日志列表

    支持分页和筛选
    """
    logs = TaskLogCRUD.get_all_logs(db, skip=skip, limit=limit, agent_key=agent_key, status=status)
    total = TaskLogCRUD.get_logs_count(db, agent_key=agent_key, status=status)

    return {
        "total": total,
        "logs": [TaskLogCRUD.to_response(log) for log in logs]
    }


@router.get("/logs/{task_id}", tags=["Platform"])
async def get_task_log_detail(task_id: str, db: Session = Depends(get_db)):
    """获取单个任务详情"""
    log = TaskLogCRUD.get_task_log(db, task_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task log '{task_id}' 不存在"
        )
    return TaskLogCRUD.to_response(log)


@router.get("/logs/stats/summary", tags=["Platform"])
async def get_task_stats_summary(db: Session = Depends(get_db)):
    """获取任务统计摘要"""
    return TaskLogCRUD.get_task_stats(db)


# ==================== 任务调度接口 (供主控AI调用) ====================

@router.post("/dispatch", tags=["Platform"])
async def dispatch_task(task_request: dict, db: Session = Depends(get_db)):
    """
    任务调度接口

    供主控AI (星期日) 调用，将任务分发给指定的智能体服务
    """
    agent_key = task_request.get("agent_key")
    task_id = task_request.get("task_id")
    task_content = task_request.get("task_content")

    if not all([agent_key, task_id, task_content]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要参数: agent_key, task_id, task_content"
        )

    # 创建任务日志
    TaskLogCRUD.create_task_log(
        db=db,
        task_id=task_id,
        agent_key=agent_key,
        task_content=task_content
    )

    # 推送任务创建事件
    await monitor_manager.broadcast_task_created(task_id, agent_key, task_content)

    # 获取可用实例
    instance = await connection_pool.get_next_instance(agent_key)
    if not instance:
        TaskLogCRUD.update_task_status(
            db=db,
            task_id=task_id,
            status="failed",
            error_message="没有可用实例"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"服务 '{agent_key}' 没有可用实例"
        )

    # 发送任务到对应的WebSocket实例
    success = await connection_pool.send_task_to_instance(
        agent_key=agent_key,
        instance_id=instance.instance_id,
        task_id=task_id,
        task_content=task_content
    )

    if not success:
        TaskLogCRUD.update_task_status(
            db=db,
            task_id=task_id,
            status="failed",
            error_message="任务发送失败"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务发送失败"
        )

    # 更新任务状态为已分发
    TaskLogCRUD.update_task_status(
        db=db,
        task_id=task_id,
        status="dispatched",
        instance_id=instance.instance_id,
        started_at=datetime.utcnow()
    )

    # 推送任务分发事件
    await monitor_manager.broadcast_task_dispatched(task_id, agent_key, instance.instance_id)

    logger.info(
        f"任务已调度: {task_id} -> {agent_key}/{instance.instance_id}"
    )

    return {
        "task_id": task_id,
        "agent_key": agent_key,
        "instance_id": instance.instance_id,
        "status": "dispatched",
        "message": "任务已下发"
    }


@router.get("/services/{agent_key}/instances", tags=["Platform"])
async def get_service_instances(agent_key: str):
    """
    获取指定服务的所有活跃实例

    返回实例列表，包含 instance_id 和连接时间
    """
    instances = connection_pool.get_all_instances_for_service(agent_key)

    return {
        "agent_key": agent_key,
        "instances": [
            {
                "instance_id": inst.instance_id,
                "connected_at": inst.connected_at.isoformat(),
                "last_heartbeat": inst.last_heartbeat.isoformat()
            }
            for inst in instances
        ]
    }


@router.post("/services/{agent_key}/test", tags=["Platform"])
async def test_service_instance(
    agent_key: str,
    test_request: dict,
    db: Session = Depends(get_db)
):
    """
    向指定实例发送测试任务

    Body:
        instance_id: 目标实例ID
        task_content: 测试任务内容（可选，默认为"测试任务"）
    """
    instance_id = test_request.get("instance_id")
    task_content = test_request.get("task_content", "测试任务")

    if not instance_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要参数: instance_id"
        )

    # 检查实例是否存在
    instance = connection_pool.get_instance(agent_key, instance_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"实例 '{instance_id}' 不存在或已断开"
        )

    # 生成测试任务ID
    task_id = f"test_{uuid4().hex[:8]}"

    # 创建任务日志
    TaskLogCRUD.create_task_log(
        db=db,
        task_id=task_id,
        agent_key=agent_key,
        task_content=f"[测试] {task_content}"
    )

    # 推送任务创建事件
    await monitor_manager.broadcast_task_created(task_id, agent_key, f"[测试] {task_content}")

    # 发送任务到指定实例
    success = await connection_pool.send_task_to_instance(
        agent_key=agent_key,
        instance_id=instance_id,
        task_id=task_id,
        task_content=task_content
    )

    if not success:
        TaskLogCRUD.update_task_status(
            db=db,
            task_id=task_id,
            status="failed",
            error_message="任务发送失败"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务发送失败"
        )

    # 更新任务状态
    TaskLogCRUD.update_task_status(
        db=db,
        task_id=task_id,
        status="dispatched",
        instance_id=instance_id,
        started_at=datetime.utcnow()
    )

    # 推送任务分发事件
    await monitor_manager.broadcast_task_dispatched(task_id, agent_key, instance_id)

    logger.info(f"测试任务已发送: {task_id} -> {agent_key}/{instance_id}")

    return {
        "task_id": task_id,
        "agent_key": agent_key,
        "instance_id": instance_id,
        "status": "dispatched",
        "message": "测试任务已发送"
    }
