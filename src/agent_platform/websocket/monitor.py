"""
监控连接管理器
负责管理所有监控客户端的 WebSocket 连接，向它们广播平台事件
"""

import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class MonitorConnectionManager:
    """监控连接管理器 - 单例模式"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._connections: List[WebSocket] = []
        logger.info("监控连接管理器初始化完成")

    async def connect(self, websocket: WebSocket):
        """新监控客户端连接"""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"新监控客户端连接，当前连接数: {len(self._connections)}")

        # 发送连接确认
        await websocket.send_json({
            "type": "monitor.connected",
            "message": "监控连接已建立"
        })

    async def disconnect(self, websocket: WebSocket):
        """监控客户端断开"""
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.info(f"监控客户端断开，当前连接数: {len(self._connections)}")

    async def broadcast(self, event: dict):
        """向所有监控客户端广播事件"""
        if not self._connections:
            return

        dead_connections = []
        for ws in self._connections:
            try:
                await ws.send_json(event)
            except Exception as e:
                logger.warning(f"发送事件到监控客户端失败: {e}")
                dead_connections.append(ws)

        # 清理失效连接
        for ws in dead_connections:
            await self.disconnect(ws)

    async def broadcast_instance_connected(self, agent_key: str, instance_id: str):
        """广播智能体实例连接事件"""
        await self.broadcast({
            "type": "instance.connected",
            "agent_key": agent_key,
            "instance_id": instance_id
        })

    async def broadcast_instance_disconnected(self, agent_key: str, instance_id: str):
        """广播智能体实例断开事件"""
        await self.broadcast({
            "type": "instance.disconnected",
            "agent_key": agent_key,
            "instance_id": instance_id
        })

    async def broadcast_task_created(self, task_id: str, agent_key: str, task_content: str):
        """广播任务创建事件"""
        await self.broadcast({
            "type": "task.created",
            "task_id": task_id,
            "agent_key": agent_key,
            "task_content": task_content
        })

    async def broadcast_task_queued(self, task_id: str, agent_key: str, delivery_target: str):
        """广播任务入队事件"""
        await self.broadcast({
            "type": "task.queued",
            "task_id": task_id,
            "agent_key": agent_key,
            "delivery_target": delivery_target
        })

    async def broadcast_task_completed(self, task_id: str, agent_key: str, success: bool):
        """广播任务完成事件"""
        await self.broadcast({
            "type": "task.completed" if success else "task.failed",
            "task_id": task_id,
            "agent_key": agent_key
        })

    def get_connection_count(self) -> int:
        """获取当前监控连接数"""
        return len(self._connections)


# 全局单例
monitor_manager = MonitorConnectionManager()
