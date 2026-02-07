"""Unit tests for configuration."""

import os
import pytest

from openhqm.config.settings import Settings, QueueSettings, WorkerSettings


def test_default_settings():
    """Test default settings values."""
    settings = Settings()

    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 8000
    assert settings.queue.type == "redis"
    assert settings.worker.count == 5


def test_queue_settings():
    """Test queue settings."""
    queue_settings = QueueSettings(
        type="redis",
        redis_url="redis://test:6379",
    )

    assert queue_settings.type == "redis"
    assert queue_settings.redis_url == "redis://test:6379"


def test_worker_settings():
    """Test worker settings."""
    worker_settings = WorkerSettings(
        count=10,
        batch_size=20,
        max_retries=5,
    )

    assert worker_settings.count == 10
    assert worker_settings.batch_size == 20
    assert worker_settings.max_retries == 5


def test_settings_from_env(monkeypatch):
    """Test settings loaded from environment variables."""
    monkeypatch.setenv("OPENHQM_SERVER__PORT", "9000")
    monkeypatch.setenv("OPENHQM_QUEUE__TYPE", "kafka")
    monkeypatch.setenv("OPENHQM_WORKER__COUNT", "15")

    settings = Settings()

    assert settings.server.port == 9000
    assert settings.queue.type == "kafka"
    assert settings.worker.count == 15
