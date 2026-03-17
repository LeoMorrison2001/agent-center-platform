"""
智能体服务平台 - FastAPI 统一入口
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 导入共有模块
from common.database import init_db
from common.pool import connection_pool

# 导入路由
from agent_platform.app import router as platform_router
from agent_platform.ws import platform_ws_router

logger = logging.getLogger(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("=" * 50)
    logger.info("智能体服务平台启动中...")
    logger.info("=" * 50)

    # 初始化数据库
    init_db()
    logger.info("数据库初始化完成")

    # 启动心跳监控
    await connection_pool.start_heartbeat_monitor()
    logger.info("心跳监控已启动")

    yield

    # 关闭时（在 yield 之后，服务器已经停止接受新连接）
    logger.info("正在关闭平台...")
    await connection_pool.stop_heartbeat_monitor()
    logger.info("平台已关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="智能体服务平台",
        description="智能体注册、心跳管理与任务调度平台",
        version="1.0.0",
        lifespan=lifespan
    )

    # 添加 CORS 中间件（允许前端跨域访问，包括 WebSocket）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有来源
        allow_credentials=True,
        allow_methods=["*"],  # 允许所有方法
        allow_headers=["*"],  # 允许所有头部
    )

    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": "智能体服务平台",
            "version": "1.0.0",
            "status": "running"
        }

    @app.get("/api/info")
    async def info():
        return {
            "name": "智能体服务平台",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "api_docs": "/docs",
                "api_platform": "/api/platform/*",
                "ws_platform": "/ws/platform/*"
            }
        }

    # 注册所有路由
    app.include_router(platform_router)
    app.include_router(platform_ws_router)

    return app


# 创建应用实例
app = create_app()
