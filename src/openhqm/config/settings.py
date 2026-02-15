"""Application settings and configuration."""

from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from openhqm.partitioning.models import PartitionConfig


class ServerSettings(BaseSettings):
    """HTTP server configuration."""

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port", ge=0, le=65535)
    workers: int = Field(default=4, description="Number of Uvicorn workers")
    reload: bool = Field(default=False, description="Enable auto-reload")


class QueueSettings(BaseSettings):
    """Message queue configuration."""

    type: Literal["redis", "kafka", "sqs", "azure_eventhubs", "gcp_pubsub", "mqtt", "custom"] = (
        Field(default="redis", description="Queue backend type")
    )

    # Redis Streams configuration
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")

    # Apache Kafka configuration
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092", description="Kafka bootstrap servers (comma-separated)"
    )
    kafka_consumer_group: str = Field(
        default="openhqm-workers", description="Kafka consumer group ID"
    )
    kafka_topics: list[str] = Field(
        default_factory=lambda: ["openhqm-requests"], description="Kafka topics to consume"
    )

    # AWS SQS configuration
    sqs_region: str = Field(default="us-east-1", description="AWS region for SQS")
    sqs_queue_url: str = Field(default="", description="SQS queue URL")

    # Azure Event Hubs configuration
    azure_eventhubs_connection_string: str = Field(
        default="", description="Azure Event Hubs connection string"
    )
    azure_eventhubs_name: str = Field(default="openhqm", description="Event Hub name")
    azure_eventhubs_consumer_group: str = Field(
        default="$Default", description="Event Hubs consumer group"
    )
    azure_eventhubs_checkpoint_store: str = Field(
        default="", description="Azure Blob Storage connection for checkpoints"
    )

    # GCP Pub/Sub configuration
    gcp_project_id: str = Field(default="", description="GCP project ID")
    gcp_credentials_path: str = Field(default="", description="Path to GCP service account JSON")
    gcp_max_messages: int = Field(default=10, description="Max messages to pull per request")

    # MQTT configuration
    mqtt_broker_host: str = Field(default="localhost", description="MQTT broker hostname")
    mqtt_broker_port: int = Field(default=1883, description="MQTT broker port")
    mqtt_username: str = Field(default="", description="MQTT username")
    mqtt_password: str = Field(default="", description="MQTT password")
    mqtt_qos: int = Field(default=1, description="MQTT Quality of Service (0, 1, or 2)")
    mqtt_client_id: str = Field(default="", description="MQTT client ID (auto-generated if empty)")

    # Custom queue handler configuration
    custom_module: str = Field(
        default="", description="Python module path for custom queue handler"
    )
    custom_class: str = Field(default="", description="Class name for custom queue handler")
    custom_config: dict[str, Any] = Field(
        default_factory=dict, description="Custom configuration passed to handler"
    )

    # Common queue settings
    request_queue_name: str = Field(
        default="openhqm-requests", description="Request queue/topic name"
    )
    response_queue_name: str = Field(
        default="openhqm-responses", description="Response queue/topic name"
    )
    dlq_name: str = Field(default="openhqm-dlq", description="Dead letter queue name")


class WorkerSettings(BaseSettings):
    """Worker configuration."""

    count: int = Field(default=5, description="Number of worker instances")
    batch_size: int = Field(default=10, description="Messages to process per batch")
    timeout_seconds: int = Field(default=300, description="Processing timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_base: float = Field(default=1.0, description="Base retry delay in seconds")
    retry_delay_max: float = Field(default=60.0, description="Maximum retry delay in seconds")


class EndpointConfig(BaseModel):
    """Configuration for a single endpoint."""

    url: str = Field(..., description="Target endpoint URL", min_length=1)
    method: str = Field(default="POST", description="HTTP method to use")
    timeout: int = Field(default=300, description="Request timeout in seconds", ge=0)
    headers: dict[str, str] | None = Field(default=None, description="Static headers to include")
    auth_type: Literal["bearer", "basic", "api_key", "custom"] | None = Field(
        default=None, description="Authentication type"
    )
    auth_token: str | None = Field(default=None, description="Auth token for bearer/api_key")
    auth_username: str | None = Field(default=None, description="Username for basic auth")
    auth_password: str | None = Field(default=None, description="Password for basic auth")
    auth_header_name: str | None = Field(
        default="Authorization", description="Header name for custom auth"
    )


class ProxySettings(BaseSettings):
    """Reverse proxy configuration for endpoints."""

    enabled: bool = Field(default=False, description="Enable proxy mode")
    default_endpoint: str | None = Field(
        default=None, description="Default endpoint URL if no routing specified"
    )
    endpoints: dict[str, EndpointConfig] = Field(
        default_factory=dict, description="Named endpoint configurations"
    )
    forward_headers: list[str] = Field(
        default_factory=lambda: ["Content-Type", "Accept", "User-Agent"],
        description="Headers to forward from client",
    )
    strip_headers: list[str] = Field(
        default_factory=lambda: ["Host", "Connection"],
        description="Headers to strip before forwarding",
    )
    max_response_size: int = Field(
        default=10 * 1024 * 1024, description="Maximum response size in bytes (10MB)"
    )


class CacheSettings(BaseSettings):
    """Cache configuration."""

    type: Literal["redis", "memory"] = Field(default="redis", description="Cache backend type")
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    ttl_seconds: int = Field(default=3600, description="Default cache TTL")
    max_connections: int = Field(default=10, description="Maximum connection pool size")


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration."""

    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: Literal["json", "text"] = Field(default="json", description="Log format")


class RoutingSettings(BaseSettings):
    """Routing configuration."""

    enabled: bool = Field(default=False, description="Enable routing engine")
    config_path: str | None = Field(
        default=None, description="Path to routing config file (YAML/JSON)"
    )
    config_dict: dict[str, Any] | None = Field(
        default=None, description="Inline routing configuration"
    )


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
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    partitioning: PartitionConfig = Field(default_factory=PartitionConfig)


# Global settings instance
settings = Settings()
