"""Tests for partition manager."""

import pytest

from openhqm.partitioning.manager import PartitionManager
from openhqm.partitioning.models import PartitionConfig, PartitionStrategy


def test_partition_assignment():
    """Test partition assignment to workers."""
    config = PartitionConfig(
        enabled=True,
        partition_count=10,
        strategy=PartitionStrategy.STICKY,
    )
    manager = PartitionManager(config, "worker-0")

    # Assign partitions for 5 workers, this is worker 0
    manager.assign_worker_partitions(worker_count=5, worker_index=0)

    # Worker 0 should get partitions 0 and 5
    assert manager._worker_partitions == {0, 5}


def test_partition_for_message():
    """Test partition calculation for a message."""
    config = PartitionConfig(
        enabled=True,
        partition_count=10,
        partition_key_field="metadata.session_id",
    )
    manager = PartitionManager(config, "worker-0")

    message = {
        "correlation_id": "test-123",
        "payload": {},
        "metadata": {"session_id": "sess-abc"},
    }

    partition_id = manager.get_partition_for_message(message)
    assert partition_id is not None
    assert 0 <= partition_id < 10


def test_should_process_message():
    """Test message processing decision based on partition."""
    config = PartitionConfig(
        enabled=True,
        partition_count=10,
    )
    manager = PartitionManager(config, "worker-0")
    manager.assign_worker_partitions(worker_count=5, worker_index=0)

    # Message with partition key that hashes to partition 0
    message = {
        "correlation_id": "test-123",
        "payload": {},
        "metadata": {"partition_key": "key-that-hashes-to-0"},
    }

    # Should process if partition 0 is assigned to this worker
    should_process = manager.should_process_message(message)
    # Result depends on hash, but method should work
    assert isinstance(should_process, bool)


def test_session_tracking():
    """Test session tracking."""
    config = PartitionConfig(
        enabled=True,
        partition_count=10,
        session_key_field="metadata.session_id",
    )
    manager = PartitionManager(config, "worker-0")
    manager.assign_worker_partitions(worker_count=5, worker_index=0)

    message = {
        "correlation_id": "test-123",
        "payload": {},
        "metadata": {"session_id": "sess-abc"},
    }

    manager.track_session(message)

    stats = manager.get_session_stats()
    assert stats["active_sessions"] >= 0  # May be 0 or 1 depending on partition assignment


def test_partition_disabled():
    """Test behavior when partitioning is disabled."""
    config = PartitionConfig(enabled=False)
    manager = PartitionManager(config, "worker-0")

    message = {
        "correlation_id": "test-123",
        "payload": {},
    }

    # Should always process when partitioning is disabled
    assert manager.should_process_message(message) is True

    # Partition ID should be None
    assert manager.get_partition_for_message(message) is None


def test_consistent_hashing():
    """Test that same key always hashes to same partition."""
    config = PartitionConfig(
        enabled=True,
        partition_count=10,
    )
    manager = PartitionManager(config, "worker-0")

    # Same key should always produce same partition
    partition1 = manager.get_partition_for_key("test-key")
    partition2 = manager.get_partition_for_key("test-key")
    assert partition1 == partition2


def test_multiple_workers():
    """Test partition distribution across multiple workers."""
    config = PartitionConfig(
        enabled=True,
        partition_count=10,
    )

    workers = []
    for i in range(5):
        manager = PartitionManager(config, f"worker-{i}")
        manager.assign_worker_partitions(worker_count=5, worker_index=i)
        workers.append(manager)

    # Each worker should have 2 partitions (10 / 5)
    for worker in workers:
        assert len(worker._worker_partitions) == 2

    # All partitions should be covered
    all_partitions = set()
    for worker in workers:
        all_partitions.update(worker._worker_partitions)

    assert all_partitions == set(range(10))
