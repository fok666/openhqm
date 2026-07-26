"""MQTT adapter (aiomqtt). Delivery guarantees come from broker QoS only.

ponytail: no app-level ack — a message that fails in the handler is logged
and dropped (the worker's own retry/DLQ logic runs before that can happen).
Use a broker-side persistent session if that ceiling matters.
"""

import json
from typing import Any
from uuid import uuid4

import structlog

from openhqm.config import QueueSettings
from openhqm.exceptions import QueueError
from openhqm.queue.base import Handler, Queue

logger = structlog.get_logger(__name__)


class MQTTQueue(Queue):
    def __init__(self, cfg: QueueSettings):
        self.host = cfg.mqtt_broker_host
        self.port = cfg.mqtt_broker_port
        self.username = cfg.mqtt_username or None
        self.password = cfg.mqtt_password or None
        self.qos = cfg.mqtt_qos
        self.client_id = cfg.mqtt_client_id or f"openhqm-{uuid4().hex[:8]}"
        self.client = None

    async def connect(self) -> None:
        try:
            import aiomqtt
        except ImportError as e:
            raise QueueError(f"MQTT support not installed: {e}") from e

        try:
            self.client = aiomqtt.Client(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                identifier=self.client_id,
            )
            await self.client.__aenter__()
        except Exception as e:
            raise QueueError(f"MQTT connect failed: {e}") from e
        logger.info("Connected to MQTT", broker=self.host, port=self.port)

    async def close(self) -> None:
        if self.client:
            await self.client.__aexit__(None, None, None)

    async def publish(self, queue_name: str, message: dict[str, Any]) -> None:
        try:
            await self.client.publish(queue_name, payload=json.dumps(message), qos=self.qos)
        except Exception as e:
            raise QueueError(f"MQTT publish failed: {e}") from e

    async def consume(self, queue_name: str, handler: Handler, batch_size: int = 10) -> None:
        await self.client.subscribe(queue_name, qos=self.qos)
        logger.info("Consuming", topic=queue_name, qos=self.qos)
        async for message in self.client.messages:
            try:
                await handler(json.loads(message.payload.decode()))
            except Exception:
                logger.exception("Handler failed, MQTT message dropped")
