# Architecture

## Request lifecycle

```
Client → CORS → RequestID → AccessLog → Metrics → Route
                                                    ↓
                                              Dependencies
                                               (Settings,
                                                DB Session,
                                                CurrentUser,
                                                ApiKey,
                                                RateLimit)
                                                    ↓
                                                Handler
                                                    ↓
                                                Response
                                                    ↓
   ← (middleware unwinds in reverse, exception handlers if needed)
```

Middleware order matters. `RequestIDMiddleware` runs early so its contextvar
is available to all downstream middleware (and their logs). `MetricsMiddleware`
runs late so it sees the final status, including those set by exception handlers.

## App factory pattern

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    app = FastAPI(lifespan=_lifespan, ...)
    app.state.settings = settings
    # middleware, exception handlers, routers, observability
    return app
```

Why a factory?
- **Test isolation**: each test can build its own app instance with custom settings.
- **No import-time side effects**: importing `app` doesn't connect to DB.
- **Multi-instance**: can run multiple apps in the same process if needed.

## Lifespan management

```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    await init_engine(settings)     # SQLAlchemy pool
    await init_redis(settings)      # Redis client
    yield
    await dispose_engine()
    await close_redis()
```

Resources are initialized once per app instance and shared across requests.
This is critical for connection pools — without lifespan management you'd
create new connections per request, exhausting the database.

## Dependency injection

FastAPI's `Depends()` is the wiring layer. We define dependency callables in
`api/deps.py` and use `Annotated[T, Depends(callable)]` aliases for ergonomics:

```python
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]

async def my_handler(session: SessionDep, user: CurrentUser): ...
```

This pattern:
- Auto-injects dependencies (no manual passing)
- Validates via type hints
- Documents requirements in the function signature
- Trivially mockable in tests (override via `app.dependency_overrides`)

## Database layer

**Two layers of indirection:**
1. **Engine** (module-level, init in lifespan) — the connection pool.
2. **Session factory** — bound to engine, creates per-request sessions.
3. **`get_session()` dependency** — yields a session, commits on success,
   rolls back on exception.

This separates pool management (long-lived) from transaction scope (per-request).

**Migrations** use Alembic in async mode (`alembic/env.py`). The `target_metadata`
is `Base.metadata`, and importing `app.db.models` registers all models with it
for autogenerate to detect schema changes.

## Auth

**JWT for users:**
- Sign with `SECRET_KEY` (HMAC) or RSA key pair (set `JWT_ALGORITHM=RS256`).
- Short-lived access tokens (default 60 min). Add refresh tokens when needed.
- Decoded in `get_current_user` dependency → loaded from DB.

**API keys for services:**
- Stored in env var `API_KEYS=key1,key2` for simplicity.
- Validated in constant time via `hmac.compare_digest`.
- For larger deployments, replace with DB-backed hashed keys (use the same
  `password.py` Argon2 pattern).

**Argon2id** beats bcrypt:
- Resistant to GPU/ASIC attacks
- Memory-hard (default 64 MiB per hash)
- Winner of the Password Hashing Competition (2015)

## Error handling

Single error response shape across all paths:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Email is required",
    "details": { "errors": [...] }
  }
}
```

Stable `code` strings let clients branch on errors programmatically.
`message` is human-readable. `details` is optional structured context.

Handler registration in `core/errors.py` covers:
- `AppError` subclasses (`NotFoundError`, `ConflictError`, etc.)
- FastAPI's `HTTPException`
- Pydantic's `RequestValidationError`
- SQLAlchemy errors (logged with stacktrace, returned as generic 500/409)
- Bare `Exception` (last-resort)

## Observability

**Structured logging** via structlog:
- Processors enrich every log: timestamp, level, request_id (from contextvar)
- Renderer: dev gets colored key=value; prod gets JSON
- Stdlib loggers (uvicorn, sqlalchemy) routed through the same formatter

**Correlation** via `X-Request-ID`:
- Middleware sets contextvar from incoming header (or generates UUID)
- `request_id` appears in every log line within the request
- Echoed back in response header so clients/proxies can chain it

**Metrics** via prometheus-client:
- `MetricsMiddleware` records counters + histograms per request
- `/metrics` endpoint exposes them in Prometheus format
- Uses route template (`/users/{user_id}`) as label to avoid cardinality explosion

## Rate limiting

**Algorithm**: fixed-window via Redis `INCR` + `EXPIRE`. Simple, O(1), and
sufficient for most API rate limiting. For sub-second precision use a token
bucket implementation.

**Granularity**: per-IP per-route by default. Override `key_prefix` to share
limits across endpoints, or use the authenticated user ID instead of IP.

Applied as a route dependency:

```python
@router.post("/login", dependencies=[Depends(rate_limit("5/minute"))])
```

## Testing strategy

| Test type | Tooling | Speed |
|---|---|---|
| Unit (auth/jwt/password) | pytest, no fixtures | <1ms each |
| Integration (endpoints) | pytest + httpx AsyncClient + real Postgres + fakeredis | 50-200ms each |
| Smoke (Docker) | `docker compose up` + curl | manual |

Integration tests use a **shared engine** for the test session and **rolled-back
sessions** per test, giving full isolation without truncating tables. The CI
workflow spins up a Postgres service container.

## Production deployment

The Dockerfile is multi-stage to keep the runtime image lean (~150 MB).
Production runs `gunicorn` with multiple `UvicornWorker` processes.

Recommended production checklist:
- [ ] Set `APP_ENV=production`
- [ ] Load `SECRET_KEY` from secrets manager (never `.env` in prod)
- [ ] Set `CORS_ORIGINS` explicitly (no `*`)
- [ ] Enable `APP_LOG_JSON=true` for log aggregation
- [ ] Configure `DATABASE_POOL_SIZE` based on load (~5-10 per worker)
- [ ] Set up Prometheus scraping at `/metrics`
- [ ] Add Sentry or similar for exception tracking (drop into `core/errors.py`)
- [ ] Run migrations as a separate job, not in app startup
- [ ] Set up rate limits on more endpoints than just login
