# FastAPI Production Starter

> Opinionated, production-ready FastAPI template. Async-first, observable, testable, deployable.
> Fork to start a new API in minutes — no wrestling with auth, logging, or CI scaffolding.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/your-user/fastapi-production-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/your-user/fastapi-production-starter/actions/workflows/ci.yml)

---

## Why this template

Setting up a new API from scratch each time wastes hours on the same plumbing:
auth, logging, error handling, testing, Docker, CI. This starter ships them
all configured, so you can focus on your domain logic from day one.

It's opinionated — Postgres (not Mongo), async (not sync), pytest (not unittest),
JWT + API keys (not OAuth flows), Argon2 (not bcrypt). If those match your
stack, you'll save days. If they don't, swap them out cleanly via the modular
structure.

## Features

| Concern | Solution |
|---|---|
| **Framework** | FastAPI 0.110+ with async I/O |
| **App pattern** | `create_app()` factory — test-friendly, multi-instance |
| **Config** | Pydantic Settings, env-var-driven, type-safe |
| **Database** | Async SQLAlchemy 2.x + Alembic migrations + PostgreSQL 16 |
| **Cache** | Redis (asyncio client) with pooled connections |
| **Auth** | JWT (Argon2-hashed passwords) + API keys |
| **Rate limiting** | Redis-backed sliding window, per-IP + per-endpoint |
| **Logging** | `structlog` JSON output + request-ID correlation |
| **Metrics** | Prometheus `/metrics` (request counts + latency histograms) |
| **Health** | `/health` (liveness) + `/ready` (checks DB) |
| **Errors** | Consistent `{"error": {"code", "message"}}` JSON shape |
| **Testing** | pytest + pytest-asyncio + httpx async client + fakeredis |
| **CI** | GitHub Actions: lint → typecheck → test (PG service) → build |
| **Quality** | ruff (lint/format) + mypy strict + pre-commit hooks |
| **Deployment** | Multi-stage Dockerfile (~150 MB image) + docker-compose stack |
| **Dev tools** | `just` recipes, `uv` for fast deps |

## Quick start

```bash
# Clone + setup
git clone <your-repo-url>
cd fastapi-production-starter
cp .env.example .env

# Install (with uv — install from https://astral.sh/uv if needed)
just install

# Run the full stack (API + PG + Redis)
just docker-up

# Run migrations
docker compose exec api alembic upgrade head

# Visit
open http://localhost:8000/docs
```

Without Docker:

```bash
just install
# Make sure PG + Redis are running on default ports
just migrate-up
just dev
```

## Project structure

```
fastapi-production-starter/
├── src/app/
│   ├── __init__.py           # create_app() factory + lifespan
│   ├── config.py             # Pydantic Settings
│   ├── core/
│   │   ├── errors.py         # AppError + handlers
│   │   ├── logging.py        # structlog + request-id contextvar
│   │   ├── middleware.py     # RequestID + AccessLog
│   │   ├── ratelimit.py      # Redis-backed rate limiter
│   │   └── redis.py          # Connection pool
│   ├── auth/
│   │   ├── apikey.py         # X-API-Key validation
│   │   ├── jwt.py            # encode/decode tokens
│   │   └── password.py       # Argon2id
│   ├── db/
│   │   ├── base.py           # DeclarativeBase + TimestampMixin
│   │   ├── session.py        # Async engine + get_session()
│   │   └── models/user.py    # Example User model
│   ├── api/
│   │   ├── deps.py           # FastAPI Depends() — auth, db, settings
│   │   ├── health.py         # /health, /ready
│   │   ├── auth.py           # /auth/login, /auth/me
│   │   └── users.py          # /users CRUD
│   └── observability/
│       └── metrics.py        # Prometheus middleware + /metrics
├── tests/
│   ├── conftest.py           # Fixtures (app, client, db, users)
│   ├── test_auth_unit.py     # Pure functions, no I/O
│   ├── test_auth_integration.py
│   ├── test_health.py
│   └── test_users.py
├── alembic/                  # Database migrations
├── .github/workflows/ci.yml
├── Dockerfile                # Multi-stage build
├── docker-compose.yml        # API + PG + Redis
├── justfile                  # Task runner recipes
└── pyproject.toml            # Project + ruff + mypy + pytest config
```

## Adding a new resource

1. **Model** — `src/app/db/models/your_thing.py`
2. **Export** in `src/app/db/models/__init__.py`
3. **Migration** — `just migrate "add your_thing table"`
4. **Schemas + routes** — `src/app/api/your_thing.py`
5. **Register** in `src/app/__init__.py` factory
6. **Tests** — `tests/test_your_thing.py`

Copy the `users.py` pattern — schemas use Pydantic, queries use SQLAlchemy
`select()`, auth via `CurrentUser`/`SuperUser` dependencies.

## API reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | none | Liveness probe |
| `/ready` | GET | none | Readiness — checks DB |
| `/metrics` | GET | none | Prometheus metrics |
| `/docs` | GET | none | Swagger UI (dev only) |
| `/auth/login` | POST | none | Get JWT (5/min rate-limited) |
| `/auth/me` | GET | JWT | Current user info |
| `/users` | POST | superuser | Create user |
| `/users` | GET | JWT | List users (paginated) |
| `/users/{id}` | GET | JWT | Get one |
| `/users/{id}` | PATCH | superuser | Update |
| `/users/{id}` | DELETE | superuser | Delete |

All errors return:
```json
{ "error": { "code": "string", "message": "string", "details": {} } }
```

Stable codes: `validation_error`, `unauthorized`, `forbidden`, `not_found`,
`conflict`, `database_error`, `internal_error`, plus `http_<status>` for
generic HTTPException.

## Development workflow

```bash
just dev          # Hot-reload dev server
just fmt          # Format + autofix
just lint         # Check lint + format
just typecheck    # mypy
just test         # All tests
just test-fast    # Skip integration tests
just check        # lint + typecheck + test (matches CI)
just migrate "add things table"
just migrate-up
```

## Observability

**Logs** are JSON when `APP_LOG_JSON=true` (production). Every log line within
a request includes `request_id` so you can trace a single request across all
its log messages and downstream services that propagate `X-Request-ID`.

**Metrics** at `/metrics` follow Prometheus exposition format:
- `http_requests_total{method, path, status}` — counter
- `http_request_duration_seconds{method, path}` — histogram with buckets tuned for API latency

Scrape with Prometheus, alert with PromQL, dashboard with Grafana.

## Security notes

- **Always set `SECRET_KEY`** from a real secret in non-dev environments.
  The config validator enforces ≥32 chars outside `development`.
- **API keys** are stored in env vars in this starter. For many keys or
  per-key permissions, persist hashed keys in the DB — see the User model
  for the pattern.
- **CORS origins** are environment-driven. Never use `*` in production with
  `allow_credentials=True`.
- **Rate limiting** is applied to `/auth/login` by default. Add `Depends(rate_limit(...))`
  to other sensitive endpoints.
- **Argon2id** parameters in `auth/password.py` are tuned for ~100ms/hash on
  modern hardware. Benchmark on your production server and adjust.

## License

[MIT](LICENSE)
