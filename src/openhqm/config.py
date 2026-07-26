"""All OpenHQM knobs, set via environment: prefix OPENHQM_, __ for nesting.

Example: OPENHQM_QUEUE__TYPE=kafka sets Settings().queue.type.
See .env.example for a ready-to-copy list.
"""

from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """HTTP server (http-to-queue mode)."""

    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=8000, description="Bind port", ge=0, le=65535)
    workers: int = Field(default=4, description="Uvicorn worker processes")


class QueueSettings(BaseSettings):
    """Queue backend selection plus per-backend connection settings."""

    type: Literal["redis", "kafka", "sqs", "azure_eventhubs", "gcp_pubsub", "mqtt", "custom"] = (
        Field(default="redis", description="Queue backend")
    )
    request_queue_name: str = Field(
        default="openhqm-requests", description="Request queue/topic/stream name"
    )
    dlq_name: str = Field(default="openhqm-dlq", description="Dead letter queue name")

    # redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")

    # kafka
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092", description="Kafka bootstrap servers (comma-separated)"
    )
    kafka_consumer_group: str = Field(
        default="openhqm-workers", description="Kafka consumer group ID"
    )

    # sqs (credentials come from the standard AWS env/IAM chain)
    sqs_region: str = Field(default="us-east-1", description="AWS region")
    sqs_queue_url: str = Field(
        default="", description="Request queue URL (optional; resolved by name when empty)"
    )

    # azure_eventhubs (event hubs named after request_queue_name/dlq_name must exist)
    azure_eventhubs_connection_string: str = Field(
        default="", description="Event Hubs namespace connection string"
    )
    azure_eventhubs_consumer_group: str = Field(
        default="$Default", description="Event Hubs consumer group"
    )
    azure_eventhubs_checkpoint_store: str = Field(
        default="", description="Blob Storage connection string for checkpoints (optional)"
    )

    # gcp_pubsub (topic and subscription named after the queue name must exist)
    gcp_project_id: str = Field(default="", description="GCP project ID")
    gcp_credentials_path: str = Field(
        default="", description="Service account JSON path (empty = ADC)"
    )

    # mqtt
    mqtt_broker_host: str = Field(default="localhost", description="MQTT broker hostname")
    mqtt_broker_port: int = Field(default=1883, description="MQTT broker port")
    mqtt_username: str = Field(default="", description="MQTT username")
    mqtt_password: str = Field(default="", description="MQTT password")
    mqtt_qos: int = Field(default=1, description="MQTT QoS (0, 1, or 2)", ge=0, le=2)
    mqtt_client_id: str = Field(default="", description="Client ID (auto-generated if empty)")

    # custom: load your own Queue implementation at runtime
    custom_module: str = Field(default="", description="Python module path of your Queue class")
    custom_class: str = Field(default="", description="Class name of your Queue implementation")
    custom_config: dict[str, Any] = Field(
        default_factory=dict, description="Constructor kwargs for the custom class"
    )


class WorkerSettings(BaseSettings):
    """Consume loop (queue-to-http mode)."""

    batch_size: int = Field(default=10, description="Messages fetched per poll", ge=1)
    max_retries: int = Field(default=3, description="Retries before a message goes to the DLQ")


class ProxySettings(BaseSettings):
    """Backend the queue-to-http worker forwards to (typically the local sidecar app)."""

    backend_url: str = Field(default="", description="Backend base URL, e.g. http://localhost:8080")
    method: str = Field(default="", description="Override HTTP method; empty uses request's method")
    timeout: int = Field(default=300, description="Request timeout in seconds", ge=0)
    headers: dict[str, str] | None = Field(
        default=None, description="Static headers added to every backend request"
    )
    auth_type: Literal["bearer", "basic", "api_key", "custom"] | None = Field(
        default=None, description="Authentication type"
    )
    auth_token: str | None = Field(default=None, description="Auth token for bearer/api_key/custom")
    auth_username: str | None = Field(default=None, description="Username for basic auth")
    auth_password: str | None = Field(default=None, description="Password for basic auth")
    auth_header_name: str | None = Field(
        default=None, description="Header name for api_key/custom (api_key defaults to X-API-Key)"
    )
    forward_headers: list[str] = Field(
        default_factory=lambda: ["Content-Type", "Accept", "User-Agent"],
        description="Client headers to forward ('*' forwards all)",
    )
    strip_headers: list[str] = Field(
        default_factory=lambda: ["Host", "Connection"],
        description="Headers to strip before forwarding",
    )


class CacheSettings(BaseSettings):
    """Result store (Redis) polled by clients."""

    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    ttl_seconds: int = Field(default=3600, description="How long results stay pollable")
    max_connections: int = Field(default=10, description="Connection pool size")


class MonitoringSettings(BaseSettings):
    """Observability."""

    metrics_enabled: bool = Field(default=True, description="Expose Prometheus /metrics")
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: Literal["json", "text"] = Field(default="json", description="Log format")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="OPENHQM_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)


settings = Settings()
