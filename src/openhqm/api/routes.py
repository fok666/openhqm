"""API route handlers."""

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from openhqm.api.dependencies import get_cache, get_queue
from openhqm.api.models import (
    RequestStatus,
    ResultResponse,
    StatusResponse,
    SubmitRequest,
    SubmitResponse,
)
from openhqm.cache.interface import CacheInterface
from openhqm.queue.interface import MessageQueueInterface
from openhqm.utils.metrics import metrics

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["requests"])


@router.post(
    "/submit",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new request",
    description="Queue a request for asynchronous processing with transparent header forwarding",
)
async def submit_request(
    request: SubmitRequest,
    queue: MessageQueueInterface = Depends(get_queue),
    cache: CacheInterface = Depends(get_cache),
) -> SubmitResponse:
    """
    Submit a request for asynchronous processing.

    - Generates a unique correlation ID
    - Validates the payload
    - Forwards headers transparently
    - Queues the request
    - Returns the correlation ID for tracking

    Args:
        request: The request to submit (with payload, headers, metadata)
        queue: Message queue instance
        cache: Cache instance

    Returns:
        Response with correlation ID and status

    Raises:
        HTTPException: If queueing fails
    """
    correlation_id = str(uuid.uuid4())
    submitted_at = datetime.utcnow()

    log = logger.bind(correlation_id=correlation_id)
    log.info("Submitting request", payload_size=len(str(request.payload)))

    # Prepare message
    message = {
        "correlation_id": correlation_id,
        "payload": request.payload,
        "headers": request.headers,
        "timestamp": submitted_at.isoformat(),
        "metadata": request.metadata.model_dump() if request.metadata else {},
    }

    try:
        # Store metadata in cache
        await cache.set(
            f"req:{correlation_id}:meta",
            {
                "status": RequestStatus.PENDING.value,
                "submitted_at": submitted_at.isoformat(),
                "updated_at": submitted_at.isoformat(),
            },
            ttl=3600,
        )

        # Publish to queue
        success = await queue.publish("requests", message)
        if not success:
            metrics.queue_publish_total.labels(queue_name="requests", status="failed").inc()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to queue request. Service temporarily unavailable.",
            )

        metrics.queue_publish_total.labels(queue_name="requests", status="success").inc()
        log.info("Request submitted successfully")

        return SubmitResponse(
            correlation_id=correlation_id,
            status=RequestStatus.PENDING,
            submitted_at=submitted_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to submit request", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit request",
        ) from e


@router.get(
    "/status/{correlation_id}",
    response_model=StatusResponse,
    summary="Check request status",
    description="Get the current status of a submitted request",
)
async def get_status(
    correlation_id: str,
    cache: CacheInterface = Depends(get_cache),
) -> StatusResponse:
    """
    Get the status of a request.

    Args:
        correlation_id: Request correlation ID
        cache: Cache instance

    Returns:
        Current request status

    Raises:
        HTTPException: If request not found
    """
    log = logger.bind(correlation_id=correlation_id)
    log.info("Checking request status")

    try:
        # Get metadata from cache
        metadata = await cache.get(f"req:{correlation_id}:meta")
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found or expired",
            )

        return StatusResponse(
            correlation_id=correlation_id,
            status=RequestStatus(metadata["status"]),
            submitted_at=datetime.fromisoformat(metadata["submitted_at"]),
            updated_at=datetime.fromisoformat(metadata["updated_at"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to get status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve status",
        ) from e


@router.get(
    "/response/{correlation_id}",
    response_model=ResultResponse,
    summary="Get request result",
    description="Retrieve the result of a processed request",
)
async def get_response(
    correlation_id: str,
    cache: CacheInterface = Depends(get_cache),
) -> ResultResponse:
    """
    Get the result of a processed request.

    Args:
        correlation_id: Request correlation ID
        cache: Cache instance

    Returns:
        Request result if completed, or current status

    Raises:
        HTTPException: If request not found
    """
    log = logger.bind(correlation_id=correlation_id)
    log.info("Retrieving request response")

    try:
        # Get metadata
        metadata = await cache.get(f"req:{correlation_id}:meta")
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found or expired",
            )

        req_status = RequestStatus(metadata["status"])

        # Get response if available
        response_data = await cache.get(f"resp:{correlation_id}")

        if req_status == RequestStatus.COMPLETED and response_data:
            return ResultResponse(
                correlation_id=correlation_id,
                status=req_status,
                result=response_data.get("result"),
                headers=response_data.get("headers"),
                status_code=response_data.get("status_code"),
                processing_time_ms=response_data.get("processing_time_ms"),
                completed_at=datetime.fromisoformat(response_data["completed_at"]),
            )
        elif req_status == RequestStatus.FAILED:
            return ResultResponse(
                correlation_id=correlation_id,
                status=req_status,
                error=response_data.get("error") if response_data else "Processing failed",
                completed_at=(
                    datetime.fromisoformat(response_data["completed_at"]) if response_data else None
                ),
            )
        else:
            # Still processing
            return ResultResponse(
                correlation_id=correlation_id,
                status=req_status,
            )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to get response", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve response",
        ) from e
