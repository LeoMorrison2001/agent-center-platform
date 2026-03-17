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
    AgentServiceCreate, AgentServiceResponse
)
from common.mq.heartbeat_consumer import heartbeat_consumer
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
        "name": "智能体服务平台",
        "version": "0.2.0",
        "status": "running",
        "endpoints": {
            "api_docs": "/docs",
            "dispatch": "/api/platform/dispatch",
            "task_result": "/api/platform/logs/{task_id}",
            "websocket": "/ws/platform/monitor"
        }
    }


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
        description=service_data.description
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
        description=service_data.description
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent key '{agent_key}' 不存在"
        )

    logger.info(f"更新服务: {service.agent_key} - {service.name}")
    return AgentServiceCRUD.to_response(service)


@router.delete("/services/{agent_key}", tags=["Platform"])
async def delete_service(agent_key: str, db: Session = Depends(get_db)):
    """
    删除智能体服务
    """
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
    active_instances = heartbeat_consumer.get_active_instances()

    running_tasks = db.query(TaskLogDB).filter(
        TaskLogDB.status.in_(["queued", "dispatched"])
    ).count()

    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "statistics": {
            "total_services": len(all_services),
            "active_instances": len(active_instances),
            "running_tasks": running_tasks
        },
        "active_instances_list": list(active_instances)
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


# ==================== 任务调度接口 (供外部调用) ====================

@router.post("/dispatch", tags=["Platform"])
async def dispatch_task(task_request: dict, db: Session = Depends(get_db)):
    """
    任务调度接口

    发送任务到智能体服务，平台自动生成 task_id

    Body:
        agent_key: 智能体服务标识
        task_content: 任务内容

    Returns:
        task_id: 任务ID（平台生成）
        status: queued
    """
    agent_key = task_request.get("agent_key")
    task_content = task_request.get("task_content")

    if not all([agent_key, task_content]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要参数: agent_key, task_content"
        )

    # 验证服务是否存在
    service = AgentServiceCRUD.get_service_by_key(db, agent_key)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"服务 '{agent_key}' 不存在"
        )

    # 平台自动生成任务ID
    task_id = f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"

    # 创建任务日志
    TaskLogCRUD.create_task_log(
        db=db,
        task_id=task_id,
        agent_key=agent_key,
        task_content=task_content
    )

    # 推送任务创建事件
    await monitor_manager.broadcast_task_created(task_id, agent_key, task_content)

    # 发布任务到 RabbitMQ 队列
    from common.mq.task_producer import task_producer

    success = await task_producer.publish_task(
        agent_key=agent_key,
        task_id=task_id,
        task_content=task_content
    )

    if not success:
        TaskLogCRUD.update_task_status(
            db=db,
            task_id=task_id,
            status="failed",
            error_message="任务发布失败"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务发布失败"
        )

    # 更新任务状态为已入队
    TaskLogCRUD.update_task_status(
        db=db,
        task_id=task_id,
        status="queued",
        started_at=datetime.utcnow()
    )

    # 推送任务分发事件（到队列）
    await monitor_manager.broadcast_task_dispatched(task_id, agent_key, "queue")

    logger.info(f"任务已发布到队列: {task_id} -> {agent_key}")

    return {
        "task_id": task_id,
        "agent_key": agent_key,
        "status": "queued",
        "message": "任务已加入队列"
    }


@router.get("/services/{agent_key}/instances", tags=["Platform"])
async def get_service_instances(agent_key: str):
    """
    获取指定服务的所有活跃实例

    返回实例列表，包含 instance_id
    """
    instances = heartbeat_consumer.get_active_instances_by_agent(agent_key)

    return {
        "agent_key": agent_key,
        "instances": [
            {
                "instance_id": instance_id
            }
            for instance_id in instances
        ]
    }


@router.post("/services/{agent_key}/test", tags=["Platform"])
async def test_service(
    agent_key: str,
    test_request: dict,
    db: Session = Depends(get_db)
):
    """
    发送测试任务到指定服务

    Body:
        task_content: 测试任务内容（可选，默认为"测试任务"）
    """
    task_content = test_request.get("task_content", "测试任务")

    # 验证服务是否存在
    service = AgentServiceCRUD.get_service_by_key(db, agent_key)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"服务 '{agent_key}' 不存在"
        )

    # 平台自动生成测试任务ID
    task_id = f"test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"

    # 创建任务日志
    TaskLogCRUD.create_task_log(
        db=db,
        task_id=task_id,
        agent_key=agent_key,
        task_content=f"[测试] {task_content}"
    )

    # 推送任务创建事件
    await monitor_manager.broadcast_task_created(task_id, agent_key, f"[测试] {task_content}")

    # 发布任务到 RabbitMQ 队列
    from common.mq.task_producer import task_producer

    success = await task_producer.publish_task(
        agent_key=agent_key,
        task_id=task_id,
        task_content=task_content
    )

    if not success:
        TaskLogCRUD.update_task_status(
            db=db,
            task_id=task_id,
            status="failed",
            error_message="任务发布失败"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务发布失败"
        )

    # 更新任务状态为已入队
    TaskLogCRUD.update_task_status(
        db=db,
        task_id=task_id,
        status="queued",
        started_at=datetime.utcnow()
    )

    # 推送任务分发事件（到队列）
    await monitor_manager.broadcast_task_dispatched(task_id, agent_key, "queue")

    logger.info(f"测试任务已发布: {task_id} -> {agent_key}")

    return {
        "task_id": task_id,
        "agent_key": agent_key,
        "status": "queued",
        "message": "测试任务已加入队列"
    }
