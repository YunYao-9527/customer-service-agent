"""
FastAPI 应用入口

提供 RESTful API 接口，支持多轮对话和工具调用。
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import get_settings
from src.db.session import init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    settings = get_settings()

    # 启动时初始化
    logger.info("app_starting", env=settings.env.value)

    # 初始化数据库
    await init_db()
    logger.info("database_initialized")

    # 注册内置工具
    from src.tools.builtin import (
        cancel_order,
        freeze_account,
        get_account,
        get_logistics,
        get_order,
        get_user,
        get_user_orders,
        process_refund,
        request_refund,
        unfreeze_account,
        update_logistics_address,
        approve_refund,
        verify_user_identity,
    )
    logger.info("tools_registered")

    yield

    # 关闭时清理
    logger.info("app_shutting_down")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    settings = get_settings()

    app = FastAPI(
        title="事务型智能客服 Agent",
        description="能够完成真实业务操作的智能客服系统",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(router, prefix="/api/v1")

    # 健康检查
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "0.1.0",
            "env": settings.env.value,
        }

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
