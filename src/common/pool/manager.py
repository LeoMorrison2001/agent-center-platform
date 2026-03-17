"""
内存连接池 - 维护活跃的智能体实例
负责WebSocket连接管理、心跳检测和实例注册/注销
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from fastapi import WebSocket
from collections import defaultdict
import asyncio
import logging
import json

logger = logging.getLogger(__name__)


# 心跳超时时间（秒）
HEARTBEAT_TIMEOUT = 90


class ConnectedInstance:
    """连接实例的内部表示（包含WebSocket连接）"""

    def __init__(
        self,
        instance_id: str,
        agent_key: str,
        websocket: WebSocket
    ):
        self.instance_id = instance_id
        self.agent_key = agent_key
        self.websocket = websocket
        self.last_heartbeat = datetime.utcnow()
        self.connected_at = datetime.utcnow()

    def update_heartbeat(self):
        """更新心跳时间"""
        self.last_heartbeat = datetime.utcnow()


class ConnectionPool:
    """
    活跃实例连接池

    数据结构:
    - agent_key -> {instance_id -> ConnectedInstance}
    - websocket_id -> (agent_key, instance_id) 用于反向查找
    """

    def __init__(self):
        # agent_key -> {instance_id -> ConnectedInstance}
        self._instances: Dict[str, Dict[str, ConnectedInstance]] = defaultdict(dict)
        # websocket_id -> (agent_key, instance_id) 用于反向查找
        self._ws_to_instance: Dict[int, tuple] = {}
        # 锁
        self._lock = asyncio.Lock()
        # 心跳检查任务
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start_heartbeat_monitor(self):
        """启动心跳监控任务"""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_checker())
            logger.info("心跳监控任务已启动")

    async def stop_heartbeat_monitor(self):
        """停止心跳监控任务"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            logger.info("心跳监控任务已停止")

    async def _heartbeat_checker(self):
        """定期检查并清理超时的实例"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                await self._cleanup_stale_instances()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳检查出错: {e}")

    async def _cleanup_stale_instances(self):
        """清理超时的实例"""
        async with self._lock:
            now = datetime.utcnow()
            timeout_threshold = now - timedelta(seconds=HEARTBEAT_TIMEOUT)

            stale_instances = []

            for agent_key, instances in self._instances.items():
                stale_instances.extend([
                    (agent_key, instance_id, info)
                    for instance_id, info in instances.items()
                    if info.last_heartbeat < timeout_threshold
                ])

            for agent_key, instance_id, info in stale_instances:
                logger.warning(
                    f"实例超时清理: {agent_key}/{instance_id}, "
                    f"最后心跳: {info.last_heartbeat}"
                )
                await self._remove_instance(agent_key, instance_id)

    async def register_instance(
        self,
        agent_key: str,
        instance_id: str,
        websocket: WebSocket
    ) -> ConnectedInstance:
        """注册一个新的活跃实例"""
        async with self._lock:
            instance = ConnectedInstance(
                instance_id=instance_id,
                agent_key=agent_key,
                websocket=websocket
            )

            self._instances[agent_key][instance_id] = instance
            self._ws_to_instance[id(websocket)] = (agent_key, instance_id)

            logger.info(
                f"实例注册成功: {agent_key}/{instance_id}, "
                f"当前该服务活跃实例数: {len(self._instances[agent_key])}"
            )
            return instance

    async def update_heartbeat(
        self,
        agent_key: str,
        instance_id: str
    ) -> bool:
        """更新实例心跳时间"""
        async with self._lock:
            if agent_key in self._instances and instance_id in self._instances[agent_key]:
                instance = self._instances[agent_key][instance_id]
                instance.update_heartbeat()
                logger.debug(f"心跳更新: {agent_key}/{instance_id}")
                return True
            return False

    async def send_task_to_instance(
        self,
        agent_key: str,
        instance_id: str,
        task_id: str,
        task_content: str
    ) -> bool:
        """发送任务到指定实例"""
        async with self._lock:
            if agent_key in self._instances and instance_id in self._instances[agent_key]:
                instance = self._instances[agent_key][instance_id]
                try:
                    message = {
                        "action": "execute_task",
                        "task_id": task_id,
                        "task_content": task_content
                    }
                    await instance.websocket.send_json(message)
                    logger.info(
                        f"任务已发送: {task_id} -> {agent_key}/{instance_id}"
                    )
                    return True
                except Exception as e:
                    logger.error(f"发送任务失败: {e}")
                    return False
            return False

    async def unregister_by_websocket(self, websocket: WebSocket) -> Optional[tuple]:
        """根据WebSocket连接注销实例（断开时调用）"""
        async with self._lock:
            ws_id = id(websocket)
            if ws_id in self._ws_to_instance:
                agent_key, instance_id = self._ws_to_instance[ws_id]
                await self._remove_instance(agent_key, instance_id)
                return (agent_key, instance_id)
            return None

    async def _remove_instance(self, agent_key: str, instance_id: str):
        """移除实例（内部方法，需要在锁内调用）"""
        if agent_key in self._instances and instance_id in self._instances[agent_key]:
            instance = self._instances[agent_key][instance_id]
            ws_id = id(instance.websocket)
            del self._instances[agent_key][instance_id]
            if ws_id in self._ws_to_instance:
                del self._ws_to_instance[ws_id]

            # 如果该服务没有活跃实例了，也清理掉
            if not self._instances[agent_key]:
                del self._instances[agent_key]

            logger.info(
                f"实例已移除: {agent_key}/{instance_id}, "
                f"剩余该服务实例数: {self._instances.get(agent_key, {}).__len__()}"
            )

    def get_instance(self, agent_key: str, instance_id: str) -> Optional[ConnectedInstance]:
        """获取指定实例信息"""
        if agent_key in self._instances and instance_id in self._instances[agent_key]:
            return self._instances[agent_key][instance_id]
        return None

    def get_all_instances_for_service(self, agent_key: str) -> List[ConnectedInstance]:
        """获取指定服务的所有活跃实例"""
        if agent_key in self._instances:
            return list(self._instances[agent_key].values())
        return []

    def get_all_active_services(self) -> Set[str]:
        """获取所有有活跃实例的服务key"""
        return set(self._instances.keys())

    def get_total_instance_count(self) -> int:
        """获取总活跃实例数"""
        return sum(len(instances) for instances in self._instances.values())

    def get_service_instance_count(self, agent_key: str) -> int:
        """获取指定服务的活跃实例数"""
        if agent_key in self._instances:
            return len(self._instances[agent_key])
        return 0

    async def broadcast_to_service(self, agent_key: str, message: dict) -> int:
        """
        向指定服务的所有活跃实例广播消息

        Args:
            agent_key: 服务标识
            message: 要广播的消息字典

        Returns:
            成功发送的实例数量
        """
        async with self._lock:
            if agent_key not in self._instances:
                return 0

            count = 0
            failed_instances = []

            for instance_id, instance in self._instances[agent_key].items():
                try:
                    await instance.websocket.send_json(message)
                    count += 1
                    logger.debug(f"消息已发送到 {agent_key}/{instance_id}")
                except Exception as e:
                    logger.warning(f"发送消息到 {agent_key}/{instance_id} 失败: {e}")
                    failed_instances.append((agent_key, instance_id))

            # 清理发送失败的实例
            for agent_key_failed, instance_id_failed in failed_instances:
                await self._remove_instance(agent_key_failed, instance_id_failed)

            logger.info(
                f"广播消息到服务 {agent_key}: "
                f"成功 {count} 个, 失败 {len(failed_instances)} 个"
            )
            return count

    async def get_next_instance(
        self,
        agent_key: str,
        strategy: str = "round_robin"
    ) -> Optional[ConnectedInstance]:
        """获取下一个可用实例（用于负载均衡）"""
        instances = self.get_all_instances_for_service(agent_key)
        if not instances:
            return None

        # 简单的轮询实现
        # TODO: 后续可以添加更复杂的调度策略
        return instances[0]  # 目前简单返回第一个


# 全局连接池实例
connection_pool = ConnectionPool()
