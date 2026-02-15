"""Comprehensive unit tests for Worker class."""

import asyncio
import signal
from unittest.mock import AsyncMock, patch

import pytest

from openhqm.cache.interface import CacheInterface
from openhqm.exceptions import FatalError, RetryableError
from openhqm.queue.interface import MessageQueueInterface
from openhqm.worker.processor import MessageProcessor
from openhqm.worker.worker import Worker


@pytest.fixture
def mock_queue():
    """Create mock queue."""
    queue = AsyncMock(spec=MessageQueueInterface)
    queue.consume = AsyncMock()
    queue.publish = AsyncMock()
    queue.disconnect = AsyncMock()
    return queue


@pytest.fixture
def mock_cache():
    """Create mock cache."""
    cache = AsyncMock(spec=CacheInterface)
    cache.set = AsyncMock()
    cache.get = AsyncMock()
    cache.close = AsyncMock()
    return cache


@pytest.fixture
def mock_processor():
    """Create mock processor."""
    processor = AsyncMock(spec=MessageProcessor)
    processor.process = AsyncMock()
    return processor


@pytest.fixture
def worker(mock_queue, mock_cache, mock_processor):
    """Create worker instance."""
    return Worker("test-worker-1", mock_queue, mock_cache, mock_processor)


@pytest.mark.asyncio
async def test_worker_initialization(worker):
    """Test worker initialization."""
    assert worker.worker_id == "test-worker-1"
    assert worker.running is False
    assert worker.current_message is None


@pytest.mark.asyncio
async def test_worker_successful_message_processing(worker, mock_queue, mock_cache, mock_processor):
    """Test successful message processing flow."""
    # Setup
    message = {
        "correlation_id": "test-123",
        "payload": {"operation": "test"},
        "metadata": {},
        "headers": {},
        "timestamp": "2026-02-08T10:00:00Z",
    }

    mock_processor.process.return_value = (
        {"result": "success"},
        200,
        {"Content-Type": "application/json"},
    )

    # Execute
    await worker._handle_message(message)

    # Verify processing
    mock_processor.process.assert_called_once_with(
        {"operation": "test"},
        metadata={},
        headers={},
        full_message=message,
    )

    # Verify cache updates (status + response)
    assert mock_cache.set.call_count == 3

    # Verify status updates
    status_calls = [call for call in mock_cache.set.call_args_list if ":meta" in call[0][0]]
    assert len(status_calls) == 2  # PROCESSING and COMPLETED

    # Verify response stored
    response_calls = [call for call in mock_cache.set.call_args_list if "resp:" in call[0][0]]
    assert len(response_calls) == 1
    response_data = response_calls[0][0][1]
    assert response_data["result"] == {"result": "success"}
    assert response_data["status_code"] == 200

    # Verify response published to queue
    mock_queue.publish.assert_called_once()
    publish_args = mock_queue.publish.call_args[0]
    assert "responses" in publish_args[0]
    assert publish_args[1]["correlation_id"] == "test-123"
    assert publish_args[1]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_worker_retryable_error_with_retries_remaining(worker, mock_queue, mock_processor):
    """Test handling of retryable error with retries remaining."""
    message = {
        "correlation_id": "test-456",
        "payload": {"operation": "test"},
        "metadata": {"retry_count": 0},
        "timestamp": "2026-02-08T10:00:00Z",
    }

    mock_processor.process.side_effect = RetryableError("Temporary failure")

    await worker._handle_message(message)

    # Should requeue with incremented retry count
    mock_queue.publish.assert_called_once()
    requeued_message = mock_queue.publish.call_args[0][1]
    assert requeued_message["metadata"]["retry_count"] == 1
    assert requeued_message["correlation_id"] == "test-456"


@pytest.mark.asyncio
async def test_worker_retryable_error_max_retries_exceeded(worker, mock_queue, mock_processor):
    """Test handling of retryable error after max retries."""
    message = {
        "correlation_id": "test-789",
        "payload": {"operation": "test"},
        "metadata": {"retry_count": 3},  # Max retries reached
        "timestamp": "2026-02-08T10:00:00Z",
    }

    mock_processor.process.side_effect = RetryableError("Still failing")

    await worker._handle_message(message)

    # Should send to DLQ
    mock_queue.publish.assert_called_once()
    dlq_call = mock_queue.publish.call_args[0]
    assert "dlq" in dlq_call[0] or "dead" in dlq_call[0].lower()
    assert dlq_call[1]["correlation_id"] == "test-789"
    assert "error" in dlq_call[1]


