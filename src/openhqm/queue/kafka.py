"""Apache Kafka adapter (aiokafka): consumer group, commit after handler success."""

import json
from typing import Any

import structlog

from openhqm.config import QueueSettings
from openhqm.exceptions import QueueError
from openhqm.queue.base import Handler, Queue

logger = structlog.get_logger(__name__)


class KafkaQueue(Queue):
    def __init__(self, cfg: QueueSettings):
        self.bootstrap_servers = cfg.kafka_bootstrap_servers
        self.group = cfg.kafka_consumer_group
        self.producer = None
        self.consumer = None

    async def connect(self) -> None:
        from aiokafka import AIOKafkaProducer

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode(),
            )
            await self.producer.start()
        except Exception as e:
            raise QueueError(f"Kafka connect failed: {e}") from e
        logger.info("Connected to Kafka", servers=self.bootstrap_servers)

    async def close(self) -> None:
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

    async def publish(self, queue_name: str, message: dict[str, Any]) -> None:
        try:
            await self.producer.send_and_wait(queue_name, message)
        except Exception as e:
            raise QueueError(f"Kafka publish failed: {e}") from e

    async def consume(self, queue_name: str, handler: Handler, batch_size: int = 10) -> None:
        from aiokafka import AIOKafkaConsumer

        self.consumer = AIOKafkaConsumer(
            queue_name,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group,
            value_deserializer=lambda v: json.loads(v.decode()),
            enable_auto_commit=False,
        )
        await self.consumer.start()
        logger.info("Consuming", topic=queue_name, group=self.group)
        async for record in self.consumer:
            try:
                await handler(record.value)
                await self.consumer.commit()
            except Exception:
                # ponytail: uncommitted offset only redelivers after restart/rebalance;
                # pause+seek here if same-session retry matters
                logger.exception(
                    "Handler failed, offset not committed",
                    topic=record.topic,
                    offset=record.offset,
                )
