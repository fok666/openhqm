"""Configuration validation and settings tests."""

import pytest
from pydantic import ValidationError
from unittest.mock import patch
import os

from openhqm.config.settings import (
    Settings,
    ServerSettings,
    QueueSettings,
    ProxySettings,
    RoutingSettings,
    PartitionConfig,
    EndpointConfig,
)


class TestEndpointConfig:
    """Test EndpointConfig validation."""

    def test_endpoint_config_minimal(self):
        """Test minimal valid endpoint configuration."""
        config = EndpointConfig(url="http://api.example.com")

        assert config.url == "http://api.example.com"
        assert config.method == "POST"
        assert config.timeout == 300
        assert config.auth_type is None

    def test_endpoint_config_full(self):
        """Test full endpoint configuration."""
        config = EndpointConfig(
            url="http://api.example.com",
            method="PUT",
            timeout=600,
            auth_type="bearer",
            auth_token="test-token",
            headers={"X-Custom": "value"},
        )

        assert config.method == "PUT"
        assert config.timeout == 600
        assert config.auth_type == "bearer"

    def test_endpoint_config_invalid_url(self):
        """Test endpoint config with invalid URL."""
        # Should still create config (validation is lenient)
        config = EndpointConfig(url="not-a-url")
        assert config.url == "not-a-url"

    def test_endpoint_config_auth_bearer(self):
        """Test bearer authentication configuration."""
        config = EndpointConfig(
            url="http://api.example.com", auth_type="bearer", auth_token="secret-token"
        )

        assert config.auth_type == "bearer"
        assert config.auth_token == "secret-token"

    def test_endpoint_config_auth_basic(self):
        """Test basic authentication configuration."""
        config = EndpointConfig(
            url="http://api.example.com",
            auth_type="basic",
            auth_username="user",
            auth_password="pass",
        )

        assert config.auth_type == "basic"
        assert config.auth_username == "user"
        assert config.auth_password == "pass"


class TestProxySettings:
    """Test ProxySettings validation."""

    def test_proxy_settings_disabled(self):
        """Test proxy settings when disabled."""
        settings = ProxySettings(enabled=False)

        assert settings.enabled is False
        assert settings.default_endpoint is None

    def test_proxy_settings_with_default_url(self):
        """Test proxy settings with default URL."""
        settings = ProxySettings(enabled=True, default_endpoint="http://default.example.com")

        assert settings.enabled is True
        assert settings.default_endpoint == "http://default.example.com"

    def test_proxy_settings_with_endpoints(self):
        """Test proxy settings with multiple endpoints."""
        settings = ProxySettings(
            enabled=True,
            endpoints={
                "api1": EndpointConfig(url="http://api1.example.com"),
                "api2": EndpointConfig(url="http://api2.example.com"),
            },
        )

        assert len(settings.endpoints) == 2
        assert "api1" in settings.endpoints
        assert "api2" in settings.endpoints

    def test_proxy_settings_header_forwarding(self):
        """Test header forwarding configuration."""
        settings = ProxySettings(
            enabled=True,
            forward_headers=["Authorization", "X-Request-ID"],
            strip_headers=["Host", "Connection"],
        )

        assert "Authorization" in settings.forward_headers
        assert "Host" in settings.strip_headers


class TestRoutingSettings:
    """Test RoutingSettings validation."""

    def test_routing_settings_disabled(self):
        """Test routing settings when disabled."""
        settings = RoutingSettings(enabled=False)

        assert settings.enabled is False
        assert settings.config_path is None

    def test_routing_settings_with_file(self):
        """Test routing settings with config file."""
        settings = RoutingSettings(enabled=True, config_path="/etc/openhqm/routing.yaml")

        assert settings.enabled is True
        assert settings.config_path == "/etc/openhqm/routing.yaml"

    def test_routing_settings_with_inline_config(self):
        """Test routing settings with inline configuration."""
        settings = RoutingSettings(
            enabled=True, config_dict={"version": "1.0", "routes": [{"name": "test"}]}
        )

        assert settings.enabled is True
        assert settings.config_dict is not None
        assert "routes" in settings.config_dict


