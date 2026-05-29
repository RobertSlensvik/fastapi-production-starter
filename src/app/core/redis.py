"""Redis connection management.

Single shared `redis.asyncio.Redis` client with a connection pool. Initialized
in app lifespan, closed on shutdown. Used for rate limiting and cache.
"""

from redis.asyncio import Redis, from_url

from app.config import Settings

_client: Redis | None = None


async def init_redis(settings: Settings) -> None:
    global _client
    _client = from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> Redis:
    """FastAPI dependency: return the shared client."""
    if _client is None:
        raise RuntimeError("Redis client not initialized — did lifespan run?")
    return _client
