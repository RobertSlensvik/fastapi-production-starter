# Common tasks — run with `just <recipe>` (https://github.com/casey/just)

# Show available recipes
default:
    @just --list

# ─── Setup ──────────────────────────────────────────────────────────────────

# Install dependencies (creates .venv via uv)
install:
    uv venv
    uv pip install -e ".[dev]"

# Install pre-commit hooks
install-hooks:
    uv run pre-commit install

# ─── Run ────────────────────────────────────────────────────────────────────

# Run dev server with auto-reload
dev:
    uv run uvicorn app:create_app --factory --reload --port 8000

# Run prod server (gunicorn + uvicorn workers)
serve:
    uv run gunicorn 'app:create_app()' \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --access-logfile - --error-logfile -

# ─── Quality ────────────────────────────────────────────────────────────────

# Format code with ruff
fmt:
    uv run ruff format src tests
    uv run ruff check --fix src tests

# Lint
lint:
    uv run ruff check src tests
    uv run ruff format --check src tests

# Type-check
typecheck:
    uv run mypy src

# Run all quality checks (matches CI)
check: lint typecheck test

# ─── Tests ──────────────────────────────────────────────────────────────────

# Run tests
test:
    uv run pytest

# Run tests with coverage report
test-cov:
    uv run pytest --cov --cov-report=term-missing --cov-report=html

# Run only fast tests (skip integration)
test-fast:
    uv run pytest -m "not slow and not integration"

# ─── Database ───────────────────────────────────────────────────────────────

# Create a new migration (usage: just migrate "add users table")
migrate name:
    uv run alembic revision --autogenerate -m "{{name}}"

# Apply migrations
migrate-up:
    uv run alembic upgrade head

# Roll back one migration
migrate-down:
    uv run alembic downgrade -1

# ─── Docker ─────────────────────────────────────────────────────────────────

# Build Docker image
docker-build:
    docker build -t fastapi-starter:dev .

# Run full stack (API + Postgres + Redis)
docker-up:
    docker compose up -d --build

# Stop stack
docker-down:
    docker compose down

# Tail container logs
docker-logs:
    docker compose logs -f api

# ─── Cleanup ────────────────────────────────────────────────────────────────

clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
