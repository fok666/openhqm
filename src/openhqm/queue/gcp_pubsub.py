"""GCP Pub/Sub adapter (async clients): pull loop, ack after handler success.

publish targets the topic named queue_name; consume pulls from the
subscription named queue_name — create both with matching names.
"""

import asyncio
import json
from typing import Any

import structlog

from openhqm.config import QueueSettings
from openhqm.exceptions import QueueError
from openhqm.queue.base import Handler, Queue

logger = structlog.get_logger(__name__)


class GCPPubSubQueue(Queue):
    def __init__(self, cfg: QueueSettings):
        self.project_id = cfg.gcp_project_id
        self.credentials_path = cfg.gcp_credentials_path or None
        self.publisher = None
        self.subscriber = None

    async def connect(self) -> None:
        try:
            from google.pubsub_v1 import PublisherAsyncClient, SubscriberAsyncClient
        except ImportError as e:
            raise QueueError(f"GCP Pub/Sub support not installed: {e}") from e

        try:
            credentials = None
            if self.credentials_path:
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
            self.publisher = PublisherAsyncClient(credentials=credentials)
            self.subscriber = SubscriberAsyncClient(credentials=credentials)
        except Exception as e:
            raise QueueError(f"GCP Pub/Sub connect failed: {e}") from e
        logger.info("Connected to GCP Pub/Sub", project=self.project_id)

    async def close(self) -> None:
        for client in (self.publisher, self.subscriber):
            if client:
                await client.transport.close()

    async def publish(self, queue_name: str, message: dict[str, Any]) -> None:
        try:
            await self.publisher.publish(
                topic=f"projects/{self.project_id}/topics/{queue_name}",
                messages=[{"data": json.dumps(message).encode()}],
            )
        except Exception as e:
            raise QueueError(f"Pub/Sub publish failed: {e}") from e

    async def consume(self, queue_name: str, handler: Handler, batch_size: int = 10) -> None:
        from google.api_core.exceptions import DeadlineExceeded

        subscription = f"projects/{self.project_id}/subscriptions/{queue_name}"
        logger.info("Consuming", subscription=subscription)
        while True:
            try:
                resp = await self.subscriber.pull(
                    subscription=subscription, max_messages=batch_size, timeout=30
                )
            except DeadlineExceeded:
                continue  # no messages within the poll window
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Pull failed, retrying in 1s")
                await asyncio.sleep(1)
                continue

            ack_ids = []
            for received in resp.received_messages:
                try:
                    await handler(json.loads(received.message.data.decode()))
                    ack_ids.append(received.ack_id)
                except Exception:
                    # not acked -> redelivered after the ack deadline
                    logger.exception("Handler failed, message will be redelivered")
            if ack_ids:
                await self.subscriber.acknowledge(subscription=subscription, ack_ids=ack_ids)
