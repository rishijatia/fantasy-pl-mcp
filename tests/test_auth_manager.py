"""Tests for FPL authentication — token-endpoint failure handling.

A 200 from the OIDC token endpoint is not enough on its own: the body must
carry an access token, and non-2xx responses must clear auth state so the
next call retries.
"""

from unittest.mock import MagicMock, patch

import pytest

from fpl_mcp.fpl.auth_manager import FPLAuthManager


def _make_manager():
    """Build an FPLAuthManager with mocked credential storage."""
    with patch("fpl_mcp.fpl.auth_manager.CredentialManager") as mock_cm:
        instance = mock_cm.return_value
        instance.migrate_legacy_credentials.return_value = None
        instance.load_credentials.return_value = ("refresh-token", "12345")
        return FPLAuthManager()


def _mock_session(status=200, body=None):
    session = MagicMock()
    response = MagicMock()
    response.status_code = status
    response.json.return_value = (
        body
        if body is not None
        else {"access_token": "at", "refresh_token": "rt-new", "expires_in": 3600}
    )
    session.post.return_value = response
    return session


async def test_token_grant_succeeds():
    manager = _make_manager()
    session = _mock_session()

    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=session):
        await manager._authenticate()

    assert manager._access_token == "at"
    assert manager.is_authenticated is True


async def test_200_without_access_token_fails():
    """HTTP 200 whose body has no access_token must not count as authenticated."""
    manager = _make_manager()
    session = _mock_session(body={"token_type": "Bearer"})

    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=session):
        with pytest.raises(ValueError, match="access token"):
            await manager._authenticate()

    # Auth state must be cleared so the next call retries authentication
    assert manager._access_token is None
    assert manager.is_authenticated is False


async def test_error_status_fails():
    manager = _make_manager()
    session = _mock_session(status=403, body={"error": "forbidden"})

    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=session):
        with pytest.raises(ValueError):
            await manager._authenticate()

    assert manager._access_token is None
    assert manager.is_authenticated is False


async def test_missing_credentials_raise():
    with patch("fpl_mcp.fpl.auth_manager.CredentialManager") as mock_cm:
        instance = mock_cm.return_value
        instance.migrate_legacy_credentials.return_value = None
        instance.load_credentials.return_value = (None, None)
        manager = FPLAuthManager()

    with pytest.raises(ValueError, match="refresh token"):
        await manager._authenticate()


async def _picks_ttl(current_gw, requested_gw):
    """Call get_team_for_gameweek and capture the ttl passed to the cache."""
    from unittest.mock import AsyncMock

    manager = _make_manager()
    fetch = AsyncMock(return_value={"picks": []})
    with patch(
        "fpl_mcp.fpl.auth_manager.get_current_gameweek_id",
        new_callable=AsyncMock,
        return_value=current_gw,
    ), patch.object(type(manager), "make_authed_request", new=AsyncMock()), patch(
        "fpl_mcp.fpl.auth_manager.cache.get_or_fetch", new=fetch
    ):
        await manager.get_team_for_gameweek(gameweek=requested_gw)

    return fetch.call_args.kwargs["ttl"]


async def test_past_gameweek_picks_cached_long():
    assert await _picks_ttl(current_gw=10, requested_gw=7) == 30 * 24 * 3600


async def test_current_gameweek_picks_cached_briefly():
    assert await _picks_ttl(current_gw=10, requested_gw=10) == 300


async def test_unknown_current_gameweek_uses_short_ttl():
    assert await _picks_ttl(current_gw=None, requested_gw=7) == 300


async def test_adopt_refresh_token_discovers_team_and_stores_rotated_token():
    """A browser-captured token needs no team ID: it comes from /api/me/, and
    the rotated refresh token (not the captured one) is what gets persisted."""
    from unittest.mock import AsyncMock

    manager = _make_manager()
    session = _mock_session()
    me = AsyncMock(return_value={"player": {"entry": 2233768}})

    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=session), patch.object(
        type(manager), "make_authed_request", new=me
    ):
        team_id = await manager.adopt_refresh_token("captured-token")

    assert team_id == "2233768"
    assert manager.team_id == "2233768"
    assert me.call_args.args[0].endswith("/me/")
    manager._credential_manager.store_credentials.assert_called_with("rt-new", "2233768")


async def test_adopt_refresh_token_without_team_raises():
    from unittest.mock import AsyncMock

    manager = _make_manager()
    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=_mock_session()), patch.object(
        type(manager), "make_authed_request", new=AsyncMock(return_value={"player": None})
    ):
        with pytest.raises(ValueError, match="no team"):
            await manager.adopt_refresh_token("captured-token")


async def test_browser_login_is_shared_across_calls():
    """A second login_to_fpl call must reuse the open window, not launch another."""
    import asyncio
    from unittest.mock import AsyncMock

    manager = _make_manager()
    gate = asyncio.Event()

    async def capture():
        await gate.wait()
        return "captured-token"

    with patch("fpl_mcp.fpl.browser_login.capture_refresh_token", new=capture), patch.object(
        type(manager), "adopt_refresh_token", new=AsyncMock(return_value="42")
    ):
        first = manager.start_browser_login()
        second = manager.start_browser_login()
        assert first is second
        gate.set()
        assert await first == "42"
