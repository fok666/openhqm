"""Prometheus metrics, exposed at /metrics in http-to-queue mode."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

registry = CollectorRegistry()

api_requests_total = Counter(
    "openhqm_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

api_requests_in_flight = Gauge(
    "openhqm_api_requests_in_flight",
    "In-flight API requests",
    ["endpoint"],
    registry=registry,
)

queue_publish_total = Counter(
    "openhqm_queue_publish_total",
    "Total messages published",
    ["queue_name", "status"],
    registry=registry,
)

queue_dlq_total = Counter(
    "openhqm_queue_dlq_total",
    "Messages sent to DLQ",
    ["reason"],
    registry=registry,
)

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
