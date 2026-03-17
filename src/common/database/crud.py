"""
CRUD 操作类
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from .models import AgentServiceDB, TaskLogDB, SundayModelConfigDB


class AgentServiceCRUD:
    """智能体服务的 CRUD 操作类"""

    @staticmethod
    def create_service(
        db: Session,
        agent_key: str,
        name: str,
        type: str,
        description: str,
        model_name: str = None,
        model_provider: str = None,
        api_key: str = None,
        temperature: float = 0.0,
        max_tokens: int = 65536
    ) -> AgentServiceDB:
        """创建新的智能体服务"""
        db_service = AgentServiceDB(
            agent_key=agent_key,
            name=name,
            type=type,
            description=description,
            created_at=datetime.utcnow(),
            # 模型配置
            model_name=model_name,
            model_provider=model_provider,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens
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
        description: str,
        model_name: str = None,
        model_provider: str = None,
        api_key: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> Optional[AgentServiceDB]:
        """更新服务信息（不修改 agent_key）"""
        service = db.query(AgentServiceDB).filter(
            AgentServiceDB.agent_key == agent_key
        ).first()
        if service:
            service.name = name
            service.type = type
            service.description = description
            # 模型配置（如果提供了则更新）
            if model_name is not None:
                service.model_name = model_name
            if model_provider is not None:
                service.model_provider = model_provider
            if api_key is not None:
                service.api_key = api_key
            if temperature is not None:
                service.temperature = temperature
            if max_tokens is not None:
                service.max_tokens = max_tokens
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
        """增加工作实例计数"""
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
        """减少工作实例计数"""
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
            "working_count": service.working_count,
            # 模型配置（不提供默认值）
            "model_name": service.model_name,
            "model_provider": service.model_provider,
            "api_key": service.api_key,
            "temperature": service.temperature if service.temperature is not None else 0.0,
            "max_tokens": service.max_tokens if service.max_tokens is not None else 65536,
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
            status="pending",
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
            TaskLogDB.status == "completed"
        ).count()
        failed = db.query(TaskLogDB).filter(
            TaskLogDB.status == "failed"
        ).count()
        pending = db.query(TaskLogDB).filter(
            TaskLogDB.status == "pending"
        ).count()

        success_rate = (completed / total * 100) if total > 0 else 0

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
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


class SundayModelConfigCRUD:
    """Sunday 多模型配置 CRUD 操作类"""

    @staticmethod
    def get_all_configs(db: Session) -> List[SundayModelConfigDB]:
        """获取所有配置（按默认优先，然后按创建时间倒序）"""
        return db.query(SundayModelConfigDB)\
            .order_by(SundayModelConfigDB.is_default.desc(),
                     SundayModelConfigDB.created_at.desc())\
            .all()

    @staticmethod
    def get_default_config(db: Session) -> Optional[SundayModelConfigDB]:
        """获取默认配置"""
        return db.query(SundayModelConfigDB)\
            .filter(SundayModelConfigDB.is_default == True)\
            .first()

    @staticmethod
    def get_by_key(db: Session, config_key: str) -> Optional[SundayModelConfigDB]:
        """根据 config_key 获取配置"""
        return db.query(SundayModelConfigDB)\
            .filter(SundayModelConfigDB.config_key == config_key)\
            .first()

    @staticmethod
    def create_config(
        db: Session,
        name: str,
        model_name: str,
        model_provider: str,
        api_key: str,
        temperature: float = 0.0,
        max_tokens: int = 65536,
        config_key: str = None,
        is_default: bool = False
    ) -> SundayModelConfigDB:
        """创建新配置"""
        import uuid

        if config_key is None:
            config_key = f"config_{uuid.uuid4().hex[:8]}"

        # 验证 config_key 唯一性
        existing = SundayModelConfigCRUD.get_by_key(db, config_key)
        if existing:
            raise ValueError(f"config_key '{config_key}' 已存在")

        # 如果设置为默认，先清除其他默认标记
        if is_default:
            db.query(SundayModelConfigDB)\
                .filter(SundayModelConfigDB.is_default == True)\
                .update({"is_default": False})

        config = SundayModelConfigDB(
            config_key=config_key,
            name=name,
            model_name=model_name,
            model_provider=model_provider,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            is_default=is_default,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config

    @staticmethod
    def update_config(
        db: Session,
        config_key: str,
        name: str = None,
        model_name: str = None,
        model_provider: str = None,
        api_key: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> Optional[SundayModelConfigDB]:
        """更新配置"""
        config = SundayModelConfigCRUD.get_by_key(db, config_key)
        if not config:
            return None

        if name is not None:
            config.name = name
        if model_name is not None:
            config.model_name = model_name
        if model_provider is not None:
            config.model_provider = model_provider
        if api_key is not None:
            config.api_key = api_key
        if temperature is not None:
            config.temperature = temperature
        if max_tokens is not None:
            config.max_tokens = max_tokens

        config.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(config)
        return config

    @staticmethod
    def delete_config(db: Session, config_key: str) -> bool:
        """删除配置（不能删除默认配置）"""
        config = SundayModelConfigCRUD.get_by_key(db, config_key)
        if not config:
            return False

        if config.is_default:
            raise ValueError("不能删除默认配置，请先设置其他配置为默认")

        db.delete(config)
        db.commit()
        return True

    @staticmethod
    def set_default(db: Session, config_key: str) -> Optional[SundayModelConfigDB]:
        """设置默认配置（事务操作）"""
        # 先清除所有默认标记
        db.query(SundayModelConfigDB)\
            .filter(SundayModelConfigDB.is_default == True)\
            .update({"is_default": False})

        # 设置新的默认
        config = SundayModelConfigCRUD.get_by_key(db, config_key)
        if config:
            config.is_default = True
            config.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(config)

        return config

    @staticmethod
    def to_response(config: SundayModelConfigDB) -> dict:
        """转换为响应字典"""
        return {
            "config_key": config.config_key,
            "name": config.name,
            "model_name": config.model_name,
            "model_provider": config.model_provider,
            "api_key": config.api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "is_default": config.is_default,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None
        }
