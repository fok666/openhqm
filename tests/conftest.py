"""Test configuration and fixtures."""

import asyncio
import socket
from collections.abc import AsyncGenerator

import pytest

from openhqm.cache.redis_cache import RedisCache
from openhqm.queue.redis_queue import RedisQueue


def _check_redis_available(host: str = "localhost", port: int = 6379) -> bool:
    """Check if Redis is reachable."""
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (ConnectionRefusedError, OSError):
        return False


@pytest.fixture(scope="session")
def redis_available() -> bool:
    """Session-scoped fixture indicating whether Redis is available."""
    return _check_redis_available()


@pytest.fixture(autouse=True)
def skip_integration_without_redis(request, redis_available):
    """Auto-skip integration tests that require Redis when it is not running."""
    if request.node.get_closest_marker("integration") and not redis_available:
        pytest.skip("Redis not available (start Redis to run integration tests)")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_queue(redis_available) -> AsyncGenerator[RedisQueue]:
    """Create Redis queue for testing."""
    if not redis_available:
        pytest.skip("Redis not available")
    queue = RedisQueue(url="redis://localhost:6379")
    await queue.connect()
    yield queue
    await queue.disconnect()


@pytest.fixture
async def redis_cache(redis_available) -> AsyncGenerator[RedisCache]:
    """Create Redis cache for testing."""
    if not redis_available:
        pytest.skip("Redis not available")
    cache = RedisCache(url="redis://localhost:6379")
    await cache.connect()
    yield cache
    await cache.close()