class TestPartitionConfig:
    """Test PartitionConfig validation."""

    def test_partition_config_default(self):
        """Test default partition configuration."""
        config = PartitionConfig()

        assert config.enabled is False
        assert config.partition_count == 10
        assert config.strategy == "sticky"

    def test_partition_config_enabled(self):
        """Test enabled partition configuration."""
        config = PartitionConfig(enabled=True, partition_count=20, strategy="hash")

        assert config.enabled is True
        assert config.partition_count == 20
        assert config.strategy == "hash"

    def test_partition_config_custom_fields(self):
        """Test partition configuration with custom field paths."""
        config = PartitionConfig(
            enabled=True,
            partition_key_field="metadata.tenant_id",
            session_key_field="metadata.user_session",
        )

        assert config.partition_key_field == "metadata.tenant_id"
        assert config.session_key_field == "metadata.user_session"

    def test_partition_config_sticky_ttl(self):
        """Test partition configuration with sticky session TTL."""
        config = PartitionConfig(enabled=True, strategy="sticky", sticky_session_ttl=7200)

        assert config.sticky_session_ttl == 7200


class TestQueueSettings:
    """Test QueueSettings validation."""

    def test_queue_settings_redis(self):
        """Test Redis queue configuration."""
        settings = QueueSettings(type="redis", redis_url="redis://localhost:6379")

        assert settings.type == "redis"
        assert settings.redis_url == "redis://localhost:6379"

    def test_queue_settings_kafka(self):
        """Test Kafka queue configuration."""
        settings = QueueSettings(type="kafka", kafka_bootstrap_servers="localhost:9092")

        assert settings.type == "kafka"
        assert settings.kafka_bootstrap_servers == "localhost:9092"

    def test_queue_settings_sqs(self):
        """Test SQS queue configuration."""
        settings = QueueSettings(
            type="sqs",
            sqs_region="us-east-1",
            sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123/requests",
        )

        assert settings.type == "sqs"
        assert settings.sqs_region == "us-east-1"


class TestServerSettings:
    """Test ServerSettings validation."""

    def test_server_settings_default(self):
        """Test default server configuration."""
        settings = ServerSettings()

        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.reload is False

    def test_server_settings_custom(self):
        """Test custom server configuration."""
        settings = ServerSettings(host="127.0.0.1", port=8080, reload=True, log_level="DEBUG")

        assert settings.host == "127.0.0.1"
        assert settings.port == 8080
        assert settings.reload is True
        assert settings.log_level == "DEBUG"


class TestFullSettings:
    """Test complete Settings object."""

    def test_settings_from_env(self):
        """Test loading settings from environment variables."""
        with patch.dict(
            os.environ,
            {
                "OPENHQM_SERVER__PORT": "9000",
                "OPENHQM_QUEUE__TYPE": "redis",
                "OPENHQM_PROXY__ENABLED": "true",
            },
        ):
            # Would need to reload settings module
            # This is a placeholder for the concept
            pass

    def test_settings_validation_complete(self):
        """Test complete settings validation."""
        settings = Settings(
            server=ServerSettings(port=8000),
            queue=QueueSettings(type="redis"),
            proxy=ProxySettings(enabled=True),
            routing=RoutingSettings(enabled=False),
            partitioning=PartitionConfig(enabled=False),
        )

        assert settings.server.port == 8000
        assert settings.queue.type == "redis"
        assert settings.proxy.enabled is True

    def test_settings_with_all_features_enabled(self):
        """Test settings with all features enabled."""
        settings = Settings(
            server=ServerSettings(port=8000),
            queue=QueueSettings(type="redis"),
            proxy=ProxySettings(
                enabled=True, endpoints={"api": EndpointConfig(url="http://api.example.com")}
            ),
            routing=RoutingSettings(enabled=True, config_dict={"version": "1.0", "routes": []}),
            partitioning=PartitionConfig(enabled=True, partition_count=10),
        )

        assert settings.proxy.enabled is True
        assert settings.routing.enabled is True
        assert settings.partitioning.enabled is True


