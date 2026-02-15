"""Comprehensive tests for MessageProcessor including routing and partitioning."""

from unittest.mock import patch

import pytest

from openhqm.config.settings import EndpointConfig
from openhqm.exceptions import ConfigurationError
from openhqm.worker.processor import MessageProcessor


@pytest.fixture
def processor():
    """Create processor instance."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.routing.enabled = False
        mock_settings.partitioning.enabled = False
        mock_settings.worker.timeout_seconds = 300
        mock_settings.proxy.enabled = True
        mock_settings.proxy.default_endpoint = "http://test.example.com"
        mock_settings.proxy.forward_headers = ["*"]
        mock_settings.proxy.strip_headers = []
        mock_settings.proxy.endpoints = {}

        proc = MessageProcessor()
        yield proc


@pytest.mark.asyncio
async def test_processor_initialization_without_routing():
    """Test processor initialization without routing."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.routing.enabled = False
        mock_settings.partitioning.enabled = False

        processor = MessageProcessor()

        assert processor._session is None
        assert processor._routing_engine is None
        assert processor._partition_manager is None


@pytest.mark.asyncio
async def test_processor_initialization_with_routing():
    """Test processor initialization with routing enabled."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.routing.enabled = True
        mock_settings.routing.config_dict = {
            "version": "1.0",
            "routes": [
                {
                    "name": "test-route",
                    "is_default": True,
                    "endpoint": "test-endpoint",
                    "transform_type": "passthrough",
                }
            ],
        }
        mock_settings.partitioning.enabled = False

        processor = MessageProcessor()

        assert processor._routing_engine is not None


@pytest.mark.asyncio
async def test_processor_initialization_with_partitioning():
    """Test processor initialization with partitioning enabled."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.routing.enabled = False
        mock_settings.partitioning.enabled = True
        mock_settings.partitioning.partition_count = 10
        mock_settings.partitioning.strategy = "hash"

        processor = MessageProcessor(worker_id="worker-1")

        assert processor._partition_manager is not None


@pytest.mark.asyncio
async def test_processor_close_cleanup():
    """Test that close properly cleans up resources."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.routing.enabled = False
        mock_settings.partitioning.enabled = True
        mock_settings.partitioning.partition_count = 10

        processor = MessageProcessor(worker_id="worker-1")

        # Create session
        await processor._get_session()
        assert processor._session is not None

        # Close should cleanup
        await processor.close()
        assert processor._session.closed


@pytest.mark.asyncio
async def test_prepare_auth_headers_bearer():
    """Test bearer token authentication."""
    processor = MessageProcessor()

    endpoint = EndpointConfig(
        url="http://test.com", auth_type="bearer", auth_token="test-token-123"
    )

    headers = processor._prepare_auth_headers(endpoint)

    assert headers["Authorization"] == "Bearer test-token-123"


@pytest.mark.asyncio
async def test_prepare_auth_headers_api_key():
    """Test API key authentication."""
    processor = MessageProcessor()

    endpoint = EndpointConfig(
        url="http://test.com",
        auth_type="api_key",
        auth_token="api-key-456",
        auth_header_name="X-API-Key",
    )

    headers = processor._prepare_auth_headers(endpoint)

    assert headers["X-API-Key"] == "api-key-456"


@pytest.mark.asyncio
async def test_prepare_auth_headers_api_key_default_header():
    """Test API key with default header name."""
    processor = MessageProcessor()

    endpoint = EndpointConfig(url="http://test.com", auth_type="api_key", auth_token="api-key-789")

    headers = processor._prepare_auth_headers(endpoint)

    assert headers["X-API-Key"] == "api-key-789"


@pytest.mark.asyncio
async def test_prepare_auth_headers_basic():
    """Test basic authentication."""
    processor = MessageProcessor()

    endpoint = EndpointConfig(
        url="http://test.com", auth_type="basic", auth_username="user", auth_password="pass"
    )

    headers = processor._prepare_auth_headers(endpoint)

    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_prepare_auth_headers_custom():
    """Test custom authentication."""
    processor = MessageProcessor()

    endpoint = EndpointConfig(
        url="http://test.com",
        auth_type="custom",
        auth_header_name="X-Custom-Auth",
        auth_token="custom-value",
    )

    headers = processor._prepare_auth_headers(endpoint)

    assert headers["X-Custom-Auth"] == "custom-value"


@pytest.mark.asyncio
async def test_prepare_auth_headers_none():
    """Test no authentication."""
    processor = MessageProcessor()

    endpoint = EndpointConfig(url="http://test.com")

    headers = processor._prepare_auth_headers(endpoint)

    assert headers == {}


@pytest.mark.asyncio
async def test_merge_headers_with_config_headers():
    """Test merging static config headers."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.forward_headers = ["*"]
        mock_settings.proxy.strip_headers = []

        processor = MessageProcessor()

        endpoint = EndpointConfig(url="http://test.com", headers={"X-Static": "static-value"})

        result = processor._merge_headers(endpoint)

        assert result["X-Static"] == "static-value"


