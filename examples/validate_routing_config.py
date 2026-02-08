#!/usr/bin/env python3
"""
Validate OpenHQM Routing Configuration

This script validates routing configuration files before deployment.
It checks:
- YAML syntax and structure
- Required fields
- JQ expression syntax
- Regex patterns
- Priority conflicts
- Endpoint definitions
- Header and query parameter mappings

Usage:
    python validate_routing_config.py routing-config.yaml
    python validate_routing_config.py k8s-routing-configmap.yaml

Exit codes:
    0 - Configuration is valid
    1 - Validation errors found
    2 - File not found or invalid YAML
"""

import sys
import yaml
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path


class ConfigValidator:
    """Validates OpenHQM routing configuration."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self) -> bool:
        """Run all validation checks."""
        self._validate_version()
        self._validate_routes()
        self._validate_default_settings()
        return len(self.errors) == 0

    def _validate_version(self):
        """Validate configuration version."""
        if 'version' not in self.config:
            self.errors.append("Missing required field 'version'")
            return

        version = self.config['version']
        if not isinstance(version, str):
            self.errors.append(f"Version must be a string, got {type(version)}")
        elif version not in ['1.0']:
            self.warnings.append(f"Unknown version '{version}', expected '1.0'")

    def _validate_routes(self):
        """Validate all routes."""
        if 'routes' not in self.config:
            self.errors.append("Missing required field 'routes'")
            return

        routes = self.config['routes']
        if not isinstance(routes, list):
            self.errors.append(f"'routes' must be a list, got {type(routes)}")
            return

        if len(routes) == 0:
            self.warnings.append("No routes defined")
            return

        # Track route names and priorities
        route_names = set()
        priorities = {}

        for idx, route in enumerate(routes):
            route_id = f"routes[{idx}]"
            self._validate_route(route, route_id)

            # Check for duplicate names
            name = route.get('name')
            if name:
                if name in route_names:
                    self.errors.append(f"{route_id}: Duplicate route name '{name}'")
                route_names.add(name)

                # Check priority conflicts
                priority = route.get('priority', 0)
                if priority in priorities:
                    self.warnings.append(
                        f"{route_id}: Route '{name}' has same priority {priority} "
                        f"as '{priorities[priority]}'"
                    )
                priorities[priority] = name

    def _validate_route(self, route: Dict[str, Any], route_id: str):
        """Validate a single route."""
        # Required fields
        required_fields = ['name', 'endpoint']
        for field in required_fields:
            if field not in route:
                self.errors.append(f"{route_id}: Missing required field '{field}'")

        # Validate name
        if 'name' in route:
            name = route['name']
            if not isinstance(name, str) or not name.strip():
                self.errors.append(f"{route_id}: Invalid route name")
            elif not re.match(r'^[a-z0-9-]+$', name):
                self.warnings.append(
                    f"{route_id}: Route name '{name}' should use lowercase "
                    "alphanumeric and hyphens only"
                )

        # Validate matching criteria
        self._validate_match_criteria(route, route_id)

        # Validate transform
        self._validate_transform(route, route_id)

        # Validate endpoint
        if 'endpoint' in route:
            endpoint = route['endpoint']
            if not isinstance(endpoint, str) or not endpoint.strip():
                self.errors.append(f"{route_id}: Invalid endpoint")

        # Validate method
        if 'method' in route:
            method = route['method']
            valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
            if method not in valid_methods:
                self.errors.append(
                    f"{route_id}: Invalid HTTP method '{method}', "
                    f"must be one of {valid_methods}"
                )

        # Validate priority
        if 'priority' in route:
            priority = route['priority']
            if not isinstance(priority, int) or priority < 0:
                self.errors.append(f"{route_id}: Priority must be a non-negative integer")

        # Validate timeout
        if 'timeout' in route:
            timeout = route['timeout']
            if not isinstance(timeout, int) or timeout <= 0:
                self.errors.append(f"{route_id}: Timeout must be a positive integer")

        # Validate max_retries
        if 'max_retries' in route:
            retries = route['max_retries']
            if not isinstance(retries, int) or retries < 0:
                self.errors.append(f"{route_id}: max_retries must be a non-negative integer")

        # Validate header mappings
        if 'header_mappings' in route:
            self._validate_header_mappings(route['header_mappings'], route_id)

        # Validate query params
        if 'query_params' in route:
            self._validate_query_params(route['query_params'], route_id)

    def _validate_match_criteria(self, route: Dict[str, Any], route_id: str):
        """Validate route matching criteria."""
        has_match_field = 'match_field' in route
        has_match_value = 'match_value' in route
        has_match_pattern = 'match_pattern' in route
        is_default = route.get('is_default', False)

        if is_default:
            if has_match_field or has_match_value or has_match_pattern:
                self.warnings.append(
                    f"{route_id}: Default route should not have match criteria"
                )
            return

        if not has_match_field:
            self.errors.append(f"{route_id}: Missing 'match_field' or 'is_default'")
            return

        if not has_match_value and not has_match_pattern:
            self.errors.append(
                f"{route_id}: Must specify either 'match_value' or 'match_pattern'"
            )

        if has_match_value and has_match_pattern:
            self.errors.append(
                f"{route_id}: Cannot specify both 'match_value' and 'match_pattern'"
            )

        # Validate regex pattern
        if has_match_pattern:
            pattern = route['match_pattern']
            try:
                re.compile(pattern)
            except re.error as e:
                self.errors.append(f"{route_id}: Invalid regex pattern: {e}")

    def _validate_transform(self, route: Dict[str, Any], route_id: str):
        """Validate transformation configuration."""
        transform_type = route.get('transform_type', 'passthrough')
        valid_types = ['jq', 'template', 'jsonpath', 'passthrough']

        if transform_type not in valid_types:
            self.errors.append(
                f"{route_id}: Invalid transform_type '{transform_type}', "
                f"must be one of {valid_types}"
            )

        if transform_type == 'passthrough':
            if 'transform' in route:
                self.warnings.append(
                    f"{route_id}: transform field ignored for passthrough type"
                )
            return

        if 'transform' not in route:
            self.errors.append(
                f"{route_id}: Missing 'transform' field for type '{transform_type}'"
            )
            return

        transform = route['transform']
        if not isinstance(transform, str) or not transform.strip():
            self.errors.append(f"{route_id}: transform must be a non-empty string")
            return

        # Validate based on type
        if transform_type == 'jq':
            self._validate_jq_expression(transform, route_id)
        elif transform_type == 'jsonpath':
            self._validate_jsonpath_expression(transform, route_id)
        elif transform_type == 'template':
            self._validate_template(transform, route_id)

    def _validate_jq_expression(self, expression: str, route_id: str):
        """Validate JQ expression syntax."""
        # Basic validation - check for common syntax errors
        if not expression.strip():
            self.errors.append(f"{route_id}: Empty JQ expression")
            return

        # Check for balanced braces
        if expression.count('{') != expression.count('}'):
            self.warnings.append(f"{route_id}: Unbalanced braces in JQ expression")

        if expression.count('[') != expression.count(']'):
            self.warnings.append(f"{route_id}: Unbalanced brackets in JQ expression")

        # Check if expression is valid JSON (object or array)
        try:
            json.loads(expression)
            self.warnings.append(
                f"{route_id}: JQ expression is static JSON, not a transformation"
            )
        except json.JSONDecodeError:
            pass  # Expected for valid JQ expressions

    def _validate_jsonpath_expression(self, expression: str, route_id: str):
        """Validate JSONPath expression."""
        if not expression.startswith('$'):
            self.errors.append(
                f"{route_id}: JSONPath expression must start with '$'"
            )

    def _validate_template(self, template: str, route_id: str):
        """Validate template syntax."""
        # Check for balanced template variables
        opens = template.count('{{')
        closes = template.count('}}')
        if opens != closes:
            self.errors.append(f"{route_id}: Unbalanced template variables")

        # Extract and validate template variables
        variables = re.findall(r'\{\{([^}]+)\}\}', template)
        for var in variables:
            var = var.strip()
            if not var:
                self.errors.append(f"{route_id}: Empty template variable")
            elif not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', var):
                self.warnings.append(
                    f"{route_id}: Template variable '{var}' has unusual format"
                )

    def _validate_header_mappings(self, mappings: Dict[str, str], route_id: str):
        """Validate header mappings."""
        if not isinstance(mappings, dict):
            self.errors.append(f"{route_id}: header_mappings must be a dictionary")
            return

        for header_name, field_path in mappings.items():
            if not isinstance(header_name, str) or not header_name.strip():
                self.errors.append(f"{route_id}: Invalid header name")

            if not isinstance(field_path, str) or not field_path.strip():
                self.errors.append(f"{route_id}: Invalid field path for header '{header_name}'")

            # Validate header name format
            if not re.match(r'^[A-Za-z0-9-]+$', header_name):
                self.warnings.append(
                    f"{route_id}: Header name '{header_name}' contains unusual characters"
                )

    def _validate_query_params(self, params: Dict[str, str], route_id: str):
        """Validate query parameters."""
        if not isinstance(params, dict):
            self.errors.append(f"{route_id}: query_params must be a dictionary")
            return

        for param_name, field_path in params.items():
            if not isinstance(param_name, str) or not param_name.strip():
                self.errors.append(f"{route_id}: Invalid query parameter name")

            if not isinstance(field_path, str) or not field_path.strip():
                self.errors.append(
                    f"{route_id}: Invalid field path for query param '{param_name}'"
                )

    def _validate_default_settings(self):
        """Validate default settings."""
        if 'default_endpoint' in self.config:
            endpoint = self.config['default_endpoint']
            if not isinstance(endpoint, str) or not endpoint.strip():
                self.errors.append("Invalid default_endpoint")

        if 'enable_fallback' in self.config:
            fallback = self.config['enable_fallback']
            if not isinstance(fallback, bool):
                self.errors.append("enable_fallback must be a boolean")

    def print_results(self):
        """Print validation results."""
        if self.errors:
            print("\n❌ Validation Errors:")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print("\n⚠️  Warnings:")
            for warning in self.warnings:
                print(f"  • {warning}")

        if not self.errors and not self.warnings:
            print("✅ Configuration is valid!")
        elif not self.errors:
            print(f"\n✅ Configuration is valid (with {len(self.warnings)} warnings)")
        else:
            print(f"\n❌ Validation failed with {len(self.errors)} errors")


def load_config(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load and parse configuration file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Check if it's a Kubernetes ConfigMap
        docs = list(yaml.safe_load_all(content))

        for doc in docs:
            if doc and doc.get('kind') == 'ConfigMap':
                # Extract routing config from ConfigMap
                if 'data' in doc and 'routing.yaml' in doc['data']:
                    print(f"📋 Extracting routing config from ConfigMap")
                    return yaml.safe_load(doc['data']['routing.yaml'])

        # If not a ConfigMap, return first document
        return docs[0] if docs else None

    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
        return None
    except yaml.YAMLError as e:
        print(f"❌ Error: Invalid YAML: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python validate_routing_config.py <config-file>")
        sys.exit(2)

    file_path = Path(sys.argv[1])
    print(f"🔍 Validating: {file_path}")

    config = load_config(file_path)
    if config is None:
        sys.exit(2)

    validator = ConfigValidator(config)
    is_valid = validator.validate()
    validator.print_results()

    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
