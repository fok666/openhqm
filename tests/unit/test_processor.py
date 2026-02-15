"""Unit tests for message processor."""

from unittest.mock import patch

import pytest

from openhqm.config.settings import settings
from openhqm.worker.processor import MessageProcessor


@pytest.fixture
def disable_proxy_mode():
    """Disable proxy mode for legacy processor tests."""
    with patch.object(settings, "proxy") as mock_proxy:
        mock_proxy.enabled = False
        yield mock_proxy


@pytest.mark.asyncio
async def test_processor_echo(disable_proxy_mode):
    """Test echo operation."""
    processor = MessageProcessor()

    result, status, headers = await processor.process({"operation": "echo", "data": "Hello World"})

    assert "output" in result
    assert result["output"] == "Hello World"
    assert "processed_at" in result
    assert status == 200


@pytest.mark.asyncio
async def test_processor_uppercase(disable_proxy_mode):
    """Test uppercase operation."""
    processor = MessageProcessor()

    result, status, headers = await processor.process(
        {"operation": "uppercase", "data": "hello world"}
    )

    assert result["output"] == "HELLO WORLD"
    assert status == 200


@pytest.mark.asyncio
async def test_processor_reverse(disable_proxy_mode):
    """Test reverse operation."""
    processor = MessageProcessor()

    result, status, headers = await processor.process({"operation": "reverse", "data": "hello"})

    assert result["output"] == "olleh"
    assert status == 200


@pytest.mark.asyncio
async def test_processor_unknown_operation(disable_proxy_mode):
    """Test unknown operation."""
    processor = MessageProcessor()

    result, status, headers = await processor.process({"operation": "unknown", "data": "test"})

    assert "Unknown operation" in result["output"]
    assert status == 200


@pytest.mark.asyncio
async def test_processor_error(disable_proxy_mode):
    """Test error handling."""
    processor = MessageProcessor()

    with pytest.raises(ValueError):
        await processor.process({"operation": "error", "data": "test"})
