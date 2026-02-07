"""Unit tests for message processor."""

import pytest

from openhqm.worker.processor import MessageProcessor


@pytest.mark.asyncio
async def test_processor_echo():
    """Test echo operation."""
    processor = MessageProcessor()

    result = await processor.process({
        "operation": "echo",
        "data": "Hello World"
    })

    assert "output" in result
    assert result["output"] == "Hello World"
    assert "processed_at" in result


@pytest.mark.asyncio
async def test_processor_uppercase():
    """Test uppercase operation."""
    processor = MessageProcessor()

    result = await processor.process({
        "operation": "uppercase",
        "data": "hello world"
    })

    assert result["output"] == "HELLO WORLD"


@pytest.mark.asyncio
async def test_processor_reverse():
    """Test reverse operation."""
    processor = MessageProcessor()

    result = await processor.process({
        "operation": "reverse",
        "data": "hello"
    })

    assert result["output"] == "olleh"


@pytest.mark.asyncio
async def test_processor_unknown_operation():
    """Test unknown operation."""
    processor = MessageProcessor()

    result = await processor.process({
        "operation": "unknown",
        "data": "test"
    })

    assert "Unknown operation" in result["output"]


@pytest.mark.asyncio
async def test_processor_error():
    """Test error handling."""
    processor = MessageProcessor()

    with pytest.raises(ValueError):
        await processor.process({
            "operation": "error",
            "data": "test"
        })
