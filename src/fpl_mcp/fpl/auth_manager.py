# src/fpl_mcp/fpl/auth_manager.py
import logging
import requests
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .cache import cache
from .rate_limiter import rate_limiter
from .credential_manager import CredentialManager
from .utils.gameweek import get_current_gameweek_id
from ..config import (
    FPL_API_BASE_URL,
    FPL_USER_AGENT,
    FPL_TOKEN_URL,
    FPL_OIDC_CLIENT_ID,
)

logger = logging.getLogger(__name__)

class FPLAuthManager:
    """Manages FPL authentication with secure credential handling"""
    
    # Refresh the access token this many seconds before it actually expires.
    _EXPIRY_SAFETY_MARGIN = 60

    def __init__(self):
        # Initialize credential manager
        self._credential_manager = CredentialManager()

        # Attempt to migrate legacy credentials on first run
        self._credential_manager.migrate_legacy_credentials()

        # Load credentials from encrypted storage
        self._refresh_token, self._team_id = self._credential_manager.load_credentials()

        logger.info("Team ID: %s", self._team_id)

        # Session management
        self._session = None
        self._access_token = None
        self._access_token_expiry = None  # datetime when the access token expires

        # Shared rate limiter so authed and public requests draw from one budget
        self._rate_limiter = rate_limiter

    def set_credentials(self, refresh_token: str, team_id: str) -> None:
        """Set and store new credentials securely"""
        self._credential_manager.store_credentials(refresh_token, team_id)
        self._refresh_token = refresh_token
        self._team_id = team_id

        # Clear any existing session to force re-authentication
        self._session = None
        self._access_token = None
        self._access_token_expiry = None
    
    @property
    def team_id(self) -> Optional[str]:
        """Get the authenticated user's team ID"""
        return self._team_id
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid, unexpired access token"""
        return self._access_token is not None and not self._auth_expired()

    def _auth_expired(self) -> bool:
        """Check if the current access token has expired (or is about to)"""
        if self._access_token_expiry is None:
            return True
        margin = timedelta(seconds=self._EXPIRY_SAFETY_MARGIN)
        return datetime.now() >= self._access_token_expiry - margin

    async def get_session(self) -> requests.Session:
        """Get an authenticated session, creating or refreshing if needed"""
        if self._session is None or self._access_token is None or self._auth_expired():
            await self._authenticate()
        return self._session

    async def _request_token(self, refresh_token: str) -> requests.Response:
        """POST a refresh_token grant to the OIDC token endpoint."""
        await self._rate_limiter.acquire()

        headers = {
            "User-Agent": FPL_USER_AGENT,
            "accept-language": "en",
            "content-type": "application/x-www-form-urlencoded",
        }

        # No scope param: the refresh grant defaults to the originally granted
        # scope. Requesting a different scope triggers an invalid_grant error.
        data = {
            "grant_type": "refresh_token",
            "client_id": FPL_OIDC_CLIENT_ID,
            "refresh_token": refresh_token,
        }

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._session.post(FPL_TOKEN_URL, data=data, headers=headers),
        )

    async def _authenticate(self) -> None:
        """Obtain an access token from the OIDC refresh token grant.

        FPL uses PingOne (Ping Identity) OIDC. The web app is a public client, so
        we exchange the stored refresh token for a short-lived access token that
        is sent to the API as an X-API-Authorization bearer header.
        """
        if not self._refresh_token:
            logger.error("FPL refresh token not found")
            raise ValueError(
                "FPL authentication requires a refresh token. "
                "Run 'fpl-mcp-config setup' to configure it."
            )

        try:
            # Reuse a single session across refreshes
            if self._session is None:
                self._session = requests.Session()

            response = await self._request_token(self._refresh_token)

            if response.status_code in (400, 401):
                # PingOne rotates refresh tokens on every use, so another
                # process sharing the credential store (e.g. the MCP server
                # while the CLI runs 'test') may have consumed our in-memory
                # token and persisted its replacement. Reload the store and
                # retry once before declaring the token dead.
                stored_token, _ = self._credential_manager.load_credentials()
                if stored_token and stored_token != self._refresh_token:
                    logger.info(
                        "Stored refresh token differs from in-memory one "
                        "(rotated by another process); retrying with it"
                    )
                    self._refresh_token = stored_token
                    response = await self._request_token(stored_token)

            logger.info(f"Authentication response status: {response.status_code}")

            if not (200 <= response.status_code < 300):
                # Surface a clear, actionable message when the token is dead.
                detail = ""
                try:
                    payload = response.json()
                    detail = payload.get("error_description") or payload.get("error", "")
                except Exception:
                    detail = response.text[:200]
                if response.status_code in (400, 401):
                    raise ValueError(
                        "FPL refresh token is invalid or expired. Provide a "
                        "fresh one via the update_fpl_credentials tool (copy "
                        "the 'oidc.user' value from Local storage on "
                        "fantasy.premierleague.com) or re-run "
                        f"'fpl-mcp-config setup'. ({detail})"
                    )
                raise ValueError(f"Failed to authenticate with FPL: {detail}")

            token_data = response.json()
            self._access_token = token_data.get("access_token")
            if not self._access_token:
                raise ValueError("Token endpoint did not return an access token")

            expires_in = int(token_data.get("expires_in", 3600))
            self._access_token_expiry = datetime.now() + timedelta(seconds=expires_in)

            # PingOne rotates refresh tokens; persist the new one so the next run works.
            new_refresh = token_data.get("refresh_token")
            if new_refresh and new_refresh != self._refresh_token:
                self._refresh_token = new_refresh
                try:
                    self._credential_manager.update_refresh_token(new_refresh)
                except Exception as e:
                    # The old token was consumed by this exchange. If the new one
                    # isn't persisted, the next process starts from a dead token
                    # and is locked out until setup is re-run.
                    logger.error(
                        "Failed to persist rotated refresh token — the next run "
                        "will fail to authenticate and need 'fpl-mcp-config setup' "
                        f"re-run: {e}"
                    )

            logger.info("Successfully authenticated with FPL")

        except ValueError:
            self._access_token = None
            self._access_token_expiry = None
            raise
        except Exception as e:
            logger.error(f"Error during FPL authentication: {str(e)}")
            self._access_token = None
            self._access_token_expiry = None
            raise

    async def make_authed_request(self, url: str) -> Dict[str, Any]:
        """Make an authenticated request to FPL API"""
        session = await self.get_session()

        # Wait for rate limiter
        await self._rate_limiter.acquire()

        headers = {
            "User-Agent": FPL_USER_AGENT,
            "X-API-Authorization": f"Bearer {self._access_token}",
        }

        # Make the GET request in an executor (synchronously)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: session.get(url, headers=headers),
        )

        # Raise for HTTP errors
        response.raise_for_status()

        return response.json()
    
    async def get_my_team(self, team_id: Optional[int] = None) -> Dict[str, Any]:
        """Get current team for the authenticated user"""
        team_id = team_id or self._team_id
        if not team_id:
            raise ValueError("Team ID must be provided")
            
        url = f"{FPL_API_BASE_URL}/my-team/{team_id}/"
        # Cache data for 60 seconds
        return await cache.get_or_fetch(
            f"my_team_{team_id}",
            fetch_func=lambda: self.make_authed_request(url),
            ttl=60,
        )
    
    async def get_team_for_gameweek(self, team_id: Optional[int] = None, gameweek: int = 1) -> Dict[str, Any]:
        """Get team picks for a specific gameweek"""
        team_id = team_id or self._team_id
        if not team_id:
            raise ValueError("Team ID must be provided")
            
        url = f"{FPL_API_BASE_URL}/entry/{team_id}/event/{gameweek}/picks/"
        # Picks for finished gameweeks are immutable, so cache them for a
        # long time; the current (or a future) gameweek can still change,
        # so keep its TTL short.
        current_gw = await get_current_gameweek_id()
        if current_gw is not None and gameweek < current_gw:
            ttl = 30 * 24 * 3600  # 30 days
        else:
            ttl = 300  # 5 minutes
        return await cache.get_or_fetch(
            f"team_gw_{team_id}_{gameweek}",
            fetch_func=lambda: self.make_authed_request(url),
            ttl=ttl,
        )
    
    async def get_entry_data(self, team_id: Optional[int] = None) -> Dict[str, Any]:
        """Get general information about a team entry"""
        team_id = team_id or self._team_id
        if not team_id:
            raise ValueError("Team ID must be provided")
            
        url = f"{FPL_API_BASE_URL}/entry/{team_id}/"
        return await self.make_authed_request(url)
        
    async def close(self):
        """Close the session"""
        if self._session is not None:
            self._session.close()
        self._session = None
        self._access_token = None
        self._access_token_expiry = None

# Singleton instance
_auth_manager = None

def get_auth_manager():
    """Get the singleton auth manager instance"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = FPLAuthManager()
    return _auth_manager