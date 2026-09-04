"""Tests for the public-data fallback seam.

Most FPL endpoints this server reads — /entry/, /entry/{id}/history/,
/entry/{id}/event/{gw}/picks/, /leagues-classic/{id}/standings/ — are public
and need no login, but they used to be routed through an authenticated
request that raised when no refresh token was stored. These tests cover the
boundary that change introduced:

  * a public endpoint must work with no credentials at all
  * a genuinely private endpoint must still refuse, with a clear message
  * credentials that exist but no longer work must not break public reads
  * working credentials must still take the authenticated path

Anything below the seam (parsing FPL's payloads, the token grant itself) is
covered by the inherited suites and is deliberately not retested here.
"""

from unittest.mock import MagicMock, patch

import pytest

from fpl_mcp.fpl.auth_manager import FPLAuthManager

PUBLIC_URL = "https://fantasy.premierleague.com/api/entry/6071111/"
PUBLIC_BODY = {"name": "Big_Brawls", "summary_overall_points": 122}
AUTH_HEADER = "X-API-Authorization"


def _make_manager(refresh_token=None, team_id=None):
    """Build an FPLAuthManager with mocked credential storage.

    Passing no arguments gives a manager with no stored credentials, which
    is the state every Tier 1 user is in.
    """
    with patch("fpl_mcp.fpl.auth_manager.CredentialManager") as mock_cm:
        instance = mock_cm.return_value
        instance.migrate_legacy_credentials.return_value = None
        instance.load_credentials.return_value = (refresh_token, team_id)
        return FPLAuthManager()


def _mock_session(get_body=None, token_status=200):
    """A session whose GET returns public data and whose POST is the token grant."""
    session = MagicMock()

    get_response = MagicMock()
    get_response.status_code = 200
    get_response.json.return_value = get_body if get_body is not None else PUBLIC_BODY
    get_response.raise_for_status.return_value = None
    session.get.return_value = get_response

    post_response = MagicMock()
    post_response.status_code = token_status
    post_response.json.return_value = (
        {"access_token": "at", "expires_in": 3600}
        if token_status == 200
        else {"error_description": "refresh token expired"}
    )
    post_response.text = "refresh token expired"
    session.post.return_value = post_response

    return session


def _sent_headers(session):
    """Headers from the most recent GET on a mocked session."""
    _, kwargs = session.get.call_args
    return kwargs.get("headers", {})


async def test_public_endpoint_works_without_credentials():
    """The Tier 1 case: no login stored, public data still returned."""
    manager = _make_manager()
    session = _mock_session()

    assert manager.has_credentials is False

    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=session):
        result = await manager.make_optional_auth_request(PUBLIC_URL)

    assert result == PUBLIC_BODY
    # No token exists, so no attempt to authenticate should have been made.
    session.post.assert_not_called()
    assert AUTH_HEADER not in _sent_headers(session)


async def test_entry_lookup_without_credentials_needs_an_explicit_team_id():
    """With no stored team id, the error must tell the user how to find theirs."""
    manager = _make_manager()

    with pytest.raises(ValueError, match="Team ID must be provided"):
        await manager.get_entry_data()


async def test_private_endpoint_still_refuses_without_credentials():
    """/my-team/ is genuinely private and must not fall back to a public read."""
    manager = _make_manager()
    session = _mock_session()

    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=session):
        with pytest.raises(ValueError, match="refresh token"):
            await manager.get_my_team(6071111)

    session.get.assert_not_called()


async def test_expired_credentials_fall_back_to_public_data():
    """A dead refresh token must not break endpoints that never needed auth."""
    manager = _make_manager(refresh_token="stale-token", team_id="6071111")
    session = _mock_session(token_status=400)

    assert manager.has_credentials is True

    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=session):
        result = await manager.make_optional_auth_request(PUBLIC_URL)

    # Authentication was attempted and failed, then the public path served it.
    session.post.assert_called()
    assert result == PUBLIC_BODY
    assert AUTH_HEADER not in _sent_headers(session)


async def test_working_credentials_still_use_the_authenticated_path():
    """No regression for existing users: a valid token is still sent."""
    manager = _make_manager(refresh_token="good-token", team_id="6071111")
    session = _mock_session(token_status=200)

    with patch("fpl_mcp.fpl.auth_manager.requests.Session", return_value=session):
        result = await manager.make_optional_auth_request(PUBLIC_URL)

    assert result == PUBLIC_BODY
    assert _sent_headers(session).get(AUTH_HEADER) == "Bearer at"
