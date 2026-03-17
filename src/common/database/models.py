"""
SQLAlchemy ORM 模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AgentServiceDB(Base):
    """智能体服务数据库模型"""
    __tablename__ = "agent_services"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    agent_key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    working_count = Column(Integer, default=0, nullable=False)

    # 模型配置 - 必须由用户配置
    model_name = Column(String, nullable=True)
    model_provider = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    temperature = Column(Float, default=0.0, nullable=True)
    max_tokens = Column(Integer, default=65536, nullable=True)


class TaskLogDB(Base):
    """任务执行日志数据库模型"""
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String, nullable=False, index=True)
    agent_key = Column(String, nullable=False, index=True)
    instance_id = Column(String)
    task_content = Column(Text)
    status = Column(String, default="pending")  # pending, dispatched, completed, failed
    result = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)


class SundayModelConfigDB(Base):
    """Sunday 多模型配置表"""
    __tablename__ = "sunday_model_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)  # 配置显示名称

    # 模型配置
    model_name = Column(String, nullable=False)
    model_provider = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    temperature = Column(Float, default=0.0, nullable=False)
    max_tokens = Column(Integer, default=65536, nullable=False)

    # 默认标记（只能有一个为 True）
    is_default = Column(Boolean, default=False, nullable=False)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_sunday_model_configs_is_default', 'is_default'),
    )
