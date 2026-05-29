"""Redis-backed sliding-window rate limiter.

Usage in a route:

    from fastapi import Depends
    from app.core.ratelimit import rate_limit

    @router.post("/login", dependencies=[Depends(rate_limit("5/minute"))])
    async def login(...): ...

Implementation: fixed-window with INCR + EXPIRE. Fast (O(1) per request),
slightly less precise than sliding-window-log near window boundaries but
fine for most API rate limiting use cases.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.core.redis import get_redis

_UNITS = {"second": 1, "minute": 60, "hour": 3600, "day": 86_400}


def _parse_rate(spec: str) -> tuple[int, int]:
    """Parse a rate specification like '100/minute' → (100, 60).

    Accepted units: second, minute, hour, day. Also accepts 's', 'm', 'h', 'd'.
    """
    try:
        count_str, unit = spec.split("/")
        count = int(count_str)
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid rate: {spec!r} — expected '<n>/<unit>'") from e

    unit = unit.strip().lower()
    short = {"s": "second", "m": "minute", "h": "hour", "d": "day"}
    unit = short.get(unit, unit)

    if unit not in _UNITS:
        raise ValueError(f"Unknown unit {unit!r}")
    return count, _UNITS[unit]


def rate_limit(
    spec: str, key_prefix: str | None = None
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Build a FastAPI dependency that enforces `spec` per client IP.

    `spec` examples: '5/minute', '1000/hour', '10/s'.
    `key_prefix` lets you override the cache key (default = route path).
    """
    count, window_seconds = _parse_rate(spec)

    async def _check(request: Request, redis: Any = Depends(get_redis)) -> None:
        client = request.client.host if request.client else "unknown"
        prefix = key_prefix or request.scope.get("path", "global")
        key = f"rl:{prefix}:{client}"

        # INCR returns the new value; on first call also set TTL.
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)

        if current > count:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded — max {count} per {window_seconds}s",
                headers={"Retry-After": str(window_seconds)},
            )

    return _check
