"""Factory for creating cache instances."""

from openhqm.cache.interface import CacheInterface
from openhqm.cache.redis_cache import RedisCache
from openhqm.config import settings


async def create_cache() -> CacheInterface:
    """
    Create and connect cache instance based on configuration.

    Returns:
        Connected cache instance
    """
    cache_type = settings.cache.type.lower()

    if cache_type == "redis":
        cache = RedisCache(
            url=settings.cache.redis_url,
            default_ttl=settings.cache.ttl_seconds,
            max_connections=settings.cache.max_connections,
        )
        await cache.connect()
        return cache
    else:
        raise ValueError(f"Unsupported cache type: {cache_type}")
