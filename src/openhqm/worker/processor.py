"""Message processor for proxying requests to configured endpoints."""

import base64
from typing import Any

import aiohttp
import structlog

from openhqm.config.settings import EndpointConfig, settings
from openhqm.exceptions import ConfigurationError, ProcessingError
from openhqm.routing.engine import RoutingEngine
from openhqm.partitioning.manager import PartitionManager

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
        
        # Initialize routing  and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        
        # Cleanup expired sessions if partitioning is enabled
        if self._partition_manager:
            self._partition_manager.cleanup_expired_sessions()
        
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
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

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
        full_message = full_message or {"payload": payload, "metadata": metadata}
        
        # Check if partitioning is enabled and if we should process this message
        if self._partition_manager:
            if not self._partition_manager.should_process_message(full_message):
                logger.info(
                    "Message skipped due to partition assignment",
                    correlation_id=full_message.get("correlation_id"),
                    partition_id=self._partition_manager.get_partition_for_message(full_message),
                )
                raise ProcessingError("Message assigned to different partition")
            
            # Track session activity
            self._partition_manager.track_session(full_message)
        
        # Use routing engine if enabled
        if self._routing_engine:
            routing_result = self._routing_engine.route(full_message)
            
            endpoint_name = routing_result.endpoint
        
        # Build URL with query params if provided
        url = endpoint_config.url
        query_params = metadata.get("query_params")
        if query_params:
            from urllib.parse import urlencode
            query_string = urlencode(query_params)
            url = f"{url}?{query_string}"
            method = routing_result.method
            payload = routing_result.payload
            
            # Merge routing headers with request headers
            if routing_result.headers:
                headers = headers or {}
                headers.update(routing_result.headers)
            
            # Override metadata with routing results
            metadata = metadata.copy()
            metadata["endpoint"] = endpoint_name
            if routing_result.timeout:
                metadata["timeout"] = routing_result.timeout
            if routing_result.max_retries:
                metadata["max_retries"] = routing_result.max_retries
            
            # Add query params to metadata for URL construction
            if routing_result.query_params:
                metadata["query_params"] = routing_result.query_params
            
            logger.info(
                "Message routed",
                route_name=routing_result.route_name,
                endpoint=endpoint_name,
                method=method,
            )
        else:
            endpoint_name = metadata.get("endpoint")
                return settings.proxy.endpoints[endpoint_name]
Get timeout from metadata or endpoint config
            timeout_seconds = metadata.get("timeout") or endpoint_config.timeout
            
            # Make the request
            async with session.request(
                method=http_method,
                url=url,
                json=payload,
                headers=merged_headers,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds
                return EndpointConfig(url=settings.proxy.default_endpoint)

        # No endpoint specified
        raise ConfigurationError("No endpoint specified and no default endpoint configured")

    async def process(
        self,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], int, dict[str, str]]:
        """
        Process message by forwarding to configured endpoint.

        Args:
            payload: Request payload (will be sent as JSON body)
            metadata: Request metadata (contains endpoint, method overrides)
            headers: Headers to forward from original request

        Returns:
            Tuple of (response_body, status_code, response_headers)

        Raises:
            ConfigurationError: If endpoint configuration is invalid
            ProcessingError: If the request fails
        """
        metadata = metadata or {}
        endpoint_name = metadata.get("endpoint")
        method = metadata.get("method")

        logger.info(
            "Proxying request",
    
    def set_partition_assignments(self, worker_count: int, worker_index: int):
        """Set partition assignments for this worker.
        
        Args:
            worker_count: Total number of workers
            worker_index: This worker's index (0-based)
        """
        if self._partition_manager:
            self._partition_manager.assign_worker_partitions(worker_count, worker_index)
    
    def get_partition_stats(self) -> dict[str, Any] | None:
        """Get partition statistics.
        
        Returns:
            Dict with partition stats or None if partitioning disabled
        """
        if self._partition_manager:
            return self._partition_manager.get_session_stats()
        return None
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
