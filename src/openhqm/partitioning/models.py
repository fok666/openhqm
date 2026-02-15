"""Data models for partitioning configuration."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class PartitionStrategy(StrEnum):
    """Strategy for partition assignment."""

    HASH = "hash"  # Hash-based consistent distribution
    KEY = "key"  # Direct key-based assignment
    ROUND_ROBIN = "round_robin"  # Simple round-robin
    STICKY = "sticky"  # Sticky sessions (same key -> same partition)


class PartitionConfig(BaseModel):
    """Configuration for message partitioning.

    Partitioning ensures messages with the same partition key
    are always processed by the same worker instance, enabling
    session affinity for legacy applications.
    """

    enabled: bool = Field(default=False, description="Enable partitioning")

    strategy: PartitionStrategy = Field(
        default=PartitionStrategy.STICKY,
        description="Partition assignment strategy",
    )

    partition_count: int = Field(
        default=10,
        description="Number of logical partitions (should be >= worker count)",
        ge=1,
    )

    partition_key_field: str = Field(
        default="metadata.partition_key",
        description="Message field path to use as partition key",
    )

    session_key_field: str = Field(
        default="metadata.session_id",
        description="Message field path to use as session identifier",
    )

    rebalance_on_worker_change: bool = Field(
        default=True,
        description="Rebalance partitions when workers join/leave",
    )

    sticky_session_ttl: int = Field(
        default=3600,
        description="Session affinity TTL in seconds (0 = no expiration)",
        ge=0,
    )

    enable_queue_partitioning: bool = Field(
        default=False,
        description="Use native queue partitioning if supported (Kafka, Redis Streams)",
    )

    # Redis Streams specific
    redis_consumer_group: str = Field(
        default="openhqm-workers",
        description="Redis Streams consumer group name",
    )

    # Kafka specific
    kafka_partition_assignment: Literal["range", "roundrobin", "sticky"] = Field(
        default="sticky",
        description="Kafka partition assignment strategy",
    )


class SessionInfo(BaseModel):
    """Information about a sticky session."""

    session_id: str = Field(..., description="Session identifier")
    partition_id: int = Field(..., description="Assigned partition")
    worker_id: str = Field(..., description="Worker handling this session")
    last_seen: float = Field(..., description="Timestamp of last activity")
    message_count: int = Field(default=0, description="Messages processed in this session")
