"""Tests for the queue-to-http MessageProcessor (reverse proxy)."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from openhqm.exceptions import ProcessingError
from openhqm.worker.processor import MessageProcessor


def _proxy(**overrides):
    """Build a mock proxy settings object with sane defaults."""
    proxy = MagicMock()
    proxy.backend_url = "http://backend:8080"
    proxy.method = ""
    proxy.timeout = 30
    proxy.headers = None
    proxy.auth_type = None
    proxy.auth_token = None
    proxy.auth_username = None
    proxy.auth_password = None
    proxy.auth_header_name = None
    proxy.forward_headers = ["Content-Type", "Accept", "User-Agent"]
    proxy.strip_headers = ["Host", "Connection"]
    for key, value in overrides.items():
        setattr(proxy, key, value)
    return proxy


def _mock_response(status=200, json_body=None, content_type="application/json", text=""):
    resp = MagicMock()
    resp.status = status
    resp.headers = {"Content-Type": content_type}
    resp.json = AsyncMock(return_value=json_body or {})
    resp.text = AsyncMock(return_value=text)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_proxy_success():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy()
        processor = MessageProcessor()

        session = MagicMock()
        session.request = MagicMock(return_value=_mock_response(json_body={"ok": True}))
        processor._get_session = AsyncMock(return_value=session)

        body, status, headers = await processor.process({"data": "x"})

        assert body == {"ok": True}
        assert status == 200
        # POST is the default method when neither config nor metadata override it
        assert session.request.call_args.kwargs["method"] == "POST"


@pytest.mark.asyncio
async def test_proxy_no_backend_raises():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy(backend_url="")
        with pytest.raises(ProcessingError, match="No backend_url"):
            await MessageProcessor().process({"data": "x"})


@pytest.mark.asyncio
async def test_proxy_method_override_from_metadata():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy()
        processor = MessageProcessor()
        session = MagicMock()
        session.request = MagicMock(return_value=_mock_response())
        processor._get_session = AsyncMock(return_value=session)

        await processor.process({}, metadata={"method": "put"})
        assert session.request.call_args.kwargs["method"] == "PUT"


@pytest.mark.asyncio
async def test_proxy_http_client_error_raises():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy()
        processor = MessageProcessor()
        session = MagicMock()
        session.request = MagicMock(side_effect=aiohttp.ClientError("boom"))
        processor._get_session = AsyncMock(return_value=session)

        with pytest.raises(ProcessingError, match="Failed to proxy"):
            await processor.process({})


@pytest.mark.asyncio
async def test_bearer_auth_header():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy(auth_type="bearer", auth_token="tok")
        headers = MessageProcessor()._merge_headers(None)
        assert headers["Authorization"] == "Bearer tok"


@pytest.mark.asyncio
async def test_api_key_auth_default_header():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy(auth_type="api_key", auth_token="k")
        headers = MessageProcessor()._merge_headers(None)
        assert headers["X-API-Key"] == "k"


@pytest.mark.asyncio
async def test_basic_auth_header():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy(auth_type="basic", auth_username="u", auth_password="p")
        headers = MessageProcessor()._merge_headers(None)
        # base64("u:p") == "dTpw"
        assert headers["Authorization"] == "Basic dTpw"


@pytest.mark.asyncio
async def test_custom_auth_header():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy(auth_type="custom", auth_token="v", auth_header_name="X-Token")
        headers = MessageProcessor()._merge_headers(None)
        assert headers["X-Token"] == "v"


@pytest.mark.asyncio
async def test_header_forwarding_and_strip():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy(forward_headers=["X-Trace"], strip_headers=["X-Secret"])
        headers = MessageProcessor()._merge_headers(
            {"X-Trace": "1", "X-Secret": "no", "X-Other": "no"}
        )
        assert headers == {"X-Trace": "1"}


@pytest.mark.asyncio
async def test_auth_overrides_forwarded_header():
    with patch("openhqm.worker.processor.settings") as s:
        s.proxy = _proxy(auth_type="bearer", auth_token="server", forward_headers=["Authorization"])
        headers = MessageProcessor()._merge_headers({"Authorization": "Bearer client"})
        assert headers["Authorization"] == "Bearer server"
