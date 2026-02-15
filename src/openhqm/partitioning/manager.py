"""Partition manager for session-aware message distribution."""

import hashlib
import time
from typing import Any

import structlog

from openhqm.partitioning.models import PartitionConfig, PartitionStrategy, SessionInfo
from openhqm.utils.helpers import get_nested_value

logger = structlog.get_logger(__name__)


class PartitionManager:
    """Manages partition assignment and session affinity for workers.

    Ensures messages with the same partition key are processed by the
    same worker instance, enabling session management for legacy apps.
    """

    def __init__(self, config: PartitionConfig, worker_id: str):
        """Initialize partition manager.

        Args:
            config: Partition configuration
            worker_id: Unique identifier for this worker instance
        """
        self.config = config
        self.worker_id = worker_id
        self._sessions: dict[str, SessionInfo] = {}
        self._partition_assignments: dict[int, str] = {}  # partition_id -> worker_id
        self._worker_partitions: set[int] = set()  # Partitions owned by this worker

        logger.info(
            "Partition manager initialized",
            worker_id=worker_id,
            strategy=config.strategy,
            partition_count=config.partition_count,
        )

    def _hash_key(self, key: str) -> int:
        """Generate consistent hash for a key.

        Args:
            key: Key to hash

        Returns:
            Hash value as integer
        """
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)

    def _assign_partition(self, key: str) -> int:
        """Assign partition based on key and strategy.

        Args:
            key: Partition key

        Returns:
            Partition ID (0 to partition_count - 1)
        """
        if self.config.strategy == PartitionStrategy.HASH:
            hash_value = self._hash_key(key)
            return hash_value % self.config.partition_count

        elif self.config.strategy in [PartitionStrategy.STICKY, PartitionStrategy.KEY]:
            # Consistent hashing for sticky sessions
            hash_value = self._hash_key(key)
            return hash_value % self.config.partition_count

        elif self.config.strategy == PartitionStrategy.ROUND_ROBIN:
            # Round-robin based on current time (not truly round-robin across workers)
            return int(time.time() * 1000) % self.config.partition_count

        else:
            # Default to hash
            return self._hash_key(key) % self.config.partition_count

    def assign_worker_partitions(self, worker_count: int, worker_index: int):
        """Assign partitions to this worker based on worker count.

        Args:
            worker_count: Total number of workers
            worker_index: This worker's index (0-based)
        """
        self._worker_partitions.clear()

        # Distribute partitions across workers
        for partition_id in range(self.config.partition_count):
            assigned_worker_index = partition_id % worker_count
            if assigned_worker_index == worker_index:
                self._worker_partitions.add(partition_id)
                self._partition_assignments[partition_id] = self.worker_id

        logger.info(
            "Worker partitions assigned",
            worker_id=self.worker_id,
            worker_index=worker_index,
            worker_count=worker_count,
            assigned_partitions=sorted(self._worker_partitions),
        )

    def set_assigned_partitions(self, partitions: set[int]):
        """Manually set which partitions this worker should process.

        Args:
            partitions: Set of partition IDs to assign to this worker
        """
        self._worker_partitions = set(partitions)
        for partition_id in partitions:
            self._partition_assignments[partition_id] = self.worker_id

        logger.info(
            "Worker partitions set",
            worker_id=self.worker_id,
            assigned_partitions=sorted(self._worker_partitions),
        )

    def get_partition_key(self, message: dict[str, Any]) -> str | None:
        """Extract partition key from message.

        Args:
            message: Queue message

        Returns:
            Partition key or None if not found
        """
        return get_nested_value(message, self.config.partition_key_field)

    def get_session_id(self, message: dict[str, Any]) -> str | None:
        """Extract session ID from message.

        Args:
            message: Queue message

        Returns:
            Session ID or None if not found
        """
        return get_nested_value(message, self.config.session_key_field)

    def get_partition_for_message(self, message: dict[str, Any]) -> int | None:
        """Determine partition for a message.

        Args:
            message: Queue message

        Returns:
            Partition ID or None if partitioning is disabled
        """
        if not self.config.enabled:
            return None

        # Try partition key first
        partition_key = self.get_partition_key(message)
        if not partition_key:
            # Try session ID as fallback
            partition_key = self.get_session_id(message)

        if not partition_key:
            logger.warning(
                "No partition key found in message",
                correlation_id=message.get("correlation_id"),
            )
            return None

        return self._assign_partition(partition_key)

    def should_process_message(self, message: dict[str, Any]) -> bool:
        """Check if this worker should process the message.

        Args:
            message: Queue message

        Returns:
            True if this worker owns the partition for this message
        """
        if not self.config.enabled:
            return True  # Process all messages if partitioning disabled

        partition_id = self.get_partition_for_message(message)
        if partition_id is None:
            return True  # Process if no partition assigned

        return partition_id in self._worker_partitions

    def track_session(self, message: dict[str, Any]):
        """Track session activity for sticky sessions.

        Args:
            message: Queue message
        """
        session_id = self.get_session_id(message)
        if not session_id:
            return

        partition_id = self.get_partition_for_message(message)
        if partition_id is None:
            return

        now = time.time()

        if session_id in self._sessions:
            # Update existing session
            session = self._sessions[session_id]
            session.last_seen = now
            session.message_count += 1
        else:
            # Create new session
            self._sessions[session_id] = SessionInfo(
                session_id=session_id,
                partition_id=partition_id,
                worker_id=self.worker_id,
                last_seen=now,
                message_count=1,
            )

        logger.debug(
            "Session tracked",
            session_id=session_id,
            partition_id=partition_id,
            message_count=self._sessions[session_id].message_count,
        )

    def cleanup_expired_sessions(self):
        """Remove expired sessions based on TTL."""
        if self.config.sticky_session_ttl == 0:
            return  # No expiration

        now = time.time()
        expired = []

        for session_id, session in self._sessions.items():
            if now - session.last_seen > self.config.sticky_session_ttl:
                expired.append(session_id)

        for session_id in expired:
            del self._sessions[session_id]

        if expired:
            logger.info("Expired sessions cleaned up", count=len(expired))

    def get_session_stats(self) -> dict[str, Any]:
        """Get statistics about active sessions.

        Returns:
            Dict with session statistics
        """
        return {
            "active_sessions": len(self._sessions),
            "assigned_partitions": len(self._worker_partitions),
            "partition_ids": sorted(self._worker_partitions),
            "total_messages": sum(s.message_count for s in self._sessions.values()),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get partition manager statistics (alias for get_session_stats).

        Returns:
            Dict with partition statistics
        """
        return self.get_session_stats()

    def get_partition_for_key(self, key: str) -> int:
        """Get partition ID for a specific key.

        Useful for manual partition assignment or testing.

        Args:
            key: Partition key

        Returns:
            Partition ID
        """
        return self._assign_partition(key)
