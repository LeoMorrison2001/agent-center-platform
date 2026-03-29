"""
CRUD 操作类
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from .models import AgentServiceDB, TaskLogDB, TaskStatus


class AgentServiceCRUD:
    """智能体服务的 CRUD 操作类"""

    @staticmethod
    def create_service(
        db: Session,
        agent_key: str,
        name: str,
        type: str,
        description: str
    ) -> AgentServiceDB:
        """创建新的智能体服务"""
        db_service = AgentServiceDB(
            agent_key=agent_key,
            name=name,
            type=type,
            description=description,
            created_at=datetime.utcnow()
        )
        db.add(db_service)
        db.commit()
        db.refresh(db_service)
        return db_service

    @staticmethod
    def get_service_by_key(db: Session, agent_key: str) -> Optional[AgentServiceDB]:
        """根据 agent_key 获取服务"""
        return db.query(AgentServiceDB).filter(
            AgentServiceDB.agent_key == agent_key
        ).first()

    @staticmethod
    def get_all_services(db: Session) -> List[AgentServiceDB]:
        """获取所有服务"""
        return db.query(AgentServiceDB).all()

    @staticmethod
    def get_services_paginated(
        db: Session,
        skip: int = 0,
        limit: int = 10
    ) -> tuple[List[AgentServiceDB], int]:
        """获取分页服务列表，返回 (服务列表, 总数)"""
        query = db.query(AgentServiceDB)
        total = query.count()
        services = query.order_by(AgentServiceDB.created_at.desc()).offset(skip).limit(limit).all()
        return services, total

    @staticmethod
    def update_service(
        db: Session,
        agent_key: str,
        name: str,
        type: str,
        description: str
    ) -> Optional[AgentServiceDB]:
        """更新服务信息（不修改 agent_key）"""
        service = db.query(AgentServiceDB).filter(
            AgentServiceDB.agent_key == agent_key
        ).first()
        if service:
            service.name = name
            service.type = type
            service.description = description
            db.commit()
            db.refresh(service)
            return service
        return None

    @staticmethod
    def delete_service(db: Session, agent_key: str) -> bool:
        """删除服务"""
        service = db.query(AgentServiceDB).filter(
            AgentServiceDB.agent_key == agent_key
        ).first()
        if service:
            db.delete(service)
            db.commit()
            return True
        return False

    @staticmethod
    def increment_working_count(db: Session, agent_key: str) -> bool:
        """增加活跃实例计数"""
        service = db.query(AgentServiceDB).filter(
            AgentServiceDB.agent_key == agent_key
        ).first()
        if service:
            service.working_count += 1
            db.commit()
            return True
        return False

    @staticmethod
    def decrement_working_count(db: Session, agent_key: str) -> bool:
        """减少活跃实例计数"""
        service = db.query(AgentServiceDB).filter(
            AgentServiceDB.agent_key == agent_key
        ).first()
        if service and service.working_count > 0:
            service.working_count -= 1
            db.commit()
            return True
        return False

    @staticmethod
    def to_response(service: AgentServiceDB) -> dict:
        """转换为响应字典"""
        return {
            "id": service.id,
            "agent_key": service.agent_key,
            "name": service.name,
            "type": service.type,
            "description": service.description,
            "created_at": service.created_at,
            "working_count": service.working_count
        }


class TaskLogCRUD:
    """任务日志 CRUD 操作类"""

    @staticmethod
    def create_task_log(
        db: Session,
        task_id: str,
        agent_key: str,
        task_content: str,
        instance_id: Optional[str] = None
    ) -> TaskLogDB:
        """创建任务日志"""
        log = TaskLogDB(
            task_id=task_id,
            agent_key=agent_key,
            instance_id=instance_id,
            task_content=task_content,
            status=TaskStatus.QUEUED,
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def update_task_status(
        db: Session,
        task_id: str,
        status: str,
        result: Optional[str] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        instance_id: Optional[str] = None
    ) -> bool:
        """更新任务状态"""
        log = db.query(TaskLogDB).filter(
            TaskLogDB.task_id == task_id
        ).first()
        if log:
            log.status = status
            if result is not None:
                log.result = result
            if error_message is not None:
                log.error_message = error_message
            if started_at is not None:
                log.started_at = started_at
            if completed_at is not None:
                log.completed_at = completed_at
            if duration_ms is not None:
                log.duration_ms = duration_ms
            if instance_id is not None:
                log.instance_id = instance_id
            db.commit()
            return True
        return False

    @staticmethod
    def get_task_log(db: Session, task_id: str) -> Optional[TaskLogDB]:
        """获取单个任务日志"""
        return db.query(TaskLogDB).filter(
            TaskLogDB.task_id == task_id
        ).first()

    @staticmethod
    def get_all_logs(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        agent_key: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[TaskLogDB]:
        """获取任务日志列表"""
        query = db.query(TaskLogDB)

        if agent_key:
            query = query.filter(TaskLogDB.agent_key == agent_key)
        if status:
            query = query.filter(TaskLogDB.status == status)

        return query.order_by(TaskLogDB.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_logs_count(
        db: Session,
        agent_key: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """获取日志总数"""
        query = db.query(TaskLogDB)

        if agent_key:
            query = query.filter(TaskLogDB.agent_key == agent_key)
        if status:
            query = query.filter(TaskLogDB.status == status)

        return query.count()

    @staticmethod
    def get_task_stats(db: Session) -> dict:
        """获取任务统计信息"""
        total = db.query(TaskLogDB).count()
        completed = db.query(TaskLogDB).filter(
            TaskLogDB.status == TaskStatus.COMPLETED
        ).count()
        failed = db.query(TaskLogDB).filter(
            TaskLogDB.status == TaskStatus.FAILED
        ).count()
        queued = db.query(TaskLogDB).filter(
            TaskLogDB.status == TaskStatus.QUEUED
        ).count()

        success_rate = (completed / total * 100) if total > 0 else 0

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "queued": queued,
            "success_rate": round(success_rate, 2)
        }

    @staticmethod
    def to_response(log: TaskLogDB) -> dict:
        """转换为响应字典"""
        return {
            "id": log.id,
            "task_id": log.task_id,
            "agent_key": log.agent_key,
            "instance_id": log.instance_id,
            "task_content": log.task_content,
            "status": log.status,
            "result": log.result,
            "error_message": log.error_message,
            "created_at": log.created_at,
            "started_at": log.started_at,
            "completed_at": log.completed_at,
            "duration_ms": log.duration_ms
        }
