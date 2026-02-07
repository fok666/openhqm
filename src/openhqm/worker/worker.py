"""Worker implementation for processing messages."""

import signal
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional

import structlog

from openhqm.worker.processor import MessageProcessor
from openhqm.queue.interface import MessageQueueInterface
from openhqm.cache.interface import CacheInterface
from openhqm.queue.factory import create_queue
from openhqm.cache.factory import create_cache
from openhqm.exceptions import RetryableError, FatalError
from openhqm.utils.metrics import metrics
from openhqm.config import settings

logger = structlog.get_logger(__name__)


class Worker:
    """Message queue worker for processing requests."""

    def __init__(
        self,
        worker_id: str,
        queue: MessageQueueInterface,
        cache: CacheInterface,
        processor: MessageProcessor,
    ):
        """
        Initialize worker.

        Args:
            worker_id: Unique worker identifier
            queue: Message queue instance
            cache: Cache instance
            processor: Message processor
        """
        self.worker_id = worker_id
        self.queue = queue
        self.cache = cache
        self.processor = processor
        self.running = False
        self.current_message: Optional[str] = None

    async def start(self) -> None:
        """Start the worker loop."""
        self.running = True

        # Register shutdown handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        logger.info("Worker started", worker_id=self.worker_id)

        # Set worker active metric
        metrics.worker_active.labels(worker_id=self.worker_id).set(1)

        try:
            await self.queue.consume(
                "requests",
                self._handle_message,
                batch_size=settings.worker.batch_size,
            )
        except Exception as e:
            logger.exception("Worker loop failed", worker_id=self.worker_id)
            raise
        finally:
            await self.shutdown()

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """
        Process a single message.

        Args:
            message: Message to process
        """
        correlation_id = message.get("correlation_id")
        self.current_message = correlation_id

        log = logger.bind(
            worker_id=self.worker_id,
            correlation_id=correlation_id,
        )

        log.info("Processing message")

        start_time = time.time()

        try:
            # Update status to PROCESSING
            await self.cache.set(
                f"req:{correlation_id}:meta",
                {
                    "status": "PROCESSING",
                    "submitted_at": message.get("timestamp"),
                    "updated_at": datetime.utcnow().isoformat(),
                },
                ttl=3600,
            )

            # Process message
            result, status_code, response_headers = await self.processor.process(
                message["payload"],
                metadata=message.get("metadata"),
                headers=message.get("headers"),
            )

            processing_time = (time.time() - start_time) * 1000  # ms

            # Update status to COMPLETED
            await self.cache.set(
                f"req:{correlation_id}:meta",
                {
                    "status": "COMPLETED",
                    "submitted_at": message.get("timestamp"),
                    "updated_at": datetime.utcnow().isoformat(),
                },
                ttl=3600,
            )

            # Store response
            await self.cache.set(
                f"resp:{correlation_id}",
                {
                    "result": result,
                    "status_code": status_code,
                    "headers": response_headers,
                    "processing_time_ms": int(processing_time),
                    "completed_at": datetime.utcnow().isoformat(),
                },
                ttl=3600,
            )

            # Publish response to response queue
            await self.queue.publish(
                settings.queue.response_queue_name,
                {
                    "correlation_id": correlation_id,
                    "result": result,
                    "status_code": status_code,
                    "headers": response_headers,
                    "status": "COMPLETED",
                    "timestamp": datetime.utcnow().isoformat(),
                    "processing_time_ms": int(processing_time),
                },
            )

            log.info(
                "Message processed successfully",
                processing_time_ms=int(processing_time),
            )

            # Record metrics
            metrics.worker_processing_duration_seconds.labels(status="success").observe(
                processing_time / 1000
            )

        except RetryableError as e:
            log.warning("Retryable error occurred", error=str(e))

            retry_count = message.get("metadata", {}).get("retry_count", 0)

            if retry_count < settings.worker.max_retries:
                # Requeue with incremented retry count
                message["metadata"]["retry_count"] = retry_count + 1
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

    async def _send_to_dlq(self, message: Dict[str, Any], error: str) -> None:
        """
        Send failed message to dead letter queue.

        Args:
            message: Original message
            error: Error description
        """
        correlation_id = message.get("correlation_id")

        try:
            await self.queue.publish(
                settings.queue.dlq_name,
                {
                    **message,
                    "failed_at": datetime.utcnow().isoformat(),
                    "worker_id": self.worker_id,
                    "error": error,
                },
            )

            logger.info("Message sent to DLQ", correlation_id=correlation_id)
            metrics.queue_dlq_total.labels(reason="processing_failed").inc()

        except Exception as e:
            logger.error(
                "Failed to send message to DLQ",
                correlation_id=correlation_id,
                error=str(e),
            )

    async def _mark_failed(self, correlation_id: str, error: str) -> None:
        """
        Mark request as failed in cache.

        Args:
            correlation_id: Request correlation ID
            error: Error description
        """
        try:
            await self.cache.set(
                f"req:{correlation_id}:meta",
                {
                    "status": "FAILED",
                    "updated_at": datetime.utcnow().isoformat(),
                },
                ttl=3600,
            )

            await self.cache.set(
                f"resp:{correlation_id}",
                {
                    "error": error,
                    "completed_at": datetime.utcnow().isoformat(),
                },
                ttl=3600,
            )

        except Exception as e:
            logger.error(
                "Failed to mark request as failed",
                correlation_id=correlation_id,
                error=str(e),
            )

    def _handle_shutdown(self, signum, frame) -> None:
        """
        Handle shutdown signal.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info("Shutdown signal received", worker_id=self.worker_id, signal=signum)
        self.running = False

    async def shutdown(self) -> None:
        """Gracefully shutdown the worker."""
        logger.info("Shutting down worker", worker_id=self.worker_id)

        # Wait for current message to complete (with timeout)
        if self.current_message:
            logger.info("Waiting for current message to complete")
            for _ in range(30):  # 30 seconds max
                if not self.current_message:
                    break
                await asyncio.sleep(1)

        # Clear worker active metric
        metrics.worker_active.labels(worker_id=self.worker_id).set(0)

        await self.queue.disconnect()
        await self.cache.close()

        logger.info("Worker shutdown complete", worker_id=self.worker_id)


async def run_worker(worker_id: str):
    """
    Run a worker instance.

    Args:
        worker_id: Unique worker identifier
    """
    from openhqm.utils.logging import setup_logging

    setup_logging()

    logger.info("Initializing worker", worker_id=worker_id)

    # Create queue and cache
    queue = await create_queue()
    cache = await create_cache()

    # Create processor
    processor = MessageProcessor()

    try:
        # Create and start worker
        worker = Worker(worker_id, queue, cache, processor)
        await worker.start()
    finally:
        # Clean up processor
        await processor.close()


async def main():
    """Main entry point for worker."""
    import sys

    worker_id = sys.argv[1] if len(sys.argv) > 1 else "worker-1"
    await run_worker(worker_id)


if __name__ == "__main__":
    asyncio.run(main())
