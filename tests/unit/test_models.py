"""Unit tests for API models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from openhqm.api.models import (
    RequestMetadata,
    RequestStatus,
    ResultResponse,
    StatusResponse,
    SubmitRequest,
    SubmitResponse,
)


def test_submit_request_valid():
    """Test valid submit request."""
    request = SubmitRequest(
        payload={"operation": "test", "data": "value"},
        metadata=RequestMetadata(priority=5, timeout=300),
    )

    assert request.payload == {"operation": "test", "data": "value"}
    assert request.metadata.priority == 5
    assert request.metadata.timeout == 300


def test_submit_request_no_metadata():
    """Test submit request without metadata."""
    request = SubmitRequest(payload={"test": "data"})

    assert request.payload == {"test": "data"}
    assert request.metadata is None


def test_request_metadata_validation():
    """Test request metadata validation."""
    # Valid priority
    metadata = RequestMetadata(priority=5)
    assert metadata.priority == 5

    # Invalid priority (too high)
    with pytest.raises(ValidationError):
        RequestMetadata(priority=10)

    # Invalid priority (negative)
    with pytest.raises(ValidationError):
        RequestMetadata(priority=-1)

    # Invalid timeout (non-positive)
    with pytest.raises(ValidationError):
        RequestMetadata(timeout=0)


def test_submit_response():
    """Test submit response model."""
    response = SubmitResponse(
        correlation_id="test-123",
        status=RequestStatus.PENDING,
        submitted_at=datetime.utcnow(),
    )

    assert response.correlation_id == "test-123"
    assert response.status == RequestStatus.PENDING
    assert isinstance(response.submitted_at, datetime)


def test_status_response():
    """Test status response model."""
    now = datetime.utcnow()
    response = StatusResponse(
        correlation_id="test-123",
        status=RequestStatus.PROCESSING,
        submitted_at=now,
        updated_at=now,
    )

    assert response.correlation_id == "test-123"
    assert response.status == RequestStatus.PROCESSING


def test_result_response_completed():
    """Test result response for completed request."""
    response = ResultResponse(
        correlation_id="test-123",
        status=RequestStatus.COMPLETED,
        result={"output": "data"},
        processing_time_ms=1250,
        completed_at=datetime.utcnow(),
    )

    assert response.status == RequestStatus.COMPLETED
    assert response.result == {"output": "data"}
    assert response.processing_time_ms == 1250
    assert response.error is None


def test_result_response_failed():
    """Test result response for failed request."""
    response = ResultResponse(
        correlation_id="test-123",
        status=RequestStatus.FAILED,
        error="Processing failed",
        completed_at=datetime.utcnow(),
    )

    assert response.status == RequestStatus.FAILED
    assert response.error == "Processing failed"
    assert response.result is None


def test_request_status_enum():
    """Test request status enum values."""
    assert RequestStatus.PENDING.value == "PENDING"
    assert RequestStatus.PROCESSING.value == "PROCESSING"
    assert RequestStatus.COMPLETED.value == "COMPLETED"
    assert RequestStatus.FAILED.value == "FAILED"
    assert RequestStatus.TIMEOUT.value == "TIMEOUT"
