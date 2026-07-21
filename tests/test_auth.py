"""Tests for the PingOne OIDC authentication flow.

Covers the refresh-token grant, token rotation persistence, recovery when
another process rotates the stored token, and the CLI helpers around
credential entry. All network and filesystem access is mocked or isolated.
"""

import asyncio
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from fpl_mcp.fpl.auth_manager import FPLAuthManager
from fpl_mcp.fpl.credential_manager import CredentialManager, extract_refresh_token

TEAM_ID = "12345"


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Point Path.home() at a temp dir and clear credential env vars."""
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    for var in ("FPL_REFRESH_TOKEN", "FPL_TEAM_ID"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def token_response(status=200, access_token="at-new", refresh_token="rt-new"):
    resp = MagicMock()
    resp.status_code = status
    if status == 200:
        resp.json.return_value = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 28800,
        }
    else:
        resp.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Refresh token does not exist",
        }
    return resp


def make_manager(session):
    """Build an FPLAuthManager wired to a fake requests session."""
    manager = FPLAuthManager()
    manager._session = session
    return manager


class TestExtractRefreshToken:
    def test_bare_token_passes_through(self):
        assert extract_refresh_token("abc.def.ghi") == "abc.def.ghi"

    def test_oidc_user_json_extracts_field(self):
        blob = json.dumps({"access_token": "at", "refresh_token": "rt", "scope": "openid"})
        assert extract_refresh_token(blob) == "rt"

    def test_invalid_json_returns_empty(self):
        assert extract_refresh_token("{not json") == ""

    def test_json_without_refresh_token_returns_empty(self):
        assert extract_refresh_token(json.dumps({"access_token": "at"})) == ""


class TestCredentialManager:
    def test_store_load_round_trip(self, isolated_home):
        cm = CredentialManager()
        cm.store_credentials("rt-1", TEAM_ID)
        assert CredentialManager().load_credentials() == ("rt-1", TEAM_ID)

    def test_update_refresh_token_keeps_team_id(self, isolated_home):
        cm = CredentialManager()
        cm.store_credentials("rt-1", TEAM_ID)
        cm.update_refresh_token("rt-2")
        assert cm.load_credentials() == ("rt-2", TEAM_ID)

    def test_stored_file_is_owner_only(self, isolated_home):
        cm = CredentialManager()
        cm.store_credentials("rt-1", TEAM_ID)
        mode = (isolated_home / ".fpl-mcp" / "credentials.enc").stat().st_mode & 0o777
        assert mode == 0o600

    def test_pre_oidc_credentials_are_rejected(self, isolated_home):
        cm = CredentialManager()
        encrypted = cm._encrypt_data({"email": "a@b.c", "password": "pw", "team_id": TEAM_ID})
        cm._encrypted_file.write_bytes(encrypted)
        assert cm.load_credentials() == (None, None)

    def test_legacy_env_vars_load_and_migrate(self, isolated_home, monkeypatch):
        monkeypatch.setenv("FPL_REFRESH_TOKEN", "rt-env")
        monkeypatch.setenv("FPL_TEAM_ID", TEAM_ID)
        cm = CredentialManager()
        assert cm.load_credentials() == ("rt-env", TEAM_ID)
        assert cm.migrate_legacy_credentials() is True
        monkeypatch.delenv("FPL_REFRESH_TOKEN")
        monkeypatch.delenv("FPL_TEAM_ID")
        assert cm.load_credentials() == ("rt-env", TEAM_ID)

    def test_no_credentials_anywhere(self, isolated_home):
        assert CredentialManager().load_credentials() == (None, None)


class TestAuthenticate:
    def test_missing_refresh_token_raises(self, isolated_home):
        manager = FPLAuthManager()
        with pytest.raises(ValueError, match="fpl-mcp-config setup"):
            asyncio.run(manager._authenticate())

    def test_success_sets_token_and_persists_rotation(self, isolated_home):
        CredentialManager().store_credentials("rt-old", TEAM_ID)
        session = MagicMock()
        session.post.return_value = token_response()
        manager = make_manager(session)

        asyncio.run(manager._authenticate())

        assert manager._access_token == "at-new"
        assert manager.is_authenticated
        # The rotated refresh token must be persisted for the next process.
        assert CredentialManager().load_credentials() == ("rt-new", TEAM_ID)
        sent = session.post.call_args.kwargs.get("data") or session.post.call_args[0][1]
        assert sent["refresh_token"] == "rt-old"
        assert sent["grant_type"] == "refresh_token"

    def test_retries_with_stored_token_after_external_rotation(self, isolated_home):
        CredentialManager().store_credentials("rt-old", TEAM_ID)
        session = MagicMock()
        manager = make_manager(session)

        # Another process consumes rt-old and persists its replacement.
        CredentialManager().store_credentials("rt-external", TEAM_ID)
        session.post.side_effect = [token_response(status=400), token_response()]

        asyncio.run(manager._authenticate())

        assert manager._access_token == "at-new"
        assert session.post.call_count == 2
        retried = session.post.call_args_list[1].kwargs["data"]
        assert retried["refresh_token"] == "rt-external"

    def test_dead_token_raises_actionable_error(self, isolated_home):
        CredentialManager().store_credentials("rt-dead", TEAM_ID)
        session = MagicMock()
        session.post.return_value = token_response(status=400)
        manager = make_manager(session)

        with pytest.raises(ValueError, match="invalid or expired"):
            asyncio.run(manager._authenticate())

        # No retry: the stored token is the one that just failed.
        assert session.post.call_count == 1
        assert manager._access_token is None
        assert not manager.is_authenticated

    def test_persist_failure_does_not_break_current_session(self, isolated_home):
        CredentialManager().store_credentials("rt-old", TEAM_ID)
        session = MagicMock()
        session.post.return_value = token_response()
        manager = make_manager(session)
        manager._credential_manager.update_refresh_token = MagicMock(
            side_effect=OSError("disk full")
        )

        asyncio.run(manager._authenticate())

        # The in-memory session stays valid even though persistence failed.
        assert manager._access_token == "at-new"
        assert manager._refresh_token == "rt-new"


class TestSetCredentials:
    def test_stores_and_forces_reauth(self, isolated_home):
        CredentialManager().store_credentials("rt-old", TEAM_ID)
        session = MagicMock()
        manager = make_manager(session)
        manager._access_token = "at-stale"
        manager._access_token_expiry = datetime.now() + timedelta(hours=1)

        manager.set_credentials("rt-fresh", "99999")

        assert manager._access_token is None
        assert not manager.is_authenticated
        assert manager.team_id == "99999"
        assert CredentialManager().load_credentials() == ("rt-fresh", "99999")

        # Next authenticated call must use the new token.
        session = MagicMock()
        session.post.return_value = token_response()
        manager._session = session
        asyncio.run(manager._authenticate())
        sent = session.post.call_args.kwargs["data"]
        assert sent["refresh_token"] == "rt-fresh"


class TestAuthedRequests:
    def test_sends_x_api_authorization_header(self, isolated_home):
        CredentialManager().store_credentials("rt-old", TEAM_ID)
        session = MagicMock()
        api_resp = MagicMock()
        api_resp.json.return_value = {"picks": []}
        session.get.return_value = api_resp
        manager = make_manager(session)
        manager._access_token = "at-current"
        manager._access_token_expiry = datetime.now() + timedelta(hours=1)

        result = asyncio.run(manager.make_authed_request("https://example.test/api/"))

        assert result == {"picks": []}
        headers = session.get.call_args.kwargs["headers"]
        assert headers["X-API-Authorization"] == "Bearer at-current"

    def test_expired_token_triggers_reauth(self, isolated_home):
        CredentialManager().store_credentials("rt-old", TEAM_ID)
        session = MagicMock()
        session.post.return_value = token_response()
        api_resp = MagicMock()
        api_resp.json.return_value = {"ok": True}
        session.get.return_value = api_resp
        manager = make_manager(session)
        manager._access_token = "at-stale"
        manager._access_token_expiry = datetime.now() - timedelta(minutes=1)

        asyncio.run(manager.make_authed_request("https://example.test/api/"))

        session.post.assert_called_once()
        headers = session.get.call_args.kwargs["headers"]
        assert headers["X-API-Authorization"] == "Bearer at-new"
