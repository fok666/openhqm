"""Integration tests for Redis queue."""

import asyncio

import pytest

from openhqm.config import QueueSettings
from openhqm.queue.redis_queue import RedisQueue


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_queue_publish_consume():
    """Test publishing and consuming messages."""
    queue = RedisQueue(QueueSettings(redis_url="redis://localhost:6379"))
    await queue.connect()

    # Publish message
    message = {"correlation_id": "test-123", "payload": {"data": "test"}}

    await queue.publish("test-queue", message)

    # Consume message
    received = []

    async def handler(msg):
        received.append(msg)

    # Start consumer in background
    consumer_task = asyncio.create_task(queue.consume("test-queue", handler, batch_size=1))

    # Wait for message processing
    await asyncio.sleep(2)

    # Stop consumer
    consumer_task.cancel()

    # Verify
    assert len(received) > 0
    assert received[0]["correlation_id"] == "test-123"

    await queue.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_queue_connection():
    """Test Redis queue connection."""
    queue = RedisQueue(QueueSettings(redis_url="redis://localhost:6379"))

    await queue.connect()
    assert queue.redis is not None

    await queue.close()
