"""Integration tests for the Redis result store."""

import pytest

from openhqm.cache import Cache


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_set_get_roundtrip():
    cache = Cache(url="redis://localhost:6379")
    await cache.connect()
    try:
        assert await cache.set("openhqm-test-key", {"data": "value"}, ttl=60) is True
        assert await cache.get("openhqm-test-key") == {"data": "value"}
        assert await cache.get("openhqm-test-missing") is None
    finally:
        await cache.redis.delete("openhqm-test-key")
        await cache.close()
