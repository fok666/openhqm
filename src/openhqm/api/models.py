"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum

from pydantic import BaseModel, Field


class RequestStatus(str, Enum):
    """Request processing status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class RequestMetadata(BaseModel):
    """Metadata for request processing."""

    priority: int = Field(default=0, ge=0, le=9, description="Priority level (0-9)")
    timeout: int = Field(default=300, gt=0, description="Timeout in seconds")
    retry_count: int = Field(default=0, ge=0, description="Current retry count")
    endpoint: Optional[str] = Field(default=None, description="Target endpoint name")
    method: Optional[str] = Field(default=None, description="HTTP method override")


class SubmitRequest(BaseModel):
    """Request model for submitting a new request."""

    payload: Dict[str, Any] = Field(..., description="Request payload")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers to forward")
    metadata: Optional[RequestMetadata] = Field(default=None, description="Request metadata")

    model_config = {"json_schema_extra": {"example": {"payload": {"operation": "echo", "data": "Hello World"}, "headers": {"Authorization": "Bearer token123"}, "metadata": {"priority": 5, "timeout": 300, "endpoint": "api-service"}}}}


class SubmitResponse(BaseModel):
    """Response model for request submission."""

    correlation_id: str = Field(..., description="Unique correlation ID")
    status: RequestStatus = Field(..., description="Request status")
    submitted_at: datetime = Field(..., description="Submission timestamp")

    model_config = {"json_schema_extra": {"example": {"correlation_id": "550e8400-e29b-41d4-a716-446655440000", "status": "PENDING", "submitted_at": "2026-02-07T10:30:00Z"}}}


class StatusResponse(BaseModel):
    """Response model for status check."""

    correlation_id: str = Field(..., description="Unique correlation ID")
    status: RequestStatus = Field(..., description="Current status")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"json_schema_extra": {"example": {"correlation_id": "550e8400-e29b-41d4-a716-446655440000", "status": "PROCESSING", "submitted_at": "2026-02-07T10:30:00Z", "updated_at": "2026-02-07T10:30:05Z"}}}


class ResultResponse(BaseModel):
    """Response model for result retrieval."""

    correlation_id: str = Field(..., description="Unique correlation ID")
    status: RequestStatus = Field(..., description="Final status")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Processing result")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Response headers")
    status_code: Optional[int] = Field(default=None, description="HTTP status code from worker")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    processing_time_ms: Optional[int] = Field(default=None, description="Processing time in ms")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")

    model_config = {"json_schema_extra": {"example": {"correlation_id": "550e8400-e29b-41d4-a716-446655440000", "status": "COMPLETED", "result": {"output": "processed data"}, "status_code": 200, "processing_time_ms": 1250, "completed_at": "2026-02-07T10:30:10Z"}}}


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(..., description="Current timestamp")
    components: Dict[str, str] = Field(..., description="Component health status")

    model_config = {"json_schema_extra": {"example": {"status": "healthy", "version": "0.1.0", "timestamp": "2026-02-07T10:30:00Z", "components": {"api": "healthy", "queue": "healthy", "cache": "healthy"}}}}
