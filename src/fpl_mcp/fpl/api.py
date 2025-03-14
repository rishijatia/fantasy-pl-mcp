import httpx
import asyncio
import json
import jsonschema
import logging
from typing import Any, Dict, List, Optional

from .cache import cache, cached
from .rate_limiter import RateLimiter
from ..config import (
    FPL_API_BASE_URL, 
    FPL_USER_AGENT, 
    STATIC_SCHEMA_PATH, 
    RATE_LIMIT_MAX_REQUESTS, 
    RATE_LIMIT_PERIOD_SECONDS
)

# Set up logging
logger = logging.getLogger(__name__)

class FPLAPI:
    """
    FPL API client with schema validation, caching, and rate limiting.
    Handles fetching data from the Fantasy Premier League API.
    """
    def __init__(self, 
                 base_url: str = FPL_API_BASE_URL,
                 schema_path: str = STATIC_SCHEMA_PATH,
                 user_agent: str = FPL_USER_AGENT):
        """
        Initialize the FPL API client.
        
        Args:
            base_url: FPL API base URL
            schema_path: Path to JSON schema for validation
            user_agent: User-Agent header for requests
        """
        self.base_url = base_url
        self.schema_path = schema_path
        self.headers = {
            "User-Agent": user_agent
        }
        self.rate_limiter = RateLimiter(
            max_requests=RATE_LIMIT_MAX_REQUESTS,
            per_seconds=RATE_LIMIT_PERIOD_SECONDS
        )
        
        # Load schema for bootstrap-static if available
        self.schema = None
        try:
            with open(schema_path, 'r') as f:
                schema_data = json.load(f)
                self.schema = schema_data.get('schema')
                logger.info(f"Loaded schema from {schema_path}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load schema: {e}")
    
    async def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Make an HTTP request to the FPL API.
        
        Args:
            endpoint: API endpoint to request (without base URL)
            
        Returns:
            JSON response data
            
        Raises:
            httpx.HTTPError: On HTTP error
        """
        # Acquire rate limit permission
        await self.rate_limiter.acquire()
        
        url = f"{self.base_url}/{endpoint}"
        logger.debug(f"Making request to {url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
    
    def validate_data(self, data: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate data against JSON schema.
        
        Args:
            data: Data to validate
            schema: Schema to validate against (uses self.schema if None)
            
        Returns:
            True if validation succeeds, False otherwise
        """
        if not schema and not self.schema:
            logger.warning("No schema available for validation")
            return True
            
        try:
            jsonschema.validate(instance=data, schema=schema or self.schema)
            return True
        except jsonschema.exceptions.ValidationError as e:
            logger.warning(f"Schema validation failed: {e}")
            return False
    
    @cached("bootstrap_static")
    async def get_bootstrap_static(self) -> Dict[str, Any]:
        """
        Get main FPL static data (players, teams, game settings).
        Uses caching with 1-hour TTL by default.
        
        Returns:
            Bootstrap static data
        """
        data = await self._make_request("bootstrap-static/")
        
        # Fix null values that should be integers according to schema
        if 'phases' in data:
            for phase in data['phases']:
                if phase.get('highest_score') is None:
                    phase['highest_score'] = 0
        
        # Validate against schema if available
        if self.schema:
            self.validate_data(data)
            
        return data
    
    @cached("fixtures")
    async def get_fixtures(self) -> List[Dict[str, Any]]:
        """
        Get fixture data for all matches.
        
        Returns:
            List of fixtures
        """
        return await self._make_request("fixtures/")
    
    @cached("gameweeks")
    async def get_gameweeks(self) -> List[Dict[str, Any]]:
        """
        Get all gameweeks data.
        
        Returns:
            List of gameweeks
        """
        static_data = await self.get_bootstrap_static()
        return static_data.get("events", [])
    
    @cached("current_gameweek", ttl=600)  # 10-minute TTL for current GW
    async def get_current_gameweek(self) -> Dict[str, Any]:
        """
        Get current gameweek data.
        
        Returns:
            Current gameweek data or None if not found
        """
        gameweeks = await self.get_gameweeks()
        for gw in gameweeks:
            if gw.get("is_current", False):
                return gw
                
        # If no current gameweek found, return next one
        for gw in gameweeks:
            if gw.get("is_next", False):
                return gw
                
        # If no next gameweek either, return first one
        return gameweeks[0] if gameweeks else {}
    
    @cached("element_summary")
    async def get_player_summary(self, player_id: int) -> Dict[str, Any]:
        """
        Get detailed data for a specific player.
        
        Args:
            player_id: FPL player ID
            
        Returns:
            Player summary data
        """
        return await self._make_request(f"element-summary/{player_id}/")
        
    async def get_players(self) -> List[Dict[str, Any]]:
        """
        Get all players data.
        
        Returns:
            List of player data
        """
        static_data = await self.get_bootstrap_static()
        return static_data.get("elements", [])
    
    async def get_teams(self) -> List[Dict[str, Any]]:
        """
        Get all teams data.
        
        Returns:
            List of team data
        """
        static_data = await self.get_bootstrap_static()
        return static_data.get("teams", [])


# Create a singleton instance
api = FPLAPI()