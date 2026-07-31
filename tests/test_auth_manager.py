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