@pytest.mark.asyncio
async def test_merge_headers_with_forwarded_headers():
    """Test forwarding request headers."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.forward_headers = ["*"]
        mock_settings.proxy.strip_headers = []

        processor = MessageProcessor()

        endpoint = EndpointConfig(url="http://test.com")
        request_headers = {"User-Agent": "test-agent", "X-Request-ID": "req-123"}

        result = processor._merge_headers(endpoint, request_headers)

        assert result["User-Agent"] == "test-agent"
        assert result["X-Request-ID"] == "req-123"


@pytest.mark.asyncio
async def test_merge_headers_strips_blacklisted():
    """Test stripping blacklisted headers."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.forward_headers = ["*"]
        mock_settings.proxy.strip_headers = ["Host", "Connection"]

        processor = MessageProcessor()

        endpoint = EndpointConfig(url="http://test.com")
        request_headers = {"Host": "old-host.com", "Connection": "keep-alive", "User-Agent": "test"}

        result = processor._merge_headers(endpoint, request_headers)

        assert "Host" not in result
        assert "Connection" not in result
        assert result["User-Agent"] == "test"


@pytest.mark.asyncio
async def test_merge_headers_auth_override_precedence():
    """Test that auth headers override forwarded headers."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.forward_headers = ["*"]
        mock_settings.proxy.strip_headers = []

        processor = MessageProcessor()

        endpoint = EndpointConfig(
            url="http://test.com", auth_type="bearer", auth_token="endpoint-token"
        )
        request_headers = {"Authorization": "Bearer client-token"}

        result = processor._merge_headers(endpoint, request_headers)

        # Endpoint auth should take precedence
        assert result["Authorization"] == "Bearer endpoint-token"


@pytest.mark.asyncio
async def test_get_endpoint_config_named_endpoint():
    """Test getting named endpoint configuration."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.enabled = True
        mock_settings.proxy.endpoints = {
            "api1": EndpointConfig(url="http://api1.com"),
            "api2": EndpointConfig(url="http://api2.com"),
        }

        processor = MessageProcessor()

        config = processor._get_endpoint_config("api1")

        assert config.url == "http://api1.com"


@pytest.mark.asyncio
async def test_get_endpoint_config_unknown_endpoint():
    """Test error for unknown endpoint."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.enabled = True
        mock_settings.proxy.endpoints = {}

        processor = MessageProcessor()

        with pytest.raises(ConfigurationError, match="not found"):
            processor._get_endpoint_config("unknown")


@pytest.mark.asyncio
async def test_get_endpoint_config_default_endpoint_named():
    """Test using default endpoint from named endpoints."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.enabled = True
        mock_settings.proxy.default_endpoint = "api1"
        mock_settings.proxy.endpoints = {
            "api1": EndpointConfig(url="http://api1.com"),
        }

        processor = MessageProcessor()

        config = processor._get_endpoint_config()

        assert config.url == "http://api1.com"


