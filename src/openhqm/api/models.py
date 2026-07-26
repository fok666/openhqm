"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RequestStatus(StrEnum):
    """Request processing status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SubmitRequest(BaseModel):
    """A request to enqueue."""

    payload: dict[str, Any] = Field(..., description="Body forwarded to the backend")
    headers: dict[str, str] | None = Field(default=None, description="HTTP headers to forward")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Passed through to the worker; 'method' overrides the backend HTTP method",
    )


class SubmitResponse(BaseModel):
    """Acknowledgment with the ID used to poll for the result."""

    correlation_id: str
    status: RequestStatus
    submitted_at: datetime


class StatusResponse(BaseModel):
    """Current processing status of a request."""

    correlation_id: str
    status: RequestStatus
    submitted_at: datetime
    updated_at: datetime


class ResultResponse(BaseModel):
    """Final result: the backend response (or error) for a request."""

    correlation_id: str
    status: RequestStatus
    result: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    status_code: int | None = Field(default=None, description="HTTP status from the backend")
    error: str | None = None
    processing_time_ms: int | None = None
    completed_at: datetime | None = None


class HealthResponse(BaseModel):
    """Health check payload."""

    status: str
    version: str
    timestamp: datetime
    components: dict[str, str]
