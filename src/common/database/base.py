"""
数据库连接和会话管理
"""
import os
from contextlib import contextmanager, asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

DEFAULT_DATABASE_URL = "mysql+pymysql://root:tcrj%40123456@192.168.10.212:3306/agent_platform?charset=utf8mb4"


def get_database_url() -> str:
    """获取数据库连接串。"""
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine_kwargs(database_url: str) -> dict:
    """根据数据库类型返回引擎参数。"""
    return {
        "connect_args": {"check_same_thread": False}
    } if database_url.startswith("sqlite") else {}


# 数据库配置（从环境变量读取）
DATABASE_URL = get_database_url()

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    **get_engine_kwargs(DATABASE_URL),
    echo=False  # 设为 True 可查看 SQL 日志
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 导入 Base（从 models.py）
from .models import Base


def init_db():
    """初始化数据库，创建所有表。

    仅用于开发环境兜底。生产和长期演进应优先使用 Alembic 迁移。
    """
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


@asynccontextmanager
async def get_db_session_async():
    """
    获取数据库会话（异步上下文管理器）

    用于在异步函数中获取会话

    Example:
        async with get_db_session_async() as db:
            # 使用 db 进行数据库操作
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
