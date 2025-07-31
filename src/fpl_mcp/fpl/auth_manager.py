# src/fpl_mcp/fpl/auth_manager.py
import logging
import requests
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .cache import cache
from .rate_limiter import RateLimiter
from .credential_manager import CredentialManager
from ..config import (
    FPL_API_BASE_URL, 
    FPL_USER_AGENT,
    FPL_LOGIN_URL,
)

logger = logging.getLogger(__name__)

class FPLAuthManager:
    """Manages FPL authentication with secure credential handling"""
    
    def __init__(self):
        # Initialize credential manager
        self._credential_manager = CredentialManager()
        
        # Attempt to migrate legacy credentials on first run
        self._credential_manager.migrate_legacy_credentials()
        
        # Load credentials from encrypted storage
        self._email, self._password, self._team_id = self._credential_manager.load_credentials()
        
        logger.info("Team ID: %s", self._team_id)

        # Session management
        self._session = None
        self._last_auth_time = None
        self._auth_valid_duration = timedelta(hours=2)  # Re-auth every 2 hours
        
        # Rate limiter for authenticated requests
        self._rate_limiter = RateLimiter()
    
    def set_credentials(self, email: str, password: str, team_id: str) -> None:
        """Set and store new credentials securely"""
        self._credential_manager.store_credentials(email, password, team_id)
        self._email = email
        self._password = password
        self._team_id = team_id
        
        # Clear any existing session to force re-authentication
        self._session = None
        self._last_auth_time = None
    
    @property
    def team_id(self) -> Optional[str]:
        """Get the authenticated user's team ID"""
        return self._team_id
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication"""
        return self._session is not None and not self._auth_expired()
    
    def _auth_expired(self) -> bool:
        """Check if authentication has expired"""
        if self._last_auth_time is None:
            return True
        return datetime.now() - self._last_auth_time > self._auth_valid_duration
    
    async def get_session(self) -> requests.Session:
        """Get an authenticated session, creating or refreshing if needed"""
        if self._session is None or self._auth_expired():
            await self._authenticate()
        return self._session
    
    async def _authenticate(self) -> None:
        """Authenticate with FPL API using environment credentials"""
        if not self._email or not self._password:
            logger.error("FPL credentials not found")
            raise ValueError(
                "FPL authentication requires FPL_EMAIL and FPL_PASSWORD to be set"
            )
        
        try:
            # Create a new session
            self._session = requests.Session()
            
            # Wait for rate limiter
            await self._rate_limiter.acquire()
            
            # Use our own user-agent with headers that work
            headers = {
                "User-Agent": FPL_USER_AGENT,
                "accept-language": "en"
            }
            
            # Use the exact data format from the working example
            data = {
                "login": self._email,
                "password": self._password,
                "app": "plfpl-web",
                "redirect_uri": "https://fantasy.premierleague.com/a/login"
            }
            
            # Make the POST request (synchronously since requests doesn't support async)
            # We'll run this in an executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self._session.post(FPL_LOGIN_URL, data=data, headers=headers)
            )
            
            # Log the response status
            logger.info(f"Authentication response status: {response.status_code}")
            
            # Check if login was successful
            if not (200 <= response.status_code < 300):
                raise ValueError("Failed to authenticate with FPL")
            
            self._last_auth_time = datetime.now()
            logger.info("Successfully authenticated with FPL")
            
        except Exception as e:
            logger.error(f"Error during FPL authentication: {str(e)}")
            self._session = None
            raise
    
    async def make_authed_request(self, url: str) -> Dict[str, Any]:
        """Make an authenticated request to FPL API"""
        session = await self.get_session()
        
        # Wait for rate limiter
        await self._rate_limiter.acquire()
        
        # Make the GET request in an executor (synchronously)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: session.get(url)
        )
        
        # Raise for HTTP errors
        response.raise_for_status()
        
        return response.json()
    
    async def get_my_team(self, team_id: Optional[int] = None) -> Dict[str, Any]:
        """Get current team for the authenticated user"""
        team_id = team_id or self._team_id
        if not team_id:
            raise ValueError("Team ID must be provided")
            
        cache_key = f"my_team_{team_id}"
        cached_data = cache.cache.get(cache_key)
        
        if cached_data and cached_data[0] + 60 > datetime.now().timestamp():
            # Use cached data if it's less than 60 seconds old
            return cached_data[1]
            
        url = f"{FPL_API_BASE_URL}/my-team/{team_id}/"
        data = await self.make_authed_request(url)
        
        # Cache data for 60 seconds
        cache.cache[cache_key] = (datetime.now().timestamp(), data)
        
        return data
    
    async def get_team_for_gameweek(self, team_id: Optional[int] = None, gameweek: int = 1) -> Dict[str, Any]:
        """Get team picks for a specific gameweek"""
        team_id = team_id or self._team_id
        if not team_id:
            raise ValueError("Team ID must be provided")
            
        cache_key = f"team_gw_{team_id}_{gameweek}"
        cached_data = cache.cache.get(cache_key)
        
        if cached_data:
            # Use cached data if available (these don't change once set)
            return cached_data[1]
            
        url = f"{FPL_API_BASE_URL}/entry/{team_id}/event/{gameweek}/picks/"
        data = await self.make_authed_request(url)
        
        # Cache this data indefinitely as historical data doesn't change
        cache.cache[cache_key] = (datetime.now().timestamp(), data)
        
        return data
    
    async def get_entry_data(self, team_id: Optional[int] = None) -> Dict[str, Any]:
        """Get general information about a team entry"""
        team_id = team_id or self._team_id
        if not team_id:
            raise ValueError("Team ID must be provided")
            
        url = f"{FPL_API_BASE_URL}/entry/{team_id}/"
        return await self.make_authed_request(url)
        
    async def close(self):
        """Close the session"""
        self._session = None

# Singleton instance
_auth_manager = None

def get_auth_manager():
    """Get the singleton auth manager instance"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = FPLAuthManager()
    return _auth_manager