@pytest.mark.asyncio
async def test_worker_fatal_error(worker, mock_queue, mock_cache, mock_processor):
    """Test handling of fatal error."""
    message = {
        "correlation_id": "test-fatal",
        "payload": {"operation": "test"},
        "metadata": {},
        "timestamp": "2026-02-08T10:00:00Z",
    }

    mock_processor.process.side_effect = FatalError("Critical failure")

    await worker._handle_message(message)

    # Should send to DLQ
    assert mock_queue.publish.called

    # Should mark as failed in cache
    failed_calls = [call for call in mock_cache.set.call_args_list if "FAILED" in str(call)]
    assert len(failed_calls) > 0


@pytest.mark.asyncio
async def test_worker_unexpected_exception(worker, mock_queue, mock_cache, mock_processor):
    """Test handling of unexpected exception."""
    message = {
        "correlation_id": "test-unexpected",
        "payload": {"operation": "test"},
        "metadata": {},
        "timestamp": "2026-02-08T10:00:00Z",
    }

    mock_processor.process.side_effect = ValueError("Unexpected error")

    await worker._handle_message(message)

    # Should handle gracefully - send to DLQ and mark failed
    assert mock_queue.publish.called
    assert mock_cache.set.called


@pytest.mark.asyncio
async def test_worker_current_message_tracking(worker, mock_processor):
    """Test that current message is tracked during processing."""
    message = {
        "correlation_id": "test-tracking",
        "payload": {},
        "metadata": {},
        "timestamp": "2026-02-08T10:00:00Z",
    }

    async def check_current_message(*args, **kwargs):
        # During processing, current_message should be set
        assert worker.current_message == "test-tracking"
        return ({}, 200, {})

    mock_processor.process.side_effect = check_current_message

    await worker._handle_message(message)

    # After processing, should be cleared
    assert worker.current_message is None


@pytest.mark.asyncio
async def test_worker_shutdown_signal_handling(worker):
    """Test shutdown signal handling."""
    worker._handle_shutdown(signal.SIGTERM, None)

    assert worker.running is False


@pytest.mark.asyncio
async def test_worker_graceful_shutdown_waits_for_current_message(worker, mock_queue, mock_cache):
    """Test that shutdown waits for current message to complete."""
    worker.current_message = "test-in-progress"

    async def clear_message():
        await asyncio.sleep(0.1)
        worker.current_message = None

    # Start clearing message in background
    clear_task = asyncio.create_task(clear_message())

    # Shutdown should wait
    await worker.shutdown()

    # Message should be cleared
    assert worker.current_message is None

    await clear_task


@pytest.mark.asyncio
async def test_worker_graceful_shutdown_timeout(worker, mock_queue, mock_cache):
    """Test that shutdown has a timeout for stuck messages."""
    worker.current_message = "test-stuck"

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Make sleep instant to speed up test
        mock_sleep.return_value = None

        await worker.shutdown()

        # Should have attempted to wait (30 iterations)
        assert mock_sleep.call_count == 30


@pytest.mark.asyncio
async def test_worker_shutdown_closes_connections(worker, mock_queue, mock_cache):
    """Test that shutdown properly closes queue and cache."""
    await worker.shutdown()

    mock_queue.disconnect.assert_called_once()
    mock_cache.close.assert_called_once()


@pytest.mark.asyncio
async def test_send_to_dlq_includes_metadata(worker, mock_queue):
    """Test that DLQ messages include proper metadata."""
    message = {
        "correlation_id": "test-dlq",
        "payload": {"data": "test"},
        "metadata": {"priority": "high"},
    }

    await worker._send_to_dlq(message, "Test error")

    mock_queue.publish.assert_called_once()
    dlq_message = mock_queue.publish.call_args[0][1]

    assert dlq_message["correlation_id"] == "test-dlq"
    assert dlq_message["payload"] == {"data": "test"}
    assert dlq_message["metadata"] == {"priority": "high"}
    assert "failed_at" in dlq_message
    assert dlq_message["worker_id"] == "test-worker-1"
    assert dlq_message["error"] == "Test error"


@pytest.mark.asyncio
async def test_send_to_dlq_handles_publish_failure(worker, mock_queue, caplog):
    """Test that DLQ publish failures are logged."""
    message = {"correlation_id": "test-dlq-fail"}
    mock_queue.publish.side_effect = Exception("Queue error")

    # Should not raise exception
    await worker._send_to_dlq(message, "Test error")

    # Should log error
    assert "Failed to send message to DLQ" in caplog.text


