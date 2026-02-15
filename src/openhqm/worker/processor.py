"""Message processor for proxying requests to configured endpoints."""

import base64
from typing import Any

import aiohttp
import structlog

from openhqm.config.settings import EndpointConfig, settings
from openhqm.exceptions import ConfigurationError, ProcessingError
from openhqm.partitioning.manager import PartitionManager
from openhqm.routing.engine import RoutingEngine

logger = structlog.get_logger(__name__)


class MessageProcessor:
    """Process messages by forwarding to configured endpoints as reverse proxy."""

    def __init__(self, worker_id: str | None = None):
        """Initialize the processor.

        Args:
            worker_id: Unique worker identifier for partitioning
        """
        self._session: aiohttp.ClientSession | None = None
        self._routing_engine: RoutingEngine | None = None
        self._partition_manager: PartitionManager | None = None

        # Initialize routing engine if enabled
        if settings.routing.enabled:
            self._init_routing_engine()

        # Initialize partition manager if enabled
        if settings.partitioning.enabled and worker_id:
            self._partition_manager = PartitionManager(settings.partitioning, worker_id)
            logger.info("Partition manager initialized", worker_id=worker_id)

    def _init_routing_engine(self):
        """Initialize routing engine from configuration."""
        try:
            if settings.routing.config_path:
                self._routing_engine = RoutingEngine.from_file(settings.routing.config_path)
                logger.info("Routing engine loaded from file", path=settings.routing.config_path)
            elif settings.routing.config_dict:
                self._routing_engine = RoutingEngine.from_dict(settings.routing.config_dict)
                logger.info("Routing engine loaded from inline config")
            else:
                logger.warning("Routing enabled but no configuration provided")
        except Exception as e:
            logger.error("Failed to initialize routing engine", error=str(e))
            raise ConfigurationError(f"Routing initialization failed: {e}") from e

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=settings.worker.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()

        # Cleanup expired sessions if partitioning is enabled
        if self._partition_manager:
            self._partition_manager.cleanup_expired_sessions()

    def _example_process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Example processing logic for testing when proxy mode is disabled."""
        from datetime import datetime

        operation = payload.get("operation", "unknown")
        data = payload.get("data", "")

        if operation == "echo":
            output = data
        elif operation == "uppercase":
            output = str(data).upper()
        elif operation == "reverse":
            output = str(data)[::-1]
        elif operation == "error":
            raise ValueError("Test error")
        else:
            output = f"Unknown operation: {operation}"

        return {
            "output": output,
            "processed_at": datetime.utcnow().isoformat(),
        }

    def _prepare_auth_headers(self, endpoint_config: EndpointConfig) -> dict[str, str]:
        """Prepare authentication headers based on endpoint configuration."""
        headers = {}

        if endpoint_config.auth_type == "bearer" and endpoint_config.auth_token:
            headers["Authorization"] = f"Bearer {endpoint_config.auth_token}"

        elif endpoint_config.auth_type == "api_key" and endpoint_config.auth_token:
            header_name = endpoint_config.auth_header_name or "X-API-Key"
            headers[header_name] = endpoint_config.auth_token

        elif endpoint_config.auth_type == "basic":
            if endpoint_config.auth_username and endpoint_config.auth_password:
                credentials = f"{endpoint_config.auth_username}:{endpoint_config.auth_password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"

        elif endpoint_config.auth_type == "custom":
            if endpoint_config.auth_token and endpoint_config.auth_header_name:
                headers[endpoint_config.auth_header_name] = endpoint_config.auth_token

        return headers

    def _merge_headers(
        self,
        endpoint_config: EndpointConfig,
        request_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Merge headers from configuration and request."""
        headers = {}

        # Start with static headers from config
        if endpoint_config.headers:
            headers.update(endpoint_config.headers)

        # Add authentication headers
        auth_headers = self._prepare_auth_headers(endpoint_config)
        headers.update(auth_headers)

        # Add forwarded headers from request (if allowed)
        if request_headers:
            forward_list = settings.proxy.forward_headers
            strip_list = settings.proxy.strip_headers

            for key, value in request_headers.items():
                # Check if header should be forwarded
                if key in forward_list or "*" in forward_list:
                    # Check if header should be stripped
                    if key not in strip_list:
                        headers[key] = value

        return headers

    def _get_endpoint_config(self, endpoint_name: str | None = None) -> EndpointConfig:
        """Get endpoint configuration by name or default."""
        if not settings.proxy.enabled:
            return None  # Allow fallback to example processing

        # Use named endpoint if specified
        if endpoint_name:
            if endpoint_name not in settings.proxy.endpoints:
                raise ConfigurationError(f"Endpoint '{endpoint_name}' not found in configuration")
            return settings.proxy.endpoints[endpoint_name]

        # Use default endpoint
        if settings.proxy.default_endpoint:
            if settings.proxy.default_endpoint in settings.proxy.endpoints:
                return settings.proxy.endpoints[settings.proxy.default_endpoint]
            else:
                # Create config from default URL
                return EndpointConfig(url=settings.proxy.default_endpoint)

        # No endpoint specified
        raise ConfigurationError("No endpoint specified and no default endpoint configured")

    def set_partition_assignments(self, partitions: set[int]):
        """Set which partitions this worker should process."""
        if self._partition_manager:
            self._partition_manager.set_assigned_partitions(partitions)
            logger.info("Partition assignments updated", partitions=sorted(partitions))

    def get_partition_stats(self) -> dict[str, Any]:
        """Get partition manager statistics."""
        if not self._partition_manager:
            return {"partitioning_enabled": False}
        return self._partition_manager.get_stats()

    async def process(
        self,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        full_message: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], int, dict[str, str]]:
        """
        Process message by forwarding to configured endpoint.

        Args:
            payload: Request payload (will be sent as JSON body)
            metadata: Request metadata (contains endpoint, method overrides)
            headers: Headers to forward from original request
            full_message: Complete queue message for routing/partitioning

        Returns:
            Tuple of (response_body, status_code, response_headers)

        Raises:
            ConfigurationError: If endpoint configuration is invalid
            ProcessingError: If the request fails
        """
        metadata = metadata or {}

        # Check partitioning - skip if not assigned to this worker
        if self._partition_manager and full_message:
            should_process = self._partition_manager.should_process_message(full_message)
            if not should_process:
                logger.debug("Message skipped - not assigned to this partition")
                # Return empty response to acknowledge message without processing
                return {"skipped": True, "reason": "partition_not_assigned"}, 200, {}

        # Apply routing if enabled
        endpoint_name = metadata.get("endpoint")
        method = metadata.get("method")

        if self._routing_engine and full_message:
            routing_result = self._routing_engine.route_message(full_message)
            if routing_result:
                # Use routing result
                payload = routing_result.transformed_payload
                endpoint_name = routing_result.endpoint
                method = routing_result.method or method

                # Merge mapped headers
                if routing_result.headers and headers:
                    headers = {**headers, **routing_result.headers}
                elif routing_result.headers:
                    headers = routing_result.headers

                logger.info(
                    "Message routed",
                    route_name=routing_result.route_name,
                    endpoint=endpoint_name,
                    method=method,
                )

        logger.info(
            "Proxying request",
            endpoint=endpoint_name,
            method=method,
            payload_size=len(str(payload)),
        )

        # Get endpoint configuration
        endpoint_config = self._get_endpoint_config(endpoint_name)

        # Fallback to example processing if proxy is disabled
        if endpoint_config is None:
            return self._example_process(payload)

        # Determine HTTP method
        http_method = (method or endpoint_config.method or "POST").upper()

        # Merge headers
        merged_headers = self._merge_headers(endpoint_config, headers)

        # Get HTTP session
        session = await self._get_session()

        try:
            # Make the request
            async with session.request(
                method=http_method,
                url=endpoint_config.url,
                json=payload,
                headers=merged_headers,
                timeout=aiohttp.ClientTimeout(total=endpoint_config.timeout),
            ) as response:
                # Read response
                content_type = response.headers.get("Content-Type", "")

                if "application/json" in content_type:
                    response_body = await response.json()
                else:
                    text = await response.text()
                    response_body = {"response": text, "content_type": content_type}

                # Filter response headers
                response_headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ["transfer-encoding", "connection"]
                }

                logger.info(
                    "Request proxied successfully",
                    endpoint=endpoint_name,
                    status=response.status,
                    response_size=len(str(response_body)),
                )

                return response_body, response.status, dict(response_headers)

        except aiohttp.ClientError as e:
            logger.error("HTTP client error", endpoint=endpoint_name, error=str(e))
            raise ProcessingError(f"Failed to proxy request: {e}") from e
        except TimeoutError:
            logger.error("Request timeout", endpoint=endpoint_name)
            raise ProcessingError("Request timeout") from None
        except Exception as e:
            logger.exception("Unexpected error during proxying", endpoint=endpoint_name)
            raise ProcessingError(f"Unexpected error: {e}") from e
