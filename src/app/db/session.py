"""Async SQLAlchemy engine + session management.

Engine is module-level so it's reused across requests (connection pooling).
Initialized in the app's lifespan handler and disposed on shutdown.

`get_session` is a FastAPI dependency that yields a session bound to the
current request's lifecycle — committed on success, rolled back on error.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_engine(settings: Settings) -> None:
    """Create the global engine + session factory. Call once at startup."""
    global _engine, _session_factory
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,  # detect stale connections before query
    )
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def dispose_engine() -> None:
    """Close the engine and release pool. Call on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _session_factory = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield an AsyncSession scoped to one request.

    Commits if no exception was raised; rolls back otherwise. The session is
    always closed.
    """
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized — did lifespan run?")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
