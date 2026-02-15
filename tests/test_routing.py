"""Tests for routing engine."""

from openhqm.routing.engine import RoutingEngine
from openhqm.routing.models import Route, RouteConfig, TransformType


def test_passthrough_transform():
    """Test passthrough transformation."""
    config = RouteConfig(
        routes=[
            Route(
                name="test",
                endpoint="test-service",
                transform_type=TransformType.PASSTHROUGH,
            )
        ]
    )
    engine = RoutingEngine(config)

    message = {
        "correlation_id": "test-123",
        "payload": {"foo": "bar"},
    }

    result = engine.route(message)
    assert result.endpoint == "test-service"
    assert result.payload == {"foo": "bar"}


def test_template_transform():
    """Test template transformation."""
    config = RouteConfig(
        routes=[
            Route(
                name="test",
                endpoint="test-service",
                transform_type=TransformType.TEMPLATE,
                transform='{"user": "{{payload.username}}", "id": "{{correlation_id}}"}',
            )
        ]
    )
    engine = RoutingEngine(config)

    message = {
        "correlation_id": "test-123",
        "payload": {"username": "alice"},
    }

    result = engine.route(message)
    assert result.payload == {"user": "alice", "id": "test-123"}


def test_route_matching_by_value():
    """Test route matching by field value."""
    config = RouteConfig(
        routes=[
            Route(
                name="user-route",
                match_field="metadata.type",
                match_value="user",
                endpoint="user-service",
                priority=10,
            ),
            Route(
                name="order-route",
                match_field="metadata.type",
                match_value="order",
                endpoint="order-service",
                priority=10,
            ),
        ]
    )
    engine = RoutingEngine(config)

    message = {
        "correlation_id": "test-123",
        "payload": {},
        "metadata": {"type": "user"},
    }

    result = engine.route(message)
    assert result.endpoint == "user-service"


def test_route_matching_by_pattern():
    """Test route matching by regex pattern."""
    config = RouteConfig(
        routes=[
            Route(
                name="notification-route",
                match_field="metadata.type",
                match_pattern=r"^notification\.",
                endpoint="notification-service",
            ),
        ]
    )
    engine = RoutingEngine(config)

    message = {
        "correlation_id": "test-123",
        "payload": {},
        "metadata": {"type": "notification.email"},
    }

    result = engine.route(message)
    assert result.endpoint == "notification-service"


def test_default_route():
    """Test default route fallback."""
    config = RouteConfig(
        routes=[
            Route(
                name="default",
                is_default=True,
                endpoint="default-service",
            ),
        ]
    )
    engine = RoutingEngine(config)

    message = {
        "correlation_id": "test-123",
        "payload": {},
        "metadata": {"type": "unknown"},
    }

    result = engine.route(message)
    assert result.endpoint == "default-service"


def test_header_mappings():
    """Test header mappings."""
    config = RouteConfig(
        routes=[
            Route(
                name="test",
                endpoint="test-service",
                header_mappings={
                    "X-User-ID": "payload.user_id",
                    "X-Correlation-ID": "correlation_id",
                },
            ),
        ]
    )
    engine = RoutingEngine(config)

    message = {
        "correlation_id": "test-123",
        "payload": {"user_id": "user-456"},
    }

    result = engine.route(message)
    assert result.headers == {
        "X-User-ID": "user-456",
        "X-Correlation-ID": "test-123",
    }


def test_query_params():
    """Test query parameter mappings."""
    config = RouteConfig(
        routes=[
            Route(
                name="test",
                endpoint="test-service",
                query_params={
                    "user": "payload.username",
                    "session": "metadata.session_id",
                },
            ),
        ]
    )
    engine = RoutingEngine(config)

    message = {
        "correlation_id": "test-123",
        "payload": {"username": "alice"},
        "metadata": {"session_id": "sess-789"},
    }

    result = engine.route(message)
    assert result.query_params == {
        "user": "alice",
        "session": "sess-789",
    }


def test_priority_based_routing():
    """Test priority-based route selection."""
    config = RouteConfig(
        routes=[
            Route(
                name="low-priority",
                match_field="metadata.type",
                match_value="test",
                endpoint="low-service",
                priority=1,
            ),
            Route(
                name="high-priority",
                match_field="metadata.type",
                match_value="test",
                endpoint="high-service",
                priority=10,
            ),
        ]
    )
    engine = RoutingEngine(config)

    message = {
        "correlation_id": "test-123",
        "payload": {},
        "metadata": {"type": "test"},
    }

    result = engine.route(message)
    # Higher priority should match first
    assert result.endpoint == "high-service"
