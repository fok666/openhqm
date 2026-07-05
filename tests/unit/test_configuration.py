"""Configuration validation and settings tests."""

import pytest
from pydantic import ValidationError

from openhqm.config.settings import (
    MonitoringSettings,
    ProxySettings,
    QueueSettings,
    ServerSettings,
    Settings,
)


class TestProxySettings:
    """Backend (queue-to-http) proxy configuration."""

    def test_defaults(self):
        p = ProxySettings()
        assert p.backend_url == ""
        assert p.method == ""
        assert p.auth_type is None
        assert "Content-Type" in p.forward_headers
        assert "Host" in p.strip_headers

    def test_backend_and_auth(self):
        p = ProxySettings(backend_url="http://localhost:8080", auth_type="bearer", auth_token="tok")
        assert p.backend_url == "http://localhost:8080"
        assert p.auth_type == "bearer"
        assert p.auth_token == "tok"

    def test_negative_timeout_invalid(self):
        with pytest.raises(ValidationError):
            ProxySettings(timeout=-1)

    def test_zero_timeout_valid(self):
        assert ProxySettings(timeout=0).timeout == 0


class TestQueueSettings:
    """Queue backend configuration."""

    def test_redis(self):
        q = QueueSettings(type="redis", redis_url="redis://localhost:6379")
        assert q.type == "redis"
        assert q.redis_url == "redis://localhost:6379"

    def test_kafka(self):
        q = QueueSettings(type="kafka", kafka_bootstrap_servers="localhost:9092")
        assert q.type == "kafka"

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            QueueSettings(type="not-a-queue")


class TestServerSettings:
    """HTTP server (http-to-queue) configuration."""

    def test_defaults(self):
        s = ServerSettings()
        assert s.host == "0.0.0.0"
        assert s.port == 8000

    @pytest.mark.parametrize("port", [-1, 70000])
    def test_out_of_range_port_invalid(self, port):
        with pytest.raises(ValidationError):
            ServerSettings(port=port)

    def test_port_zero_valid(self):
        assert ServerSettings(port=0).port == 0


class TestFullSettings:
    """Composed Settings object and env overrides."""

    def test_compose(self):
        settings = Settings(
            server=ServerSettings(port=8080),
            queue=QueueSettings(type="redis"),
            proxy=ProxySettings(backend_url="http://localhost:8080"),
        )
        assert settings.server.port == 8080
        assert settings.queue.type == "redis"
        assert settings.proxy.backend_url == "http://localhost:8080"

    def test_nested_env_override(self, monkeypatch):
        monkeypatch.setenv("OPENHQM_SERVER__PORT", "9001")
        monkeypatch.setenv("OPENHQM_PROXY__BACKEND_URL", "http://app:8080")
        settings = Settings()
        assert settings.server.port == 9001
        assert settings.proxy.backend_url == "http://app:8080"

    def test_log_level_passthrough(self):
        assert MonitoringSettings(log_level="DEBUG").log_level == "DEBUG"
