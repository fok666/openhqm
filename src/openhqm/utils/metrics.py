"""Prometheus metrics for monitoring."""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from openhqm.config import settings

# Create registry
registry = CollectorRegistry()

# API metrics
api_requests_total = Counter(
    "openhqm_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

api_request_duration_seconds = Histogram(
    "openhqm_api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
    registry=registry,
)

api_requests_in_flight = Gauge(
    "openhqm_api_requests_in_flight",
    "In-flight API requests",
    ["endpoint"],
    registry=registry,
)

# Queue metrics
queue_publish_total = Counter(
    "openhqm_queue_publish_total",
    "Total messages published",
    ["queue_name", "status"],
    registry=registry,
)

queue_consume_total = Counter(
    "openhqm_queue_consume_total",
    "Total messages consumed",
    ["queue_name"],
    registry=registry,
)

queue_depth = Gauge(
    "openhqm_queue_depth",
    "Current queue depth",
    ["queue_name"],
    registry=registry,
)

queue_dlq_total = Counter(
    "openhqm_queue_dlq_total",
    "Messages sent to DLQ",
    ["reason"],
    registry=registry,
)

# Worker metrics
worker_active = Gauge(
    "openhqm_worker_active",
    "Active workers",
    ["worker_id"],
    registry=registry,
)

worker_processing_duration_seconds = Histogram(
    "openhqm_worker_processing_duration_seconds",
    "Message processing duration",
    ["status"],
    registry=registry,
)

worker_errors_total = Counter(
    "openhqm_worker_errors_total",
    "Worker errors",
    ["error_type"],
    registry=registry,
)


class Metrics:
    """Metrics wrapper for easy access."""

    def __init__(self):
        self.api_requests_total = api_requests_total
        self.api_request_duration_seconds = api_request_duration_seconds
        self.api_requests_in_flight = api_requests_in_flight
        self.queue_publish_total = queue_publish_total
        self.queue_consume_total = queue_consume_total
        self.queue_depth = queue_depth
        self.queue_dlq_total = queue_dlq_total
        self.worker_active = worker_active
        self.worker_processing_duration_seconds = worker_processing_duration_seconds
        self.worker_errors_total = worker_errors_total
        self.registry = registry


metrics = Metrics()