@pytest.mark.asyncio
async def test_get_endpoint_config_default_endpoint_url():
    """Test using default endpoint as direct URL."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.enabled = True
        mock_settings.proxy.default_endpoint = "http://default.com"
        mock_settings.proxy.endpoints = {}

        processor = MessageProcessor()

        config = processor._get_endpoint_config()

        assert config.url == "http://default.com"


@pytest.mark.asyncio
async def test_get_endpoint_config_proxy_disabled():
    """Test that proxy disabled returns None."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.proxy.enabled = False

        processor = MessageProcessor()

        config = processor._get_endpoint_config()

        assert config is None


@pytest.mark.asyncio
async def test_set_partition_assignments():
    """Test setting partition assignments."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.routing.enabled = False
        mock_settings.partitioning.enabled = True
        mock_settings.partitioning.partition_count = 10

        processor = MessageProcessor(worker_id="worker-1")

        partitions = {0, 3, 6, 9}
        processor.set_partition_assignments(partitions)

        stats = processor.get_partition_stats()
        assert stats["assigned_partitions"] == sorted(partitions)


@pytest.mark.asyncio
async def test_get_partition_stats_disabled():
    """Test partition stats when partitioning is disabled."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.routing.enabled = False
        mock_settings.partitioning.enabled = False

        processor = MessageProcessor()

        stats = processor.get_partition_stats()

        assert stats == {"partitioning_enabled": False}


@pytest.mark.asyncio
async def test_process_with_partition_filtering():
    """Test that messages are filtered by partition."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.routing.enabled = False
        mock_settings.partitioning.enabled = True
        mock_settings.partitioning.partition_count = 10
        mock_settings.partitioning.partition_key_field = "metadata.session_id"
        mock_settings.proxy.enabled = False

        processor = MessageProcessor(worker_id="worker-1")
        processor.set_partition_assignments({0, 1, 2})

        # Message that hashes to partition not assigned to this worker
        full_message = {
            "correlation_id": "test-123",
            "metadata": {"session_id": "different-session"},
            "payload": {"data": "test"},
        }

        result, status, headers = await processor.process(
            payload={"data": "test"}, full_message=full_message
        )

        # Should skip message
        if result.get("skipped"):
            assert result["reason"] == "partition_not_assigned"
            assert status == 200


@pytest.mark.asyncio
async def test_example_process_echo():
    """Test example echo operation."""
    processor = MessageProcessor()

    result = processor._example_process({"operation": "echo", "data": "hello"})

    assert result["output"] == "hello"
    assert "processed_at" in result


@pytest.mark.asyncio
async def test_example_process_uppercase():
    """Test example uppercase operation."""
    processor = MessageProcessor()

    result = processor._example_process({"operation": "uppercase", "data": "hello"})

    assert result["output"] == "HELLO"


@pytest.mark.asyncio
async def test_example_process_reverse():
    """Test example reverse operation."""
    processor = MessageProcessor()

    result = processor._example_process({"operation": "reverse", "data": "hello"})

    assert result["output"] == "olleh"


@pytest.mark.asyncio
async def test_example_process_error():
    """Test example error operation."""
    processor = MessageProcessor()

    with pytest.raises(ValueError, match="Test error"):
        processor._example_process({"operation": "error"})


@pytest.mark.asyncio
async def test_example_process_unknown():
    """Test example unknown operation."""
    processor = MessageProcessor()

    result = processor._example_process({"operation": "unknown", "data": "test"})

    assert "Unknown operation" in result["output"]


@pytest.mark.asyncio
async def test_session_management():
    """Test that session is created and reused."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.worker.timeout_seconds = 300

        processor = MessageProcessor()

        session1 = await processor._get_session()
        session2 = await processor._get_session()

        # Should reuse same session
        assert session1 is session2


@pytest.mark.asyncio
async def test_session_recreation_after_close():
    """Test that session is recreated after close."""
    with patch("openhqm.worker.processor.settings") as mock_settings:
        mock_settings.worker.timeout_seconds = 300

        processor = MessageProcessor()

        session1 = await processor._get_session()
        await session1.close()

        session2 = await processor._get_session()

        # Should create new session
        assert session1 is not session2
        assert not session1.closed
        assert not session2.closed
