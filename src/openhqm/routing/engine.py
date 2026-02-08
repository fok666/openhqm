"""Routing engine for message transformation and endpoint selection."""

import json
import re
from typing import Any

import structlog

from openhqm.exceptions import ConfigurationError, ProcessingError
from openhqm.routing.models import Route, RouteConfig, RoutingResult, TransformType
from openhqm.utils.helpers import get_nested_value

logger = structlog.get_logger(__name__)


class RoutingEngine:
    """Engine for routing messages to endpoints with payload transformation."""

    def __init__(self, config: RouteConfig):
        """Initialize routing engine with configuration.
        
        Args:
            config: Route configuration
        """
        self.config = config
        self._routes_sorted = sorted(
            [r for r in config.routes if r.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )
        
        # Try to import jq if any route uses it
        self._jq_available = False
        if any(r.transform_type == TransformType.JQ for r in self._routes_sorted):
            try:
                import pyjq
                self._jq = pyjq
                self._jq_available = True
            except ImportError:
                logger.warning(
                    "pyjq not installed, JQ transforms will not work. "
                    "Install with: pip install pyjq"
                )
        
        logger.info(
            "Routing engine initialized",
            route_count=len(self._routes_sorted),
            jq_available=self._jq_available,
        )

    def _match_route(self, route: Route, message: dict[str, Any]) -> bool:
        """Check if message matches route criteria.
        
        Args:
            route: Route to check
            message: Queue message
            
        Returns:
            True if message matches route
        """
        # Default route matches everything
        if route.is_default:
            return True
        
        # No match criteria - route matches everything
        if not route.match_field:
            return True
        
        # Get field value
        field_value = get_nested_value(message, route.match_field)
        if field_value is None:
            return False
        
        # Exact match
        if route.match_value:
            return str(field_value) == route.match_value
        
        # Pattern match
        if route.match_pattern:
            return bool(re.match(route.match_pattern, str(field_value)))
        
        return False

    def _apply_jq_transform(self, expression: str, data: dict[str, Any]) -> Any:
        """Apply JQ transformation.
        
        Args:
            expression: JQ expression
            data: Input data
            
        Returns:
            Transformed data
            
        Raises:
            ProcessingError: If transform fails
        """
        if not self._jq_available:
            raise ProcessingError(
                "JQ transform requested but pyjq is not installed. "
                "Install with: pip install pyjq"
            )
        
        try:
            # pyjq.all returns a list of results
            results = self._jq.all(expression, data)
            # Return first result, or empty dict if no results
            return results[0] if results else {}
        except Exception as e:
            logger.error("JQ transform failed", expression=expression, error=str(e))
            raise ProcessingError(f"JQ transform failed: {e}") from e

    def _apply_jsonpath_transform(self, expression: str, data: dict[str, Any]) -> Any:
        """Apply JSONPath transformation.
        
        Args:
            expression: JSONPath expression
            data: Input data
            
        Returns:
            Transformed data
            
        Raises:
            ProcessingError: If transform fails
        """
        try:
            from jsonpath_ng import parse
            
            jsonpath_expr = parse(expression)
            matches = [match.value for match in jsonpath_expr.find(data)]
            
            # Return single value or list
            if len(matches) == 1:
                return matches[0]
            return matches
        except ImportError:
            raise ProcessingError(
                "JSONPath transform requested but jsonpath-ng is not installed. "
                "Install with: pip install jsonpath-ng"
            )
        except Exception as e:
            logger.error("JSONPath transform failed", expression=expression, error=str(e))
            raise ProcessingError(f"JSONPath transform failed: {e}") from e

    def _apply_template_transform(self, template: str, data: dict[str, Any]) -> dict[str, Any]:
        """Apply template transformation using string substitution.
        
        Template uses {{field.path}} syntax for substitution.
        
        Args:
            template: JSON template string
            data: Input data
            
        Returns:
            Transformed data as dict
            
        Raises:
            ProcessingError: If transform fails
        """
        try:
            # Replace template variables
            result = template
            
            # Find all {{...}} patterns
            pattern = r'\{\{([^}]+)\}\}'
            matches = re.findall(pattern, template)
            
            for match in matches:
                field_path = match.strip()
                value = get_nested_value(data, field_path)
                
                # Convert value to JSON-safe string
                if value is not None:
                    if isinstance(value, (dict, list)):
                        value_str = json.dumps(value)
                    else:
                        # For strings, don't add extra quotes (template already has them)
                        value_str = str(value)
                else:
                    value_str = "null"
                
                result = result.replace(f"{{{{{match}}}}}", value_str)
            
            # Parse as JSON
            return json.loads(result)
        except Exception as e:
            logger.error("Template transform failed", template=template, error=str(e))
            raise ProcessingError(f"Template transform failed: {e}") from e

    def _transform_payload(
        self, route: Route, message: dict[str, Any]
    ) -> dict[str, Any]:
        """Transform message payload according to route configuration.
        
        Args:
            route: Route with transform configuration
            message: Queue message
            
        Returns:
            Transformed payload
        """
        # Passthrough - no transformation
        if route.transform_type == TransformType.PASSTHROUGH or not route.transform:
            return message.get("payload", message)
        
        # Apply transformation based on type
        if route.transform_type == TransformType.JQ:
            return self._apply_jq_transform(route.transform, message)
        
        elif route.transform_type == TransformType.JSONPATH:
            result = self._apply_jsonpath_transform(route.transform, message)
            # Ensure result is a dict
            if not isinstance(result, dict):
                return {"result": result}
            return result
        
        elif route.transform_type == TransformType.TEMPLATE:
            return self._apply_template_transform(route.transform, message)
        
        else:
            logger.warning("Unknown transform type", transform_type=route.transform_type)
            return message.get("payload", message)

    def _transform_headers(
        self, route: Route, message: dict[str, Any]
    ) -> dict[str, str]:
        """Transform message fields to HTTP headers.
        
        Args:
            route: Route with header mappings
            message: Queue message
            
        Returns:
            Dict of HTTP headers
        """
        headers = {}
        
        if not route.header_mappings:
            return headers
        
        for header_name, field_path in route.header_mappings.items():
            # Simple field path extraction
            value = get_nested_value(message, field_path)
            if value is not None:
                headers[header_name] = str(value)
        
        return headers

    def _transform_query_params(
        self, route: Route, message: dict[str, Any]
    ) -> dict[str, str]:
        """Transform message fields to query parameters.
        
        Args:
            route: Route with query param mappings
            message: Queue message
            
        Returns:
            Dict of query parameters
        """
        params = {}
        
        if not route.query_params:
            return params
        
        for param_name, field_path in route.query_params.items():
            value = get_nested_value(message, field_path)
            if value is not None:
                params[param_name] = str(value)
        
        return params

    def route(self, message: dict[str, Any]) -> RoutingResult:
        """Route message to endpoint with transformations.
        
        Args:
            message: Queue message with payload and metadata
            
        Returns:
            RoutingResult with endpoint and transformed data
            
        Raises:
            ConfigurationError: If routing fails due to config issues
            ProcessingError: If transformation fails
        """
        logger.info("Routing message", message_id=message.get("correlation_id"))
        
        # Find matching route
        matched_route = None
        for route in self._routes_sorted:
            if self._match_route(route, message):
                matched_route = route
                logger.info("Route matched", route_name=route.name)
                break
        
        # No match - use default
        if not matched_route:
            if self.config.enable_fallback and self.config.default_endpoint:
                logger.info("No route matched, using default endpoint")
                return RoutingResult(
                    route_name=None,
                    endpoint=self.config.default_endpoint,
                    payload=message.get("payload", message),
                )
            else:
                raise ConfigurationError("No matching route found and no default configured")
        
        # Apply transformations
        try:
            payload = self._transform_payload(matched_route, message)
            headers = self._transform_headers(matched_route, message)
            query_params = self._transform_query_params(matched_route, message)
            
            return RoutingResult(
                route_name=matched_route.name,
                endpoint=matched_route.endpoint,
                method=matched_route.method or "POST",
                payload=payload,
                headers=headers,
                query_params=query_params,
                timeout=matched_route.timeout,
                max_retries=matched_route.max_retries,
            )
        except Exception as e:
            logger.error(
                "Routing failed",
                route_name=matched_route.name,
                error=str(e),
            )
            raise

    @classmethod
    def from_file(cls, file_path: str) -> "RoutingEngine":
        """Load routing configuration from YAML or JSON file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            RoutingEngine instance
        """
        import yaml
        from pathlib import Path
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Routing config file not found: {file_path}")
        
        content = path.read_text()
        
        if path.suffix in [".yaml", ".yml"]:
            config_dict = yaml.safe_load(content)
        elif path.suffix == ".json":
            config_dict = json.loads(content)
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")
        
        config = RouteConfig(**config_dict)
        return cls(config)

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "RoutingEngine":
        """Create routing engine from dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            RoutingEngine instance
        """
        config = RouteConfig(**config_dict)
        return cls(config)
