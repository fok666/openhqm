"""Unit tests for proxy processor."""

from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from openhqm.config.settings import EndpointConfig, settings
from openhqm.exceptions import ConfigurationError, ProcessingError
from openhqm.worker.processor import MessageProcessor


@pytest.fixture
def mock_endpoint_config():
    """Create a mock endpoint configuration."""
    return EndpointConfig(
        url="https://api.example.com/process",
        method="POST",
        timeout=300,
        auth_type="bearer",
        auth_token="test-token-123",
        headers={"X-Service": "openhqm"},
    )


@pytest.fixture
def mock_proxy_settings(mock_endpoint_config):
    """Create mock proxy settings."""
    with patch.object(settings, "proxy") as mock_proxy:
        mock_proxy.enabled = True
        mock_proxy.default_endpoint = "test-api"
        mock_proxy.endpoints = {"test-api": mock_endpoint_config}
        mock_proxy.forward_headers = ["Content-Type", "Authorization"]
        mock_proxy.strip_headers = ["Host", "Connection"]
        mock_proxy.max_response_size = 10 * 1024 * 1024
        yield mock_proxy


@pytest.mark.asyncio
async def test_processor_proxy_request_success(mock_proxy_settings):
    """Test successful proxy request."""
    processor = MessageProcessor()

    # Mock HTTP response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json", "X-Response-ID": "123"}
    mock_response.json = AsyncMock(return_value={"result": "success", "data": "processed"})

    # Mock async context manager
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    # session.request should return the context manager directly, not a coroutine
    mock_session.request = Mock(return_value=mock_context)

    # Make _get_session return mock_session properly
    async def mock_get_session():
        return mock_session

    with patch.object(processor, "_get_session", side_effect=mock_get_session):
        result, status_code, headers = await processor.process(
            payload={"operation": "test", "data": "hello"},
            metadata={"endpoint": "test-api"},
            headers={"Content-Type": "application/json"},
        )

    assert status_code == 200
    assert result == {"result": "success", "data": "processed"}
    assert "Content-Type" in headers

    await processor.close()


@pytest.mark.asyncio
async def test_processor_prepare_bearer_auth():
    """Test Bearer token authentication preparation."""
    processor = MessageProcessor()

    config = EndpointConfig(
        url="https://api.example.com",
        auth_type="bearer",
        auth_token="my-bearer-token",
    )

    headers = processor._prepare_auth_headers(config)

    assert headers["Authorization"] == "Bearer my-bearer-token"


@pytest.mark.asyncio
async def test_processor_prepare_api_key_auth():
    """Test API key authentication preparation."""
    processor = MessageProcessor()

    config = EndpointConfig(
        url="https://api.example.com",
        auth_type="api_key",
        auth_token="my-api-key",
        auth_header_name="X-API-Key",
    )

    headers = processor._prepare_auth_headers(config)

    assert headers["X-API-Key"] == "my-api-key"


@pytest.mark.asyncio
async def test_processor_prepare_basic_auth():
    """Test Basic authentication preparation."""
    processor = MessageProcessor()

    config = EndpointConfig(
        url="https://api.example.com",
        auth_type="basic",
        auth_username="user",
        auth_password="pass",
    )

    headers = processor._prepare_auth_headers(config)

    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_processor_prepare_custom_auth():
    """Test custom authentication preparation."""
    processor = MessageProcessor()

    config = EndpointConfig(
        url="https://api.example.com",
        auth_type="custom",
        auth_header_name="X-Custom-Token",
        auth_token="custom-token-value",
    )

    headers = processor._prepare_auth_headers(config)

    assert headers["X-Custom-Token"] == "custom-token-value"


@pytest.mark.asyncio
async def test_processor_merge_headers(mock_proxy_settings):
    """Test header merging with forwarding rules."""
    processor = MessageProcessor()

    config = EndpointConfig(
        url="https://api.example.com",
        headers={"X-Static": "static-value"},
        auth_type="bearer",
        auth_token="token123",
    )

    request_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer client-token",
        "Host": "original-host.com",
        "X-Custom": "custom-value",
    }

    merged = processor._merge_headers(config, request_headers)

    # Static header should be present
    assert merged["X-Static"] == "static-value"

    # Auth header from config should override (tokens are masked in logs)
    assert "Authorization" in merged
    assert merged["Authorization"].startswith("Bearer ")

    # Forwarded header should be present
    assert merged["Content-Type"] == "application/json"

    # Stripped header should not be present
    assert "Host" not in merged


@pytest.mark.asyncio
async def test_processor_endpoint_not_found():
    """Test error when endpoint is not found."""
    processor = MessageProcessor()

    with patch.object(settings, "proxy") as mock_proxy:
        mock_proxy.enabled = True
        mock_proxy.endpoints = {}
        mock_proxy.default_endpoint = None

        with pytest.raises(ConfigurationError, match="not found in configuration"):
            await processor.process(
                payload={"data": "test"},
                metadata={"endpoint": "non-existent"},
            )


@pytest.mark.asyncio
async def test_processor_proxy_disabled():
    """Test fallback to example processing when proxy mode is disabled."""
    processor = MessageProcessor()

    with patch.object(settings, "proxy") as mock_proxy:
        mock_proxy.enabled = False

        # Should fall back to example processing instead of raising error
        result, status, headers = await processor.process(
            payload={"operation": "echo", "data": "test"}
        )
        assert result["output"] == "test"
        assert "processed_at" in result
        assert status == 200


@pytest.mark.asyncio
async def test_processor_http_error(mock_proxy_settings):
    """Test handling of HTTP client errors."""
    processor = MessageProcessor()

    # Mock context manager that raises on enter
    mock_context = AsyncMock()
    mock_context.__aenter__.side_effect = aiohttp.ClientError("Connection failed")

    mock_session = AsyncMock()
    # session.request should return the context manager directly, not a coroutine
    mock_session.request = Mock(return_value=mock_context)

    # Make _get_session return mock_session properly
    async def mock_get_session():
        return mock_session

    with patch.object(processor, "_get_session", side_effect=mock_get_session):
        with pytest.raises(ProcessingError, match="Failed to proxy request"):
            await processor.process(
                payload={"data": "test"},
                metadata={"endpoint": "test-api"},
            )

    await processor.close()


@pytest.mark.asyncio
async def test_processor_method_override(mock_proxy_settings):
    """Test HTTP method override from metadata."""
    processor = MessageProcessor()

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json = AsyncMock(return_value={"status": "ok"})

    # Mock async context manager
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    # session.request should return the context manager directly, not a coroutine
    mock_session.request = Mock(return_value=mock_context)

    # Make _get_session return mock_session properly
    async def mock_get_session():
        return mock_session

    with patch.object(processor, "_get_session", side_effect=mock_get_session):
        await processor.process(
            payload={"data": "test"},
            metadata={"endpoint": "test-api", "method": "PUT"},
        )

        # Verify PUT method was used
        call_args = mock_session.request.call_args
        assert call_args[1]["method"] == "PUT"

    await processor.close()
