"""Azure Event Hubs adapter: checkpoint after handler success.

queue_name maps to an event hub in the configured namespace, so the request
queue and DLQ event hubs must exist. Without a checkpoint store, progress is
lost on restart.
"""

import json
from typing import Any

import structlog

from openhqm.config import QueueSettings
from openhqm.exceptions import QueueError
from openhqm.queue.base import Handler, Queue

logger = structlog.get_logger(__name__)


class AzureEventHubsQueue(Queue):
    def __init__(self, cfg: QueueSettings):
        self.connection_string = cfg.azure_eventhubs_connection_string
        self.consumer_group = cfg.azure_eventhubs_consumer_group
        self.checkpoint_store_connection = cfg.azure_eventhubs_checkpoint_store or None
        self.checkpoint_store = None
        self._producers: dict[str, Any] = {}
        self._consumer = None

    async def connect(self) -> None:
        try:
            from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore
        except ImportError as e:
            raise QueueError(f"Azure Event Hubs support not installed: {e}") from e

        if self.checkpoint_store_connection:
            self.checkpoint_store = BlobCheckpointStore.from_connection_string(
                conn_str=self.checkpoint_store_connection, container_name="checkpoints"
            )
        logger.info("Azure Event Hubs configured", consumer_group=self.consumer_group)

    async def close(self) -> None:
        for producer in self._producers.values():
            await producer.close()
        self._producers.clear()
        if self._consumer:
            await self._consumer.close()

    def _producer(self, eventhub_name: str):
        from azure.eventhub.aio import EventHubProducerClient

        if eventhub_name not in self._producers:
            self._producers[eventhub_name] = EventHubProducerClient.from_connection_string(
                conn_str=self.connection_string, eventhub_name=eventhub_name
            )
        return self._producers[eventhub_name]

    async def publish(self, queue_name: str, message: dict[str, Any]) -> None:
        from azure.eventhub import EventData

        try:
            producer = self._producer(queue_name)
            batch = await producer.create_batch()
            batch.add(EventData(json.dumps(message)))
            await producer.send_batch(batch)
        except Exception as e:
            raise QueueError(f"Event Hubs publish failed: {e}") from e

    async def consume(self, queue_name: str, handler: Handler, batch_size: int = 10) -> None:
        from azure.eventhub.aio import EventHubConsumerClient

        self._consumer = EventHubConsumerClient.from_connection_string(
            conn_str=self.connection_string,
            consumer_group=self.consumer_group,
            eventhub_name=queue_name,
            checkpoint_store=self.checkpoint_store,
        )

        async def on_event(partition_context, event):
            if event is None:
                return
            try:
                await handler(json.loads(event.body_as_str()))
                await partition_context.update_checkpoint(event)
            except Exception:
                logger.exception(
                    "Handler failed, event not checkpointed",
                    partition=partition_context.partition_id,
                )

        logger.info("Consuming", eventhub=queue_name, consumer_group=self.consumer_group)
        async with self._consumer:
            await self._consumer.receive(on_event=on_event, starting_position="-1")
