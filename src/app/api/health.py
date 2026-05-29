"""Liveness and readiness endpoints.

- `/health` (liveness): always 200 if the process is running. Used by
  orchestrators (k8s, Docker) to detect dead processes.
- `/ready` (readiness): returns 200 only if external dependencies (DB) are
  reachable. Use this for traffic gating during rollouts.
"""

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import SessionDep

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: str
    checks: dict[str, str] | None = None


@router.get("/health", response_model=HealthStatus, status_code=status.HTTP_200_OK)
async def health() -> HealthStatus:
    """Liveness: process is alive."""
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus)
async def ready(session: SessionDep) -> HealthStatus:
    """Readiness: all dependencies are reachable.

    Currently checks: database connectivity. Extend with Redis / external
    APIs if your app depends on them at request time.
    """
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return HealthStatus(status=overall, checks=checks)
