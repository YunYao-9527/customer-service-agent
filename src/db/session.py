"""
数据库会话管理

提供异步数据库连接和会话管理。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.config import get_settings
from src.db.models import Base


# 创建异步引擎
settings = get_settings()
engine = create_async_engine(
    settings.database.url,
    echo=settings.database.echo,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """初始化数据库（创建表）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入用）"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncSession:
    """获取数据库会话（直接调用用）"""
    return async_session_factory()
