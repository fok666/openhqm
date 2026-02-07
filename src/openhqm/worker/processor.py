"""Message processor for proxying requests to configured endpoints."""

import base64
from typing import Any

import aiohttp
import structlog

from openhqm.config.settings import EndpointConfig, settings
from openhqm.exceptions import ConfigurationError, ProcessingError

logger = structlog.get_logger(__name__)


class MessageProcessor:
    """Process messages by forwarding to configured endpoints as reverse proxy."""

    def __init__(self):
        """Initialize the processor."""
        self._session: aiohttp.ClientSession | None = None

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
