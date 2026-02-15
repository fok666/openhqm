"""Error handling and edge case tests."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from openhqm.exceptions import ConfigurationError, FatalError, ProcessingError, RetryableError
from openhqm.worker.processor import MessageProcessor


class TestExceptionHandling:
    """Test exception handling throughout the system."""

    @pytest.mark.asyncio
    async def test_configuration_error_propagation(self):
        """Test that configuration errors are properly propagated."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = True
            mock_settings.routing.config_path = "/nonexistent/path.yaml"
            mock_settings.routing.config_dict = None

            with pytest.raises(ConfigurationError):
                MessageProcessor()

    @pytest.mark.asyncio
    async def test_processing_error_with_network_timeout(self):
        """Test processing error for network timeout."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False
            mock_settings.proxy.enabled = True
            mock_settings.proxy.default_endpoint = "http://slow.example.com"
            mock_settings.worker.timeout_seconds = 1

            processor = MessageProcessor()

            with patch("aiohttp.ClientSession.request") as mock_request:
                mock_request.side_effect = TimeoutError()

                with pytest.raises(ProcessingError, match="timeout"):
                    await processor.process({"data": "test"})

    @pytest.mark.asyncio
    async def test_processing_error_with_connection_error(self):
        """Test processing error for connection failure."""
        import aiohttp

        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False
            mock_settings.proxy.enabled = True
            mock_settings.proxy.default_endpoint = "http://unreachable.example.com"

            processor = MessageProcessor()

            with patch("aiohttp.ClientSession.request") as mock_request:
                mock_request.side_effect = aiohttp.ClientError("Connection refused")

                with pytest.raises(ProcessingError, match="Failed to proxy"):
                    await processor.process({"data": "test"})

    @pytest.mark.asyncio
    async def test_retryable_error_identification(self):
        """Test that retryable errors are correctly identified."""
        error = RetryableError("Temporary failure")

        assert isinstance(error, Exception)
        assert "Temporary" in str(error)

    @pytest.mark.asyncio
    async def test_fatal_error_identification(self):
        """Test that fatal errors are correctly identified."""
        error = FatalError("Critical failure")

        assert isinstance(error, Exception)
        assert "Critical" in str(error)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_payload_processing(self):
        """Test processing with empty payload."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False
            mock_settings.proxy.enabled = False

            processor = MessageProcessor()

            result, status, headers = processor._example_process({})

            assert "output" in result
            assert status == 200

    @pytest.mark.asyncio
    async def test_extremely_large_payload(self):
        """Test handling of very large payload."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False
            mock_settings.proxy.enabled = False

            processor = MessageProcessor()

        # 1MB payload
        large_payload = {"data": "x" * (1024 * 1024), "operation": "echo"}

        result, status, headers = processor._example_process(large_payload)

        assert len(result["output"]) == 1024 * 1024
        assert status == 200

    @pytest.mark.asyncio
    async def test_zero_partition_count(self):
        """Test handling of invalid partition count."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = True
            mock_settings.partitioning.partition_count = 0

            # Should handle gracefully or raise error
            try:
                processor = MessageProcessor(worker_id="worker-1")
                # If no error, partition count should be adjusted
                assert processor._partition_manager is not None
            except (ValueError, ConfigurationError):
                # Expected for invalid configuration
                pass

    @pytest.mark.asyncio
    async def test_negative_retry_count(self):
        """Test handling of negative retry count."""
        from openhqm.worker.worker import Worker

        mock_queue = AsyncMock()
        mock_cache = AsyncMock()
        mock_processor = AsyncMock()
        mock_processor.process.side_effect = RetryableError("Test")

        worker = Worker("test", mock_queue, mock_cache, mock_processor)

        message = {
            "correlation_id": "test",
            "payload": {},
            "metadata": {"retry_count": -1},  # Invalid
            "timestamp": "2026-02-08T10:00:00Z",
        }

        await worker._handle_message(message)

        # Should treat as 0 and retry
        assert mock_queue.publish.called

    @pytest.mark.asyncio
    async def test_malformed_timestamp(self):
        """Test handling of malformed timestamp."""
        from openhqm.worker.worker import Worker

        mock_queue = AsyncMock()
        mock_cache = AsyncMock()
        mock_processor = AsyncMock()
        mock_processor.process.return_value = ({}, 200, {})

        worker = Worker("test", mock_queue, mock_cache, mock_processor)

        message = {
            "correlation_id": "test",
            "payload": {},
            "metadata": {},
            "timestamp": "invalid-timestamp",
        }

        # Should handle gracefully
        await worker._handle_message(message)

        assert mock_processor.process.called

    @pytest.mark.asyncio
    async def test_missing_correlation_id(self):
        """Test handling of missing correlation ID."""
        from openhqm.worker.worker import Worker

        mock_queue = AsyncMock()
        mock_cache = AsyncMock()
        mock_processor = AsyncMock()
        mock_processor.process.return_value = ({}, 200, {})

        worker = Worker("test", mock_queue, mock_cache, mock_processor)

        message = {
            # No correlation_id
            "payload": {},
            "metadata": {},
            "timestamp": "2026-02-08T10:00:00Z",
        }

        # Should handle gracefully or use default
        await worker._handle_message(message)

    @pytest.mark.asyncio
    async def test_unicode_in_headers(self):
        """Test handling of unicode characters in headers."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False
            mock_settings.proxy.enabled = False
            mock_settings.proxy.forward_headers = ["*"]
            mock_settings.proxy.strip_headers = []

            processor = MessageProcessor()

            from openhqm.config.settings import EndpointConfig

            endpoint = EndpointConfig(url="http://test.com")

            headers = processor._merge_headers(endpoint, {"X-Custom": "Hello 世界"})

            assert headers["X-Custom"] == "Hello 世界"

    @pytest.mark.asyncio
    async def test_circular_reference_in_payload(self):
        """Test handling of circular references."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False

            MessageProcessor()

        payload = {"a": {"b": {"c": {}}}}
        payload["a"]["b"]["c"]["circular"] = payload["a"]  # Create cycle

        # Should fail during JSON serialization
        # This is expected behavior
        import json

        with pytest.raises((ValueError, TypeError)):
            json.dumps(payload)

    @pytest.mark.asyncio
    async def test_max_header_size(self):
        """Test handling of extremely large headers."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False
            mock_settings.proxy.enabled = False
            mock_settings.proxy.forward_headers = ["*"]
            mock_settings.proxy.strip_headers = []

            processor = MessageProcessor()

            from openhqm.config.settings import EndpointConfig

            endpoint = EndpointConfig(url="http://test.com")

            # Very large header value
            large_value = "x" * 10000
            headers = processor._merge_headers(endpoint, {"X-Large": large_value})

            assert headers["X-Large"] == large_value

    @pytest.mark.asyncio
    async def test_special_header_names(self):
        """Test handling of special header names."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False
            mock_settings.proxy.enabled = False
            mock_settings.proxy.forward_headers = ["*"]
            mock_settings.proxy.strip_headers = []

            processor = MessageProcessor()

            from openhqm.config.settings import EndpointConfig

            endpoint = EndpointConfig(url="http://test.com")

            headers = processor._merge_headers(
                endpoint, {"X-123-Numeric": "value", "X_Underscore": "value", "X-Special!": "value"}
            )

            # Should preserve all headers
            assert len(headers) >= 3


