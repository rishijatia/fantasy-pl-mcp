"""Tests for the shared HTTP client, timeouts, and retry behavior in FPLAPI."""

import asyncio
from unittest.mock import patch

import httpx
import pytest
import respx

from fpl_mcp.fpl.api import FPLAPI

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


@pytest.fixture
def fpl_api():
    api = FPLAPI(schema_path="/nonexistent/path")
    yield api


async def _close(api):
    await api.close()


async def test_client_is_reused_across_requests(fpl_api):
    """A single AsyncClient instance should serve multiple requests."""
    with respx.mock:
        respx.get(BOOTSTRAP_URL).mock(return_value=httpx.Response(200, json={"ok": 1}))

        await fpl_api._make_request("bootstrap-static/")
        first_client = fpl_api._client
        await fpl_api._make_request("bootstrap-static/")
        second_client = fpl_api._client

        assert first_client is second_client
        assert not first_client.is_closed
    await _close(fpl_api)


async def test_client_has_timeouts_configured(fpl_api):
    client = fpl_api._get_client()
    assert client.timeout.connect == 5.0
    assert client.timeout.read == 15.0
    await _close(fpl_api)


async def test_retries_on_500_then_succeeds(fpl_api):
    with respx.mock:
        route = respx.get(BOOTSTRAP_URL)
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(200, json={"ok": 1}),
        ]

        with patch("fpl_mcp.fpl.api.asyncio.sleep", return_value=None):
            data = await fpl_api._make_request("bootstrap-static/")

        assert data == {"ok": 1}
        assert route.call_count == 2
    await _close(fpl_api)


async def test_retries_on_429_then_succeeds(fpl_api):
    with respx.mock:
        route = respx.get(BOOTSTRAP_URL)
        route.side_effect = [
            httpx.Response(429),
            httpx.Response(200, json={"ok": 1}),
        ]

        with patch("fpl_mcp.fpl.api.asyncio.sleep", return_value=None):
            data = await fpl_api._make_request("bootstrap-static/")

        assert data == {"ok": 1}
        assert route.call_count == 2
    await _close(fpl_api)


async def test_gives_up_after_max_retries(fpl_api):
    with respx.mock:
        route = respx.get(BOOTSTRAP_URL).mock(return_value=httpx.Response(503))

        with patch("fpl_mcp.fpl.api.asyncio.sleep", return_value=None):
            with pytest.raises(httpx.HTTPStatusError):
                await fpl_api._make_request("bootstrap-static/", max_retries=3)

        assert route.call_count == 3
    await _close(fpl_api)


async def test_client_errors_are_not_retried(fpl_api):
    """4xx client errors (other than 429) are permanent — no retry."""
    with respx.mock:
        route = respx.get(BOOTSTRAP_URL).mock(return_value=httpx.Response(404))

        with pytest.raises(httpx.HTTPStatusError):
            await fpl_api._make_request("bootstrap-static/")

        assert route.call_count == 1
    await _close(fpl_api)


async def test_retries_on_timeout(fpl_api):
    with respx.mock:
        route = respx.get(BOOTSTRAP_URL)
        route.side_effect = [
            httpx.ConnectTimeout("boom"),
            httpx.Response(200, json={"ok": 1}),
        ]

        with patch("fpl_mcp.fpl.api.asyncio.sleep", return_value=None):
            data = await fpl_api._make_request("bootstrap-static/")

        assert data == {"ok": 1}
        assert route.call_count == 2
    await _close(fpl_api)
