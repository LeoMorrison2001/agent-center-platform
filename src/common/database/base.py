"""
数据库连接和会话管理
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 数据库配置（从环境变量读取）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./sunday_agents.db"
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False  # 设为 True 可查看 SQL 日志
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 特有配置
    echo=False  # 设为 True 可查看 SQL 日志
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 导入 Base（从 models.py）
from .models import Base


def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话（依赖注入用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    获取数据库会话（同步上下文管理器）

    用于在非依赖注入场景下获取会话

    Example:
        with get_db_session() as db:
            # 使用 db 进行数据库操作
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
