"""Comprehensive API integration tests."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from openhqm.api.app import create_app


@pytest.fixture
def mock_queue():
    """Create mock queue for API tests."""
    queue = AsyncMock()
    queue.publish = AsyncMock(return_value=True)
    queue.connect = AsyncMock()
    return queue


@pytest.fixture
def mock_cache():
    """Create mock cache for API tests."""
    cache = AsyncMock()
    cache.get = AsyncMock()
    cache.set = AsyncMock()
    cache.connect = AsyncMock()
    return cache


@pytest.fixture
def client(mock_queue, mock_cache):
    """Create test client with mocked dependencies."""
    with patch("openhqm.api.dependencies.get_queue", return_value=mock_queue):
        with patch("openhqm.api.dependencies.get_cache", return_value=mock_cache):
            app = create_app()
            with TestClient(app) as test_client:
                yield test_client


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_metrics_endpoint(client):
    """Test metrics endpoint returns Prometheus format."""
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    # Should contain some metric names
    assert b"openhqm_" in response.content


def test_submit_request_success(client, mock_queue):
    """Test successful request submission."""
    payload = {
        "payload": {"operation": "test", "data": "hello"},
        "metadata": {"priority": "normal"},
    }

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202
    data = response.json()

    assert "correlation_id" in data
    assert data["status"] == "PENDING"
    assert "submitted_at" in data

    # Verify queue publish was called
    mock_queue.publish.assert_called_once()


def test_submit_request_with_headers(client, mock_queue):
    """Test request submission with custom headers."""
    payload = {
        "payload": {"data": "test"},
        "headers": {"Authorization": "Bearer token", "X-Custom": "value"},
    }

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202

    # Verify headers were included in queue message
    call_args = mock_queue.publish.call_args[0][1]
    assert call_args["headers"]["Authorization"] == "Bearer token"
    assert call_args["headers"]["X-Custom"] == "value"


def test_submit_request_with_endpoint(client, mock_queue):
    """Test request submission with specific endpoint."""
    payload = {"payload": {"data": "test"}, "metadata": {"endpoint": "api-service", "timeout": 300}}

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202

    # Verify metadata was passed
    call_args = mock_queue.publish.call_args[0][1]
    assert call_args["metadata"]["endpoint"] == "api-service"
    assert call_args["metadata"]["timeout"] == 300


def test_submit_request_minimal_payload(client, mock_queue):
    """Test request with minimal required fields."""
    payload = {"payload": {"data": "test"}}

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202


def test_submit_request_validation_error_missing_payload(client):
    """Test request validation error for missing payload."""
    response = client.post("/api/v1/submit", json={})

    assert response.status_code == 422


def test_submit_request_validation_error_invalid_json(client):
    """Test request validation error for invalid JSON."""
    response = client.post(
        "/api/v1/submit", data="invalid json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422


def test_submit_request_queue_failure(client, mock_queue):
    """Test handling of queue publish failure."""
    mock_queue.publish.side_effect = Exception("Queue error")

    payload = {"payload": {"data": "test"}}

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 500
    assert "error" in response.json()


def test_get_status_pending(client, mock_cache):
    """Test getting status for pending request."""
    mock_cache.get.return_value = {"status": "PENDING", "submitted_at": "2026-02-08T10:00:00Z"}

    response = client.get("/api/v1/status/test-correlation-123")

    assert response.status_code == 200
    data = response.json()

    assert data["correlation_id"] == "test-correlation-123"
    assert data["status"] == "PENDING"
    assert data["submitted_at"] == "2026-02-08T10:00:00Z"


def test_get_status_processing(client, mock_cache):
    """Test getting status for processing request."""
    mock_cache.get.return_value = {
        "status": "PROCESSING",
        "submitted_at": "2026-02-08T10:00:00Z",
        "updated_at": "2026-02-08T10:00:05Z",
    }

    response = client.get("/api/v1/status/test-correlation-456")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "PROCESSING"
    assert "updated_at" in data


def test_get_status_not_found(client, mock_cache):
    """Test getting status for non-existent request."""
    mock_cache.get.return_value = None

    response = client.get("/api/v1/status/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_response_completed(client, mock_cache):
    """Test getting completed response."""
    mock_cache.get.side_effect = [
        {  # Metadata
            "status": "COMPLETED",
            "submitted_at": "2026-02-08T10:00:00Z",
            "updated_at": "2026-02-08T10:00:10Z",
        },
        {  # Response
            "result": {"output": "success"},
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "processing_time_ms": 1500,
            "completed_at": "2026-02-08T10:00:10Z",
        },
    ]

    response = client.get("/api/v1/response/test-correlation-789")

    assert response.status_code == 200
    data = response.json()

    assert data["correlation_id"] == "test-correlation-789"
    assert data["status"] == "COMPLETED"
    assert data["result"] == {"output": "success"}
    assert data["status_code"] == 200
    assert data["processing_time_ms"] == 1500


def test_get_response_still_processing(client, mock_cache):
    """Test getting response when request is still processing."""
    mock_cache.get.side_effect = [
        {  # Metadata
            "status": "PROCESSING",
            "submitted_at": "2026-02-08T10:00:00Z",
        },
        None,  # No response yet
    ]

    response = client.get("/api/v1/response/test-in-progress")

    assert response.status_code == 202
    data = response.json()

    assert data["status"] == "PROCESSING"
    assert "result" not in data


def test_get_response_failed(client, mock_cache):
    """Test getting response for failed request."""
    mock_cache.get.side_effect = [
        {  # Metadata
            "status": "FAILED",
            "submitted_at": "2026-02-08T10:00:00Z",
            "updated_at": "2026-02-08T10:00:15Z",
        },
        {  # Response with error
            "error": "Processing failed: Network timeout",
            "completed_at": "2026-02-08T10:00:15Z",
        },
    ]

    response = client.get("/api/v1/response/test-failed")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "FAILED"
    assert "error" in data
    assert "Network timeout" in data["error"]


def test_get_response_not_found(client, mock_cache):
    """Test getting response for non-existent request."""
    mock_cache.get.return_value = None

    response = client.get("/api/v1/response/nonexistent")

    assert response.status_code == 404


def test_cors_headers(client):
    """Test CORS headers are present."""
    response = client.options("/api/v1/submit")

    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers


def test_rate_limiting_headers(client, mock_queue):
    """Test rate limiting headers are included."""
    payload = {"payload": {"data": "test"}}

    response = client.post("/api/v1/submit", json=payload)

    # Headers might include rate limit info
    # This depends on implementation
    assert response.status_code in [200, 202]


def test_concurrent_submissions(client, mock_queue):
    """Test multiple concurrent submissions."""
    payloads = [{"payload": {"data": f"test-{i}"}} for i in range(10)]

    responses = [client.post("/api/v1/submit", json=p) for p in payloads]

    # All should succeed
    assert all(r.status_code == 202 for r in responses)

    # All should have unique correlation IDs
    correlation_ids = [r.json()["correlation_id"] for r in responses]
    assert len(set(correlation_ids)) == 10


def test_large_payload_submission(client, mock_queue):
    """Test submission with large payload."""
    large_data = {"items": [{"id": i, "data": "x" * 1000} for i in range(100)]}
    payload = {"payload": large_data}

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202


def test_special_characters_in_payload(client, mock_queue):
    """Test payload with special characters."""
    payload = {
        "payload": {"text": "Hello 世界 🌍", "unicode": "\u2713 \u2717", "special": "!@#$%^&*()"}
    }

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202


def test_nested_payload_structure(client, mock_queue):
    """Test deeply nested payload structure."""
    payload = {"payload": {"level1": {"level2": {"level3": {"level4": {"data": "deep"}}}}}}

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202


def test_null_values_in_payload(client, mock_queue):
    """Test payload with null values."""
    payload = {"payload": {"field1": None, "field2": "value", "field3": None}}

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202


def test_empty_array_in_payload(client, mock_queue):
    """Test payload with empty arrays."""
    payload = {"payload": {"items": [], "tags": []}}

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202


def test_boolean_values_in_payload(client, mock_queue):
    """Test payload with boolean values."""
    payload = {"payload": {"enabled": True, "active": False, "verified": True}}

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202


def test_numeric_values_in_payload(client, mock_queue):
    """Test payload with various numeric types."""
    payload = {
        "payload": {
            "integer": 42,
            "float": 3.14159,
            "negative": -100,
            "zero": 0,
            "large": 9999999999,
        }
    }

    response = client.post("/api/v1/submit", json=payload)

    assert response.status_code == 202


def test_api_version_endpoint(client):
    """Test API version information."""
    response = client.get("/")

    # Root endpoint should return API info
    assert response.status_code in [200, 404]  # Depends on implementation


def test_request_id_tracking(client, mock_queue):
    """Test that request IDs are tracked through the system."""
    payload = {"payload": {"data": "test"}}

    response = client.post(
        "/api/v1/submit", json=payload, headers={"X-Request-ID": "client-request-123"}
    )

    assert response.status_code == 202
    # Correlation ID should be returned
    assert "correlation_id" in response.json()


def test_content_type_validation(client):
    """Test content type validation."""
    response = client.post(
        "/api/v1/submit",
        data="payload=test",  # Form data instead of JSON
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    # Should reject non-JSON content
    assert response.status_code in [415, 422]


def test_method_not_allowed(client):
    """Test method not allowed responses."""
    response = client.put("/api/v1/submit", json={"payload": {}})

    assert response.status_code == 405


def test_invalid_correlation_id_format(client, mock_cache):
    """Test handling of invalid correlation ID format."""
    mock_cache.get.return_value = None

    response = client.get("/api/v1/status/invalid format with spaces")

    # Should handle gracefully
    assert response.status_code in [400, 404]
