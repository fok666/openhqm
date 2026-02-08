"""Data models for routing configuration."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TransformType(str, Enum):
    """Type of payload transformation."""

    JQ = "jq"
    JSONPATH = "jsonpath"
    TEMPLATE = "template"
    PASSTHROUGH = "passthrough"


class Route(BaseModel):
    """Configuration for a single route.
    
    A route defines how to transform an incoming queue message
    to an HTTP request for a backend endpoint.
    """

    name: str = Field(..., description="Unique route name")
    description: str | None = Field(default=None, description="Route description")
    
    # Matching criteria
    match_field: str | None = Field(
        default=None, description="Message field to match on (e.g., 'metadata.type')"
    )
    match_value: str | None = Field(
        default=None, description="Value to match for routing"
    )
    match_pattern: str | None = Field(
        default=None, description="Regex pattern to match"
    )
    is_default: bool = Field(default=False, description="Use as default route if no match")
    priority: int = Field(default=0, description="Route priority (higher = first)")
    
    # Target endpoint
    endpoint: str = Field(..., description="Target endpoint name from proxy config")
    
    # Transformation
    transform_type: TransformType = Field(
        default=TransformType.PASSTHROUGH,
        description="Type of payload transformation",
    )
    transform: str | None = Field(
        default=None,
        description="JQ expression, JSONPath, or template for transformation",
    )
    
    # HTTP method override
    method: str | None = Field(default=None, description="HTTP method override (GET, POST, etc.)")
    
    # Header transformations
    header_mappings: dict[str, str] | None = Field(
        default=None,
        description="Map queue message fields to HTTP headers using JQ or templates",
    )
    
    # Query parameter transformations
    query_params: dict[str, str] | None = Field(
        default=None,
        description="Map queue message fields to query parameters",
    )
    
    # Conditional routing
    enabled: bool = Field(default=True, description="Enable/disable this route")
    
    # Retry and timeout overrides
    timeout: int | None = Field(default=None, description="Override endpoint timeout")
    max_retries: int | None = Field(default=None, description="Override max retries")


class RouteConfig(BaseModel):
    """Collection of routes with global settings."""

    version: str = Field(default="1.0", description="Configuration version")
    routes: list[Route] = Field(default_factory=list, description="List of routes")
    default_endpoint: str | None = Field(
        default=None,
        description="Default endpoint if no route matches",
    )
    enable_fallback: bool = Field(
        default=True,
        description="Allow fallback to default endpoint on match failure",
    )


class RoutingResult(BaseModel):
    """Result of routing and transformation."""

    route_name: str | None = Field(default=None, description="Matched route name")
    endpoint: str = Field(..., description="Target endpoint")
    method: str = Field(default="POST", description="HTTP method")
    payload: dict[str, Any] = Field(..., description="Transformed payload")
    headers: dict[str, str] = Field(default_factory=dict, description="Additional headers")
    query_params: dict[str, str] = Field(
        default_factory=dict, description="Query parameters"
    )
    timeout: int | None = Field(default=None, description="Timeout override")
    max_retries: int | None = Field(default=None, description="Max retries override")
