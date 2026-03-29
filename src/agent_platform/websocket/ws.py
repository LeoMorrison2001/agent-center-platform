"""
Agent Platform WebSocket 端点 - 仅保留监控端点
"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agent_platform.websocket.monitor import monitor_manager

logger = logging.getLogger(__name__)

# 创建 Platform WebSocket 路由器，带 /ws/platform 前缀
platform_ws_router = APIRouter(
    prefix="/ws/platform"
)


@platform_ws_router.websocket("/monitor")
async def websocket_monitor_endpoint(websocket: WebSocket):
    """
    监控 WebSocket 连接端点

    用于前端实时接收平台状态变化事件：
    - task.created: 任务已创建
    - task.queued: 任务已入队
    - task.completed: 任务已完成
    - instance.connected: 智能体实例连接（通过 MQ 心跳）
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
