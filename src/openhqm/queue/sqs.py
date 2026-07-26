"""AWS SQS adapter (aioboto3): long polling, delete after handler success."""

import json
from contextlib import AsyncExitStack
from typing import Any

import structlog

from openhqm.config import QueueSettings
from openhqm.exceptions import QueueError
from openhqm.queue.base import Handler, Queue

logger = structlog.get_logger(__name__)


class SQSQueue(Queue):
    def __init__(self, cfg: QueueSettings):
        self.region = cfg.sqs_region
        self.request_queue_url = cfg.sqs_queue_url  # optional; other queues resolve by name
        self.request_queue_name = cfg.request_queue_name
        self.client = None
        self._stack: AsyncExitStack | None = None
        self._urls: dict[str, str] = {}

    async def connect(self) -> None:
        import aioboto3

        try:
            self._stack = AsyncExitStack()
            session = aioboto3.Session()
            self.client = await self._stack.enter_async_context(
                session.client("sqs", region_name=self.region)
            )
        except Exception as e:
            raise QueueError(f"SQS connect failed: {e}") from e
        logger.info("Connected to SQS", region=self.region)

    async def close(self) -> None:
        if self._stack:
            await self._stack.aclose()

    async def _url(self, queue_name: str) -> str:
        if queue_name not in self._urls:
            if queue_name == self.request_queue_name and self.request_queue_url:
                self._urls[queue_name] = self.request_queue_url
            else:
                resp = await self.client.get_queue_url(QueueName=queue_name)
                self._urls[queue_name] = resp["QueueUrl"]
        return self._urls[queue_name]

    async def publish(self, queue_name: str, message: dict[str, Any]) -> None:
        try:
            await self.client.send_message(
                QueueUrl=await self._url(queue_name), MessageBody=json.dumps(message)
            )
        except Exception as e:
            raise QueueError(f"SQS publish failed: {e}") from e

    async def consume(self, queue_name: str, handler: Handler, batch_size: int = 10) -> None:
        url = await self._url(queue_name)
        logger.info("Consuming", queue=queue_name)
        while True:
            resp = await self.client.receive_message(
                QueueUrl=url,
                MaxNumberOfMessages=min(batch_size, 10),  # SQS hard limit
                WaitTimeSeconds=20,
            )
            for msg in resp.get("Messages", []):
                try:
                    await handler(json.loads(msg["Body"]))
                    await self.client.delete_message(
                        QueueUrl=url, ReceiptHandle=msg["ReceiptHandle"]
                    )
                except Exception:
                    # not deleted -> redelivered after the visibility timeout
                    logger.exception("Handler failed, message will be redelivered")
