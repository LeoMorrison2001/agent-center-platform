"""
Agent Platform WebSocket 端点
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.orm import Session

from common.database import init_db, get_db, AgentServiceCRUD, TaskLogCRUD, TaskLogDB
from agent_platform.models import (
    AgentServiceCreate, AgentServiceResponse, ToolDescription,
    HeartbeatRequest, RegisterRequest, TaskToAgent, TaskResult,
    WebSocketAction
)
from common.pool import connection_pool, HEARTBEAT_TIMEOUT
from agent_platform.websocket.monitor import monitor_manager

logger = logging.getLogger(__name__)

# 创建 Platform WebSocket 路由器，带 /ws/platform 前缀
platform_ws_router = APIRouter(
    prefix="/ws/platform"
)


@platform_ws_router.websocket("/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    """
    智能体 WebSocket 连接端点

    支持的消息类型:
    - register: 智能体注册
    - heartbeat: 心跳保活
    - execute_task: 平台下发任务
    - task_result: 智能体返回结果
    """
    await websocket.accept()
    logger.info("新的 Worker WebSocket 连接已建立")

    # 记录连接信息
    agent_info = None  # (agent_key, instance_id)

    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")
            agent_key = message.get("agent_key")
            instance_id = message.get("instance_id")

            logger.debug(f"收到消息: action={action}, agent_key={agent_key}")

            # 处理不同类型的消息
            if action == WebSocketAction.REGISTER.value:
                # 注册
                agent_info = await handle_register(
                    websocket, agent_key, instance_id
                )

            elif action == WebSocketAction.HEARTBEAT.value:
                # 心跳
                await handle_heartbeat(websocket, agent_key, instance_id)

            elif action == WebSocketAction.TASK_RESULT.value:
                # 任务结果
                await handle_task_result(websocket, message)

            else:
                logger.warning(f"未知消息类型: {action}")
                await websocket.send_json({
                    "error": f"Unknown action: {action}"
                })

    except WebSocketDisconnect:
        logger.info("Worker WebSocket 连接断开")
        if agent_info:
            # 清理连接
            await cleanup_disconnected_agent(websocket)
    except Exception as e:
        logger.error(f"Worker WebSocket 错误: {e}", exc_info=True)
        await cleanup_disconnected_agent(websocket)


@platform_ws_router.websocket("/monitor")
async def websocket_monitor_endpoint(websocket: WebSocket):
    """
    监控 WebSocket 连接端点

    用于前端实时接收平台状态变化事件：
    - instance.connected: 智能体实例连接
    - instance.disconnected: 智能体实例断开
    """
    await monitor_manager.connect(websocket)

    try:
        while True:
            # 监控端点是单向推送，不需要处理客户端消息
            # 只需要保持连接活跃
            data = await websocket.receive_text()
            # 可选：处理监控客户端的请求（如心跳、状态查询等）
    except WebSocketDisconnect:
        logger.info("监控客户端断开")
        await monitor_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"监控 WebSocket 错误: {e}", exc_info=True)
        await monitor_manager.disconnect(websocket)


async def handle_register(
    websocket: WebSocket,
    agent_key: str,
    instance_id: str
) -> tuple:
    """处理智能体注册"""
    logger.info(f"Worker 注册: {agent_key}/{instance_id}")

    # 验证服务是否存在
    db: Session = next(get_db())
    service = AgentServiceCRUD.get_service_by_key(db, agent_key)
    db.close()

    if not service:
        # 服务不存在，返回错误并关闭连接
        error_msg = f"Agent key '{agent_key}' 不存在，请先在平台创建该服务"
        logger.warning(error_msg)
        await websocket.send_json({
            "action": "error",
            "message": error_msg
        })
        await websocket.close()
        raise ValueError(error_msg)

    # 注册到连接池
    instance = await connection_pool.register_instance(
        agent_key=agent_key,
        instance_id=instance_id,
        websocket=websocket
    )

    # 更新数据库中的工作实例计数
    db: Session = next(get_db())
    try:
        AgentServiceCRUD.increment_working_count(db, agent_key)

        # 获取服务的模型配置
        service = AgentServiceCRUD.get_service_by_key(db, agent_key)
    finally:
        db.close()

    # 构建模型配置（不提供默认值，如果未配置则返回 None）
    model_config = None
    if service:
        model_config = {
            "model_name": service.model_name,
            "model_provider": service.model_provider,
            "api_key": service.api_key,
            "temperature": service.temperature if service.temperature is not None else 0.0,
            "max_tokens": service.max_tokens if service.max_tokens is not None else 65536,
        }

    # 返回确认消息（包含模型配置）
    await websocket.send_json({
        "action": "registered",
        "agent_key": agent_key,
        "instance_id": instance_id,
        "heartbeat_interval": 30,
        "message": "注册成功",
        "model_settings": model_config
    })

    # 推送监控事件
    await monitor_manager.broadcast_instance_connected(agent_key, instance_id)

    return (agent_key, instance_id)


async def handle_heartbeat(
    websocket: WebSocket,
    agent_key: str,
    instance_id: str
):
    """处理心跳消息"""
    success = await connection_pool.update_heartbeat(agent_key, instance_id)

    if success:
        await websocket.send_json({
            "action": "heartbeat_ack",
            "timestamp": datetime.utcnow().isoformat()
        })
    else:
        logger.warning(f"未注册的实例发送心跳: {agent_key}/{instance_id}")
        await websocket.send_json({
            "error": "Instance not registered"
        })


async def handle_task_result(websocket: WebSocket, message: dict):
    """处理任务结果"""
    result = TaskResult(**message)
    logger.info(
        f"收到任务结果: {result.agent_key}/{result.instance_id} "
        f"- task_id={result.task_id}, success={result.success}"
    )

    # 更新任务日志
    db: Session = next(get_db())
    try:
        # 计算执行时长（精确到毫秒）
        start_time = datetime.strptime(result.start_time, "%Y-%m-%d %H:%M:%S.%f")
        end_time = datetime.strptime(result.end_time, "%Y-%m-%d %H:%M:%S.%f")
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        TaskLogCRUD.update_task_status(
            db=db,
            task_id=result.task_id,
            status="completed" if result.success else "failed",
            result=result.result,
            error_message=None if result.success else "任务执行失败",
            completed_at=end_time,
            duration_ms=duration_ms
        )

        # 推送任务完成事件
        await monitor_manager.broadcast_task_completed(result.task_id, result.agent_key, result.success)
    finally:
        db.close()

    # 发送确认
    await websocket.send_json({
        "action": "result_ack",
        "task_id": result.task_id
    })


async def cleanup_disconnected_agent(websocket: WebSocket):
    """清理断开的智能体连接"""
    result = await connection_pool.unregister_by_websocket(websocket)
    if result:
        agent_key, instance_id = result
        logger.info(f"清理断开连接: {agent_key}/{instance_id}")

        # 更新数据库中的工作实例计数
        db: Session = next(get_db())
        try:
            AgentServiceCRUD.decrement_working_count(db, agent_key)
        finally:
            db.close()

        # 推送监控事件
        await monitor_manager.broadcast_instance_disconnected(agent_key, instance_id)
