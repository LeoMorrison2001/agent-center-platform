"""
SQLAlchemy ORM 模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TaskStatus:
    """任务状态常量。"""
    QUEUED = "queued"
    COMPLETED = "completed"
    FAILED = "failed"


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


class TaskLogDB(Base):
    """任务执行日志数据库模型"""
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String, nullable=False, index=True)
    agent_key = Column(String, nullable=False, index=True)
    instance_id = Column(String)
    task_content = Column(Text)
    status = Column(String, default=TaskStatus.QUEUED)  # queued, completed, failed
    result = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)
