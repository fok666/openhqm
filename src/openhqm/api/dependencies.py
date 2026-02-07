"""Dependency injection for FastAPI."""

from typing import AsyncGenerator

from openhqm.queue.factory import create_queue
from openhqm.queue.interface import MessageQueueInterface
from openhqm.cache.factory import create_cache
from openhqm.cache.interface import CacheInterface

# Global instances
_queue_instance: MessageQueueInterface | None = None
_cache_instance: CacheInterface | None = None


async def get_queue() -> MessageQueueInterface:
    """
    Get message queue instance.

    Returns:
        Message queue instance
    """
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = await create_queue()
    return _queue_instance


async def get_cache() -> CacheInterface:
    """
    Get cache instance.

    Returns:
        Cache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = await create_cache()
    return _cache_instance


async def cleanup_resources():
    """Clean up global resources on shutdown."""
    global _queue_instance, _cache_instance

    if _queue_instance:
        await _queue_instance.disconnect()
        _queue_instance = None

    if _cache_instance:
        await _cache_instance.close()
        _cache_instance = None
