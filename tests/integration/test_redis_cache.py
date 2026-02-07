"""Integration tests for Redis cache."""

import pytest

from openhqm.cache.redis_cache import RedisCache


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_cache_set_get():
    """Test setting and getting values."""
    cache = RedisCache(url="redis://localhost:6379")
    await cache.connect()

    # Set value
    success = await cache.set("test-key", {"data": "value"}, ttl=60)
    assert success is True

    # Get value
    value = await cache.get("test-key")
    assert value == {"data": "value"}

    # Cleanup
    await cache.delete("test-key")
    await cache.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_cache_exists():
    """Test checking key existence."""
    cache = RedisCache(url="redis://localhost:6379")
    await cache.connect()

    # Set value
    await cache.set("test-exists", {"data": "value"})

    # Check existence
    exists = await cache.exists("test-exists")
    assert exists is True

    # Delete
    await cache.delete("test-exists")

    # Check again
    exists = await cache.exists("test-exists")
    assert exists is False

    await cache.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_cache_delete():
    """Test deleting keys."""
    cache = RedisCache(url="redis://localhost:6379")
    await cache.connect()

    # Set value
    await cache.set("test-delete", {"data": "value"})

    # Delete
    success = await cache.delete("test-delete")
    assert success is True

    # Verify deleted
    value = await cache.get("test-delete")
    assert value is None

    await cache.close()
