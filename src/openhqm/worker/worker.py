"""Worker for the queue-to-http mode: consume messages, proxy to the backend."""

import asyncio
import signal
import time
from datetime import UTC, datetime
from typing import Any

import structlog

from openhqm.cache.factory import create_cache
from openhqm.cache.interface import CacheInterface
from openhqm.config import settings
from openhqm.exceptions import FatalError, RetryableError
from openhqm.queue.factory import create_queue
from openhqm.queue.interface import MessageQueueInterface
from openhqm.utils.metrics import metrics
from openhqm.worker.processor import MessageProcessor

logger = structlog.get_logger(__name__)


class Worker:
    """Consume requests from the queue and forward them to the backend."""

    def __init__(
        self,
        worker_id: str,
        queue: MessageQueueInterface,
        cache: CacheInterface,
        processor: MessageProcessor,
    ):
        self.worker_id = worker_id
        self.queue = queue
        self.cache = cache
        self.processor = processor
        self.running = False
        self.current_message: str | None = None

    async def start(self) -> None:
        """Consume until cancelled (SIGTERM/SIGINT), then drain and shut down."""
        self.running = True
        metrics.worker_active.labels(worker_id=self.worker_id).set(1)
        logger.info("Worker started", worker_id=self.worker_id)

        consume_task = asyncio.ensure_future(
            self.queue.consume(
                "requests", self._handle_message, batch_size=settings.worker.batch_size
            )
        )

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, consume_task.cancel)
            except NotImplementedError:
                # ponytail: add_signal_handler is Unix-only; Windows relies on KeyboardInterrupt
                pass

        try:
            await consume_task
        except asyncio.CancelledError:
            logger.info("Worker draining: stopped consuming", worker_id=self.worker_id)
        finally:
            await self.shutdown()

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Process a single message: forward to backend, store the result for polling."""
        correlation_id = message.get("correlation_id")
        self.current_message = correlation_id
        log = logger.bind(worker_id=self.worker_id, correlation_id=correlation_id)
        log.info("Processing message")
        start_time = time.time()

        try:
            await self.cache.set(
                f"req:{correlation_id}:meta",
                {
                    "status": "PROCESSING",
                    "submitted_at": message.get("timestamp"),
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                ttl=settings.cache.ttl_seconds,
            )

            result, status_code, response_headers = await self.processor.process(
                message["payload"],
                metadata=message.get("metadata") or {},
                headers=message.get("headers") or {},
            )

            processing_time = (time.time() - start_time) * 1000  # ms

            await self.cache.set(
                f"req:{correlation_id}:meta",
                {
                    "status": "COMPLETED",
                    "submitted_at": message.get("timestamp"),
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                ttl=settings.cache.ttl_seconds,
            )
            await self.cache.set(
                f"resp:{correlation_id}",
                {
                    "result": result,
                    "status_code": status_code,
                    "headers": response_headers,
                    "processing_time_ms": int(processing_time),
                    "completed_at": datetime.now(UTC).isoformat(),
                },
                ttl=settings.cache.ttl_seconds,
            )

            log.info("Message processed successfully", processing_time_ms=int(processing_time))
            metrics.worker_processing_duration_seconds.labels(status="success").observe(
                processing_time / 1000
            )

        except RetryableError as e:
            log.warning("Retryable error occurred", error=str(e))
            retry_count = message.get("metadata", {}).get("retry_count", 0)
            if retry_count < settings.worker.max_retries:
                message["metadata"]["retry_count"] = retry_count + 1
                await asyncio.sleep(2 ** retry_count)
                await self.queue.publish("requests", message)
                log.info("Message requeued", retry_count=retry_count + 1)
            else:
                log.error("Max retries exceeded, sending to DLQ")
                await self._send_to_dlq(message, str(e))
            metrics.worker_errors_total.labels(error_type="retryable").inc()

        except FatalError as e:
            log.error("Fatal error occurred", error=str(e))
            await self._send_to_dlq(message, str(e))
            await self._mark_failed(correlation_id, str(e))
            metrics.worker_errors_total.labels(error_type="fatal").inc()

        except Exception as e:
            log.exception("Unexpected error occurred")
            await self._send_to_dlq(message, str(e))
            await self._mark_failed(correlation_id, str(e))
            metrics.worker_errors_total.labels(error_type="unexpected").inc()

        finally:
            self.current_message = None

    async def _send_to_dlq(self, message: dict[str, Any], error: str) -> None:
        """Send a failed message to the dead letter queue."""
        correlation_id = message.get("correlation_id")
        try:
            await self.queue.publish(
                settings.queue.dlq_name,
                {
                    **message,
                    "failed_at": datetime.now(UTC).isoformat(),
                    "worker_id": self.worker_id,
                    "error": error,
                },
            )
            logger.info("Message sent to DLQ", correlation_id=correlation_id)
            metrics.queue_dlq_total.labels(reason="processing_failed").inc()
        except Exception as e:
            logger.error(
                "Failed to send message to DLQ", correlation_id=correlation_id, error=str(e)
            )

    async def _mark_failed(self, correlation_id: str, error: str) -> None:
        """Mark a request FAILED in the cache so pollers see the error."""
        try:
            await self.cache.set(
                f"req:{correlation_id}:meta",
                {"status": "FAILED", "updated_at": datetime.now(UTC).isoformat()},
                ttl=settings.cache.ttl_seconds,
            )
            await self.cache.set(
                f"resp:{correlation_id}",
                {"error": error, "completed_at": datetime.now(UTC).isoformat()},
                ttl=settings.cache.ttl_seconds,
            )
        except Exception as e:
            logger.error(
                "Failed to mark request as failed", correlation_id=correlation_id, error=str(e)
            )

    async def shutdown(self) -> None:
        """Release resources. The in-flight message (if any) is already done or will be redelivered."""
        logger.info("Shutting down worker", worker_id=self.worker_id)
        metrics.worker_active.labels(worker_id=self.worker_id).set(0)
        await self.queue.disconnect()
        await self.cache.close()
        logger.info("Worker shutdown complete", worker_id=self.worker_id)


async def run_worker(worker_id: str) -> None:
    """Create dependencies and run a worker instance."""
    from openhqm.utils.logging import setup_logging

    setup_logging()
    logger.info("Initializing worker", worker_id=worker_id)

    queue = await create_queue()
    cache = await create_cache()
    processor = MessageProcessor()
    try:
        await Worker(worker_id, queue, cache, processor).start()
    finally:
        await processor.close()


async def main() -> None:
    """Entry point for the queue-to-http worker."""
    import sys

    worker_id = sys.argv[1] if len(sys.argv) > 1 else "worker-1"
    await run_worker(worker_id)


if __name__ == "__main__":
    asyncio.run(main())
