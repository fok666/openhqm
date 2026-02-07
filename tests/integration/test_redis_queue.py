"""Integration tests for Redis queue."""

import pytest
import asyncio

from openhqm.queue.redis_queue import RedisQueue


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_queue_publish_consume():
    """Test publishing and consuming messages."""
    queue = RedisQueue(url="redis://localhost:6379")
    await queue.connect()

    # Publish message
    message = {
        "correlation_id": "test-123",
        "payload": {"data": "test"}
    }

    success = await queue.publish("test-queue", message)
    assert success is True

    # Consume message
    received = []

    async def handler(msg):
        received.append(msg)

    # Start consumer in background
    consumer_task = asyncio.create_task(
        queue.consume("test-queue", handler, batch_size=1)
    )

    # Wait for message processing
    await asyncio.sleep(2)

    # Stop consumer
    consumer_task.cancel()

    # Verify
    assert len(received) > 0
    assert received[0]["correlation_id"] == "test-123"

    await queue.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_queue_connection():
    """Test Redis queue connection."""
    queue = RedisQueue(url="redis://localhost:6379")

    await queue.connect()
    assert queue.redis is not None

    await queue.disconnect()
