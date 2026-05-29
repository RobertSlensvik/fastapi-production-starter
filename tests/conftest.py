"""Pytest fixtures for the FastAPI starter.

Strategy:
- Session-scoped engine + tables (created once) for speed.
- Truncate user tables between tests for isolation.
- Each integration test uses a real PG database (DATABASE_URL).
- Redis is faked via fakeredis (no external service needed).

CI: spins up Postgres as a service container.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Force test settings before importing app
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-for-unit-tests-only-32chars+")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
    ),
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app import create_app
from app.auth.password import hash_password
from app.config import Settings, get_settings
from app.db.base import Base
from app.db.models.user import User

# ─── Settings ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


# ─── Database ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def db_engine(settings: Settings):
    """Session-scoped engine. NullPool avoids connection-reuse issues across tasks."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    """Fresh session per test. Tables truncated before each test for isolation."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    # Truncate first so prior test data doesn't leak.
    async with factory() as session:
        await session.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))
        await session.commit()

    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


# ─── App / HTTP client ──────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncIterator[AsyncClient]:
    """ASGI client. Wires the test engine + fakeredis into the app, bypasses lifespan."""
    # Patch globals so app dependencies use our test instances.
    import app.db.session as session_module

    session_module._engine = db_engine
    session_module._session_factory = async_sessionmaker(
        db_engine, expire_on_commit=False, class_=AsyncSession
    )

    try:
        import fakeredis.aioredis as fake
    except ImportError:
        pytest.skip("fakeredis not installed — pip install fakeredis")

    import app.core.redis as redis_module

    redis_module._client = fake.FakeRedis(decode_responses=True)

    # Build app with lifespan disabled — we manage resources here.
    app = create_app()
    app.router.lifespan_context = None  # type: ignore[assignment]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── User fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("correct-horse-battery-staple"),
        full_name="Regular User",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def super_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("correct-horse-battery-staple"),
        full_name="Admin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
