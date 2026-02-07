"""Test configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator

import pytest

from openhqm.cache.redis_cache import RedisCache
from openhqm.queue.redis_queue import RedisQueue


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_queue() -> AsyncGenerator[RedisQueue]:
    """Create Redis queue for testing."""
    queue = RedisQueue(url="redis://localhost:6379")
    await queue.connect()
    yield queue
    await queue.disconnect()


@pytest.fixture
async def redis_cache() -> AsyncGenerator[RedisCache]:
    """Create Redis cache for testing."""
    cache = RedisCache(url="redis://localhost:6379")
    await cache.connect()
    yield cache
    await cache.close()
