"""Redis result store: request status + backend response, TTL'd, polled by clients.

meta_key(id) tracks status (PENDING/PROCESSING/COMPLETED/FAILED);
resp_key(id) holds the forwarded backend response.
"""

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from openhqm.config import settings

logger = structlog.get_logger(__name__)


def meta_key(correlation_id: str) -> str:
    return f"req:{correlation_id}:meta"


def resp_key(correlation_id: str) -> str:
    return f"resp:{correlation_id}"


class Cache:
    """JSON-over-Redis store. Read errors return None, write errors return False."""

    def __init__(self, url: str, default_ttl: int = 3600, max_connections: int = 10):
        self.url = url
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self.redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        self.redis = aioredis.from_url(
            self.url, max_connections=self.max_connections, decode_responses=True
        )
        await self.redis.ping()  # type: ignore[misc]
        logger.info("Connected to Redis cache", url=self.url)

    async def close(self) -> None:
        if self.redis:
            await self.redis.aclose()

    async def get(self, key: str) -> dict[str, Any] | None:
        if self.redis is None:
            raise RuntimeError("Cache.connect() not called")
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error("Cache get failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> bool:
        if self.redis is None:
            raise RuntimeError("Cache.connect() not called")
        try:
            await self.redis.set(key, json.dumps(value), ex=ttl or self.default_ttl)
            return True
        except Exception as e:
            logger.error("Cache set failed", key=key, error=str(e))
            return False


async def create_cache() -> Cache:
    """Create and connect the result store from settings."""
    cache = Cache(
        url=settings.cache.redis_url,
        default_ttl=settings.cache.ttl_seconds,
        max_connections=settings.cache.max_connections,
    )
    await cache.connect()
    return cache
