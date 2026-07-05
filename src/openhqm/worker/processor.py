"""Forward queued requests to the backend over HTTP (queue-to-http mode)."""

import base64
from typing import Any

import aiohttp
import structlog

from openhqm.config.settings import settings
from openhqm.exceptions import FatalError, ProcessingError, RetryableError

logger = structlog.get_logger(__name__)


class MessageProcessor:
    """Forward a message's payload to the configured backend as a reverse proxy."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=settings.proxy.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _auth_headers(self) -> dict[str, str]:
        """Build auth headers from proxy configuration."""
        p = settings.proxy
        if p.auth_type == "bearer" and p.auth_token:
            return {"Authorization": f"Bearer {p.auth_token}"}
        if p.auth_type == "api_key" and p.auth_token:
            return {p.auth_header_name or "X-API-Key": p.auth_token}
        if p.auth_type == "basic" and p.auth_username and p.auth_password:
            creds = base64.b64encode(f"{p.auth_username}:{p.auth_password}".encode()).decode()
            return {"Authorization": f"Basic {creds}"}
        if p.auth_type == "custom" and p.auth_token and p.auth_header_name:
            return {p.auth_header_name: p.auth_token}
        return {}

    def _merge_headers(self, request_headers: dict[str, str] | None) -> dict[str, str]:
        """Merge static + forwarded client + auth headers (auth wins)."""
        headers: dict[str, str] = dict(settings.proxy.headers or {})

        forward = {h.lower() for h in settings.proxy.forward_headers}
        strip = {h.lower() for h in settings.proxy.strip_headers}
        for key, value in (request_headers or {}).items():
            key_lower = key.lower()
            if (key_lower in forward or "*" in forward) and key_lower not in strip:
                headers[key] = value

        headers.update(self._auth_headers())
        return headers

    async def process(
        self,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], int, dict[str, str]]:
        """Forward the payload to the backend and return (body, status, headers).

        Raises:
            ProcessingError: if no backend is configured or the request fails.
        """
        url = settings.proxy.backend_url
        if not url:
            raise FatalError("No backend_url configured (set OPENHQM_PROXY__BACKEND_URL)")

        metadata = metadata or {}
        method = (metadata.get("method") or settings.proxy.method or "POST").upper()
        merged_headers = self._merge_headers(headers)
        session = await self._get_session()

        logger.info("Proxying request", url=url, method=method)

        try:
            async with session.request(
                method=method, url=url, json=payload, headers=merged_headers
            ) as response:
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    body = await response.json()
                else:
                    body = {"response": await response.text(), "content_type": content_type}

                resp_headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ("transfer-encoding", "connection")
                }
                logger.info("Request proxied", url=url, status=response.status)
                return body, response.status, dict(resp_headers)

        except aiohttp.ClientError as e:
            raise ProcessingError(f"Failed to proxy request: {e}") from e
        except TimeoutError:
            raise ProcessingError("Request timeout") from None