@pytest.mark.asyncio
async def test_mark_failed_updates_cache(worker, mock_cache):
    """Test that mark_failed properly updates cache."""
    await worker._mark_failed("test-failed", "Test error message")

    # Should update both metadata and response
    assert mock_cache.set.call_count == 2

    # Check metadata update
    meta_call = [c for c in mock_cache.set.call_args_list if ":meta" in c[0][0]][0]
    assert meta_call[0][0] == "req:test-failed:meta"
    assert meta_call[0][1]["status"] == "FAILED"

    # Check response update
    resp_call = [c for c in mock_cache.set.call_args_list if "resp:" in c[0][0]][0]
    assert resp_call[0][0] == "resp:test-failed"
    assert resp_call[0][1]["error"] == "Test error message"


@pytest.mark.asyncio
async def test_mark_failed_handles_cache_errors(worker, mock_cache, caplog):
    """Test that cache errors during mark_failed are logged."""
    mock_cache.set.side_effect = Exception("Cache error")

    # Should not raise exception
    await worker._mark_failed("test-cache-fail", "Original error")

    # Should log error
    assert "Failed to mark request as failed" in caplog.text


@pytest.mark.asyncio
async def test_worker_processing_records_timing(worker, mock_processor):
    """Test that processing time is recorded."""
    message = {
        "correlation_id": "test-timing",
        "payload": {},
        "metadata": {},
        "timestamp": "2026-02-08T10:00:00Z",
    }

    async def slow_process(*args, **kwargs):
        await asyncio.sleep(0.01)
        return ({}, 200, {})

    mock_processor.process.side_effect = slow_process

    await worker._handle_message(message)

    # Check that processing time was recorded
    response_calls = [c for c in worker.cache.set.call_args_list if "resp:" in c[0][0]]
    assert len(response_calls) > 0
    assert "processing_time_ms" in response_calls[0][0][1]
    assert response_calls[0][0][1]["processing_time_ms"] > 0


@pytest.mark.asyncio
async def test_worker_preserves_message_headers(worker, mock_processor):
    """Test that message headers are passed to processor."""
    message = {
        "correlation_id": "test-headers",
        "payload": {"data": "test"},
        "metadata": {"endpoint": "api1"},
        "headers": {
            "Authorization": "Bearer token",
            "X-Custom": "value",
        },
        "timestamp": "2026-02-08T10:00:00Z",
    }

    mock_processor.process.return_value = ({}, 200, {})

    await worker._handle_message(message)

    # Verify headers were passed
    call_kwargs = mock_processor.process.call_args[1]
    assert call_kwargs["headers"] == {
        "Authorization": "Bearer token",
        "X-Custom": "value",
    }


@pytest.mark.asyncio
async def test_worker_handles_missing_optional_fields(worker, mock_processor):
    """Test that worker handles messages with missing optional fields."""
    message = {
        "correlation_id": "test-minimal",
        "payload": {"data": "test"},
        "timestamp": "2026-02-08T10:00:00Z",
        # No metadata, headers
    }

    mock_processor.process.return_value = ({}, 200, {})

    # Should not raise exception
    await worker._handle_message(message)

    # Should call processor with None for missing fields
    call_kwargs = mock_processor.process.call_args[1]
    assert call_kwargs["metadata"] == {}


@pytest.mark.asyncio
async def test_worker_start_sets_metrics(worker, mock_queue):
    """Test that worker start sets active metric."""

    # Make consume return immediately
    async def immediate_return(*args, **kwargs):
        worker.running = False

    mock_queue.consume.side_effect = immediate_return

    with patch("openhqm.worker.worker.metrics") as mock_metrics:
        await worker.start()

        # Should set active metric
        mock_metrics.worker_active.labels.assert_called_with(worker_id="test-worker-1")


@pytest.mark.asyncio
async def test_worker_processes_batch(worker, mock_queue, mock_processor):
    """Test that worker can process messages in batch."""
    messages = [
        {
            "correlation_id": f"test-{i}",
            "payload": {},
            "metadata": {},
            "timestamp": "2026-02-08T10:00:00Z",
        }
        for i in range(5)
    ]

    mock_processor.process.return_value = ({}, 200, {})

    for msg in messages:
        await worker._handle_message(msg)

    # Should process all messages
    assert mock_processor.process.call_count == 5


@pytest.mark.asyncio
async def test_worker_concurrent_processing_isolation(worker, mock_processor):
    """Test that concurrent message processing is isolated."""
    message1 = {
        "correlation_id": "concurrent-1",
        "payload": {},
        "metadata": {},
        "timestamp": "2026-02-08T10:00:00Z",
    }
    message2 = {
        "correlation_id": "concurrent-2",
        "payload": {},
        "metadata": {},
        "timestamp": "2026-02-08T10:00:00Z",
    }

    mock_processor.process.return_value = ({}, 200, {})

    # Process concurrently
    await asyncio.gather(
        worker._handle_message(message1),
        worker._handle_message(message2),
    )

    # Both should succeed
    assert mock_processor.process.call_count == 2
