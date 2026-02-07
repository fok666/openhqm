"""Redis cache implementation."""

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from openhqm.cache.interface import CacheInterface

logger = structlog.get_logger(__name__)


class RedisCache(CacheInterface):
    """Redis cache implementation."""

    def __init__(self, url: str, default_ttl: int = 3600, max_connections: int = 10):
        """
        Initialize Redis cache.

        Args:
            url: Redis connection URL
            default_ttl: Default TTL in seconds
            max_connections: Maximum connection pool size
        """
        self.url = url
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self.redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        self.redis = await aioredis.from_url(
            self.url,
            max_connections=self.max_connections,
            decode_responses=True,
        )
        await self.redis.ping()
        logger.info("Connected to Redis cache", url=self.url)

    async def get(self, key: str) -> dict[str, Any] | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if not self.redis:
            await self.connect()

        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Failed to get from cache", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds

        Returns:
            True if successful
        """
        if not self.redis:
            await self.connect()

        try:
            serialized = json.dumps(value)
            ttl = ttl or self.default_ttl

            await self.redis.set(key, serialized, ex=ttl)
            return True
        except Exception as e:
            logger.error("Failed to set in cache", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        if not self.redis:
            return False

        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error("Failed to delete from cache", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        if not self.redis:
            return False

        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error("Failed to check existence", key=key, error=str(e))
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Closed Redis cache connection")
