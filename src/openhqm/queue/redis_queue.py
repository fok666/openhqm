"""Redis Streams implementation of message queue."""

import json
import asyncio
from typing import Dict, Any, Callable, Optional

import redis.asyncio as aioredis
import structlog

from openhqm.queue.interface import MessageQueueInterface
from openhqm.exceptions import QueueError
from openhqm.config import settings

logger = structlog.get_logger(__name__)


class RedisQueue(MessageQueueInterface):
    """Redis Streams implementation of message queue."""

    def __init__(self, url: str, max_connections: int = 10):
        """
        Initialize Redis queue.

        Args:
            url: Redis connection URL
            max_connections: Maximum connection pool size
        """
        self.url = url
        self.max_connections = max_connections
        self.redis: Optional[aioredis.Redis] = None
        self.consumer_group = "openhqm-workers"
        self.consumer_name = f"consumer-{id(self)}"
        self._running = False

    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.redis = await aioredis.from_url(
                self.url,
                max_connections=self.max_connections,
                decode_responses=True,
            )
            await self.redis.ping()
            logger.info("Connected to Redis", url=self.url)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise QueueError(f"Failed to connect to Redis: {e}")

    async def disconnect(self) -> None:
        """Close connection to Redis."""
        self._running = False
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    async def publish(
        self,
        queue_name: str,
        message: Dict[str, Any],
        priority: int = 0,
    ) -> bool:
        """
        Publish a message to Redis stream.

        Args:
            queue_name: Stream name
            message: Message payload
            priority: Priority (currently not used in Redis Streams)

        Returns:
            True if published successfully
        """
        if not self.redis:
            raise QueueError("Not connected to Redis")

        try:
            stream_name = f"{settings.queue.request_queue_name if queue_name == 'requests' else queue_name}"

            # Serialize message
            message_data = {"payload": json.dumps(message)}

            # Add to stream
            message_id = await self.redis.xadd(stream_name, message_data)

            logger.debug(
                "Published message to Redis",
                stream=stream_name,
                message_id=message_id,
                correlation_id=message.get("correlation_id"),
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to publish message",
                stream=queue_name,
                error=str(e),
            )
            return False

    async def consume(
        self,
        queue_name: str,
        handler: Callable[[Dict[str, Any]], Any],
        batch_size: int = 1,
    ) -> None:
        """
        Consume messages from Redis stream.

        Args:
            queue_name: Stream name
            handler: Async function to process messages
            batch_size: Number of messages to fetch per batch
        """
        if not self.redis:
            raise QueueError("Not connected to Redis")

        stream_name = f"{settings.queue.request_queue_name if queue_name == 'requests' else queue_name}"

        # Create consumer group if it doesn't exist
        try:
            await self.redis.xgroup_create(
                stream_name,
                self.consumer_group,
                id="0",
                mkstream=True,
            )
            logger.info("Created consumer group", stream=stream_name)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error("Failed to create consumer group", error=str(e))
                raise

        self._running = True
        logger.info(
            "Starting to consume messages",
            stream=stream_name,
            consumer=self.consumer_name,
        )

        while self._running:
            try:
                # Read messages from stream
                messages = await self.redis.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {stream_name: ">"},
                    count=batch_size,
                    block=1000,  # 1 second timeout
                )

                if not messages:
                    continue

                for stream, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        try:
                            # Deserialize message
                            payload = json.loads(message_data["payload"])

                            # Process message
                            await handler(payload)

                            # Acknowledge message
                            await self.acknowledge(message_id)

                        except Exception as e:
                            logger.error(
                                "Failed to process message",
                                message_id=message_id,
                                error=str(e),
                            )
                            # Don't acknowledge, let it be reprocessed

            except asyncio.CancelledError:
                logger.info("Consumer cancelled")
                break
            except Exception as e:
                logger.error("Error in consumer loop", error=str(e))
                await asyncio.sleep(1)

    async def acknowledge(self, message_id: str) -> bool:
        """
        Acknowledge message processing.

        Args:
            message_id: Redis stream message ID

        Returns:
            True if acknowledged
        """
        if not self.redis:
            return False

        try:
            await self.redis.xack(
                settings.queue.request_queue_name,
                self.consumer_group,
                message_id,
            )
            return True
        except Exception as e:
            logger.error("Failed to acknowledge message", message_id=message_id, error=str(e))
            return False

    async def reject(self, message_id: str, requeue: bool = True) -> bool:
        """
        Reject a message.

        Args:
            message_id: Message ID
            requeue: Whether to requeue (not used in Redis Streams)

        Returns:
            True if rejected
        """
        # In Redis Streams, not acknowledging is equivalent to rejecting
        return True

    async def get_queue_depth(self, queue_name: str) -> int:
        """
        Get queue depth.

        Args:
            queue_name: Stream name

        Returns:
            Number of pending messages
        """
        if not self.redis:
            return 0

        try:
            stream_name = f"{settings.queue.request_queue_name if queue_name == 'requests' else queue_name}"
            info = await self.redis.xpending(stream_name, self.consumer_group)
            return info["pending"] if info else 0
        except Exception:
            return 0