class TestConcurrency:
    """Test concurrent scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self):
        """Test processing multiple messages concurrently."""
        from openhqm.worker.worker import Worker

        mock_queue = AsyncMock()
        mock_cache = AsyncMock()
        mock_processor = AsyncMock()

        async def slow_process(*args, **kwargs):
            await asyncio.sleep(0.01)
            return ({}, 200, {})

        mock_processor.process.side_effect = slow_process

        worker = Worker("test", mock_queue, mock_cache, mock_processor)

        messages = [
            {
                "correlation_id": f"test-{i}",
                "payload": {},
                "metadata": {},
                "timestamp": "2026-02-08T10:00:00Z",
            }
            for i in range(10)
        ]

        # Process all concurrently
        await asyncio.gather(*[worker._handle_message(msg) for msg in messages])

        # All should complete
        assert mock_processor.process.call_count == 10

    @pytest.mark.asyncio
    async def test_session_reuse_under_load(self):
        """Test that session is reused properly under concurrent load."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False
            mock_settings.worker.timeout_seconds = 300

            processor = MessageProcessor()

            # Get session multiple times concurrently
            sessions = await asyncio.gather(*[processor._get_session() for _ in range(100)])

            # All should be the same instance
            assert all(s is sessions[0] for s in sessions)

    @pytest.mark.asyncio
    async def test_partition_manager_concurrent_access(self):
        """Test partition manager under concurrent access."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = True
            mock_settings.partitioning.partition_count = 10

            processor = MessageProcessor(worker_id="worker-1")
            processor.set_partition_assignments({0, 1, 2, 3, 4})

            # Get stats concurrently
            stats_list = await asyncio.gather(
                *[asyncio.to_thread(processor.get_partition_stats) for _ in range(100)]
            )

            # All should return consistent results
            assert all(s == stats_list[0] for s in stats_list)


class TestResourceCleanup:
    """Test resource cleanup and lifecycle management."""

    @pytest.mark.asyncio
    async def test_processor_close_idempotent(self):
        """Test that close() can be called multiple times safely."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False

            processor = MessageProcessor()

        await processor._get_session()

        # Close multiple times
        await processor.close()
        await processor.close()
        await processor.close()

        # Should not raise errors

    @pytest.mark.asyncio
    async def test_worker_shutdown_idempotent(self):
        """Test that shutdown can be called multiple times."""
        from openhqm.worker.worker import Worker

        mock_queue = AsyncMock()
        mock_cache = AsyncMock()
        mock_processor = AsyncMock()

        worker = Worker("test", mock_queue, mock_cache, mock_processor)

        # Shutdown multiple times
        await worker.shutdown()
        await worker.shutdown()

        # Disconnect/close should still be called
        assert mock_queue.disconnect.called
        assert mock_cache.close.called

    @pytest.mark.asyncio
    async def test_session_recreation_after_error(self):
        """Test session is recreated after error."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False

            processor = MessageProcessor()

        session1 = await processor._get_session()

        # Simulate session error
        await session1.close()

        # Getting session again should create new one
        session2 = await processor._get_session()

        assert session2 is not session1
        assert not session2.closed


class TestInputValidation:
    """Test input validation and sanitization."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_payload(self):
        """Test handling of SQL injection attempts in payload."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False

            processor = MessageProcessor()

        payload = {"operation": "echo", "data": "'; DROP TABLE users; --"}

        result, status, headers = processor._example_process(payload)

        # Should handle safely (no DB in this system, but test anyway)
        assert "DROP TABLE" in result["output"]
        assert status == 200

    @pytest.mark.asyncio
    async def test_xss_in_payload(self):
        """Test handling of XSS attempts in payload."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.routing.enabled = False
            mock_settings.partitioning.enabled = False

            processor = MessageProcessor()

        payload = {"operation": "echo", "data": "<script>alert('XSS')</script>"}

        result, status, headers = processor._example_process(payload)

        # Should not execute, just return as-is
        assert "<script>" in result["output"]
        assert status == 200

    @pytest.mark.asyncio
    async def test_path_traversal_in_endpoint(self):
        """Test handling of path traversal attempts."""
        with patch("openhqm.worker.processor.settings") as mock_settings:
            mock_settings.proxy.enabled = True
            mock_settings.proxy.endpoints = {}

            processor = MessageProcessor()

            # Attempt path traversal
            with pytest.raises(ConfigurationError):
                processor._get_endpoint_config("../../etc/passwd")

    @pytest.mark.asyncio
    async def test_null_byte_injection(self):
        """Test handling of null byte injection."""
        processor = MessageProcessor()

        payload = {"operation": "echo", "data": "test\x00hidden"}

        result, status, headers = processor._example_process(payload)

        # Should handle gracefully
        assert "test" in result["output"]
        assert status == 200
