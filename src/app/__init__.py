"""FastAPI application factory.

Use `create_app()` everywhere (uvicorn `--factory`, gunicorn, tests). Avoid
module-level FastAPI instances — they prevent test isolation and re-instantiation.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import AccessLogMiddleware, RequestIDMiddleware

__version__ = "0.1.0"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup & shutdown hooks. Run once per app instance."""
    settings: Settings = app.state.settings
    log = get_logger(__name__)
    log.info("startup", app=settings.app_name, env=settings.app_env, version=__version__)

    # Initialize resources that should be shared (DB pool, Redis client).
    # Lazy imports keep app importable even when these deps aren't installed
    # (e.g., during config-only tests).
    from app.core.redis import close_redis, init_redis
    from app.db.session import dispose_engine, init_engine

    await init_engine(settings)
    await init_redis(settings)
    try:
        yield
    finally:
        log.info("shutdown")
        await dispose_engine()
        await close_redis()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return a FastAPI application instance.

    Pass `settings` to override config (mainly for tests). In production,
    settings are loaded from environment variables.
    """
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.app_debug,
        lifespan=_lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )
    app.state.settings = settings

    # ─── Middleware (order matters — last added runs first) ─────────────────
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── Exception handlers ─────────────────────────────────────────────────
    register_exception_handlers(app)

    # ─── Routes ─────────────────────────────────────────────────────────────
    from app.api.auth import router as auth_router
    from app.api.health import router as health_router
    from app.api.users import router as users_router

    app.include_router(health_router)
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(users_router, prefix="/users", tags=["users"])

    # ─── Observability ──────────────────────────────────────────────────────
    if settings.metrics_enabled:
        from app.observability.metrics import setup_metrics

        setup_metrics(app)

    return app
