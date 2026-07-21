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
