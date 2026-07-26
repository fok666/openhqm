"""Queue contract and factory.

To add a backend:
  1. implement Queue in a module under openhqm/queue/,
  2. add one line to _ADAPTERS below,
  3. add its settings fields to QueueSettings and its dependency as a pyproject extra.

Or skip all that and use type=custom to load your own class at runtime.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from importlib import import_module
from typing import Any

import structlog

from openhqm.config import settings
from openhqm.exceptions import QueueError

logger = structlog.get_logger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[Any]]


class Queue(ABC):
    """Minimal queue contract: publish dicts, consume dicts at-least-once.

    Acknowledgment is the adapter's job: ack after ``handler`` returns,
    leave the message for redelivery when it raises.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the backend. Raises QueueError on failure."""

    @abstractmethod
    async def close(self) -> None:
        """Release connections. Safe to call when never connected."""

    @abstractmethod
    async def publish(self, queue_name: str, message: dict[str, Any]) -> None:
        """Publish one message. Raises QueueError on failure."""

    @abstractmethod
    async def consume(self, queue_name: str, handler: Handler, batch_size: int = 10) -> None:
        """Consume until cancelled, awaiting handler(message) for each message."""


_ADAPTERS = {
    "redis": ("openhqm.queue.redis_queue", "RedisQueue"),
    "kafka": ("openhqm.queue.kafka", "KafkaQueue"),
    "sqs": ("openhqm.queue.sqs", "SQSQueue"),
    "azure_eventhubs": ("openhqm.queue.azure_eventhubs", "AzureEventHubsQueue"),
    "gcp_pubsub": ("openhqm.queue.gcp_pubsub", "GCPPubSubQueue"),
    "mqtt": ("openhqm.queue.mqtt", "MQTTQueue"),
}


async def create_queue() -> Queue:
    """Create and connect the queue selected by OPENHQM_QUEUE__TYPE."""
    cfg = settings.queue

    if cfg.type == "custom":
        if not cfg.custom_module or not cfg.custom_class:
            raise QueueError(
                "custom queue requires OPENHQM_QUEUE__CUSTOM_MODULE and OPENHQM_QUEUE__CUSTOM_CLASS"
            )
        queue_class = getattr(import_module(cfg.custom_module), cfg.custom_class)
        queue = queue_class(**cfg.custom_config)
    else:
        module_name, class_name = _ADAPTERS[cfg.type]
        try:
            queue_class = getattr(import_module(module_name), class_name)
        except ImportError as e:
            extra = cfg.type.split("_")[0]  # azure_eventhubs -> azure, gcp_pubsub -> gcp
            raise QueueError(
                f"{cfg.type} support is not installed — pip install 'openhqm[{extra}]' ({e})"
            ) from e
        queue = queue_class(cfg)

    await queue.connect()
    logger.info("Queue connected", type=cfg.type)
    return queue
