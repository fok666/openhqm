"""Redis Streams adapter: consumer group, ack on handler success."""

import asyncio
import json
from typing import Any
from uuid import uuid4

import redis.asyncio as aioredis
import structlog

from openhqm.config import QueueSettings
from openhqm.exceptions import QueueError
from openhqm.queue.base import Handler, Queue

logger = structlog.get_logger(__name__)


class RedisQueue(Queue):
    def __init__(self, cfg: QueueSettings):
        self.url = cfg.redis_url
        self.group = "openhqm-workers"
        self.consumer = f"consumer-{uuid4().hex[:8]}"
        self.redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        try:
            self.redis = aioredis.from_url(self.url, decode_responses=True)
            await self.redis.ping()
        except Exception as e:
            raise QueueError(f"Redis connect failed: {e}") from e
        logger.info("Connected to Redis queue", url=self.url)

    async def close(self) -> None:
        if self.redis:
            await self.redis.aclose()

    async def publish(self, queue_name: str, message: dict[str, Any]) -> None:
        try:
            await self.redis.xadd(queue_name, {"payload": json.dumps(message)})
        except Exception as e:
            raise QueueError(f"Redis publish failed: {e}") from e

    async def consume(self, queue_name: str, handler: Handler, batch_size: int = 10) -> None:
        try:
            await self.redis.xgroup_create(queue_name, self.group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise QueueError(f"Redis consumer group setup failed: {e}") from e

        logger.info("Consuming", stream=queue_name, group=self.group, consumer=self.consumer)
        while True:
            try:
                batches = await self.redis.xreadgroup(
                    self.group, self.consumer, {queue_name: ">"}, count=batch_size, block=1000
                )
                for _stream, entries in batches or []:
                    for entry_id, fields in entries:
                        try:
                            await handler(json.loads(fields["payload"]))
                            await self.redis.xack(queue_name, self.group, entry_id)
                        except Exception:
                            # ponytail: unacked entries stay pending; add periodic
                            # XAUTOCLAIM if crashed-consumer redelivery matters
                            logger.exception("Handler failed, message left pending", id=entry_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Consumer loop error, retrying in 1s")
                await asyncio.sleep(1)