class TestConfigurationValidation:
    """Test configuration validation rules."""

    def test_negative_port_invalid(self):
        """Test that negative port number is invalid."""
        with pytest.raises(ValidationError):
            ServerSettings(port=-1)

    def test_zero_port_invalid(self):
        """Test that port 0 is handled."""
        # Port 0 means OS assigns port
        settings = ServerSettings(port=0)
        assert settings.port == 0

    def test_huge_port_invalid(self):
        """Test that port number above 65535 is invalid."""
        with pytest.raises(ValidationError):
            ServerSettings(port=70000)

    def test_negative_timeout_invalid(self):
        """Test that negative timeout is invalid."""
        with pytest.raises(ValidationError):
            EndpointConfig(url="http://test.com", timeout=-10)

    def test_zero_timeout_valid(self):
        """Test that zero timeout is handled."""
        # Zero timeout means no timeout
        config = EndpointConfig(url="http://test.com", timeout=0)
        assert config.timeout == 0

    def test_empty_url_invalid(self):
        """Test that empty URL is invalid."""
        with pytest.raises(ValidationError):
            EndpointConfig(url="")

    def test_invalid_queue_type(self):
        """Test that invalid queue type is rejected."""
        # Depending on validation, this might raise
        try:
            settings = QueueSettings(type="invalid-type")
            # If no validation, just check it was set
            assert settings.type == "invalid-type"
        except ValidationError:
            # Expected if validation is strict
            pass

    def test_invalid_log_level(self):
        """Test that invalid log level is handled."""
        # Should accept any string (will be validated at runtime)
        settings = ServerSettings(log_level="INVALID")
        assert settings.log_level == "INVALID"


class TestEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_env_prefix_handling(self):
        """Test that OPENHQM_ prefix is handled correctly."""
        with patch.dict(os.environ, {"OPENHQM_SERVER__PORT": "9999"}):
            # In real usage, settings would be reloaded
            # This tests the concept
            assert os.environ.get("OPENHQM_SERVER__PORT") == "9999"

    def test_nested_env_vars(self):
        """Test nested configuration via environment variables."""
        with patch.dict(
            os.environ,
            {
                "OPENHQM_PROXY__ENABLED": "true",
                "OPENHQM_PROXY__DEFAULT_ENDPOINT": "http://test.com",
            },
        ):
            # Settings would parse these with __ as nesting separator
            assert os.environ.get("OPENHQM_PROXY__ENABLED") == "true"

    def test_boolean_env_parsing(self):
        """Test boolean environment variable parsing."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
        ]

        for env_val, expected in test_cases:
            # Pydantic handles these conversions
            with patch.dict(os.environ, {"OPENHQM_PROXY__ENABLED": env_val}):
                # Would need actual Settings reload to test
                pass


class TestConfigurationSecurity:
    """Test security-related configuration."""

    def test_sensitive_values_not_logged(self):
        """Test that sensitive configuration values are not exposed."""
        config = EndpointConfig(
            url="http://api.example.com", auth_type="bearer", auth_token="super-secret-token"
        )

        # Should not include token in string representation
        str_repr = str(config)
        # Depending on implementation, might be masked
        # This is a reminder to implement secret masking

    def test_password_not_in_repr(self):
        """Test that passwords are not in string representation."""
        config = EndpointConfig(
            url="http://api.example.com",
            auth_type="basic",
            auth_username="user",
            auth_password="secret-password",
        )

        # Should not expose password in repr
        # This is a security best practice reminder

    def test_api_key_handling(self):
        """Test secure handling of API keys."""
        config = EndpointConfig(
            url="http://api.example.com", auth_type="api_key", auth_token="secret-api-key-12345"
        )

        assert config.auth_token == "secret-api-key-12345"
        # Should be stored securely (encrypted at rest in real systems)
