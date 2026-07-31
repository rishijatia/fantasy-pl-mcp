# src/fpl_mcp/fpl/tools/team.py
import logging
import time
from typing import Dict, Any, Optional, List

from ..auth_manager import get_auth_manager
from ..api import api
from ..cache import cache

logger = logging.getLogger(__name__)

async def get_team_for_gameweek(gameweek: Optional[int] = None, team_id: int = 0) -> Dict[str, Any]:
    """
    Get any FPL team for a specific gameweek with rich data
    
    Args:
        gameweek: The gameweek number (defaults to current)
        team_id: FPL team ID to look up (required)
        
    Returns:
        Detailed team information including player details
    """
    # Get auth manager for API access
    auth_manager = get_auth_manager()
    
    # Check that we have a valid team ID
    if not team_id:
        return {
            "error": "No team ID specified",
            "suggestion": "Please provide a valid team_id parameter"
        }
    
    logger.info(f"Getting team data for team {team_id}, gameweek {gameweek}")
    
    # Use current gameweek if not specified
    if gameweek is None:
        current_gw_data = await api.get_current_gameweek()
        gameweek = current_gw_data.get("id", 1)  # Extract just the ID
    
    # Ensure gameweek is an integer
    try:
        gameweek = int(gameweek)
    except (ValueError, TypeError):
        logger.error(f"Invalid gameweek value: {gameweek}")
        return {"error": f"Invalid gameweek value: {gameweek}"}
    
    # Get team data for the gameweek
    try:
        gw_picks_data = await auth_manager.get_team_for_gameweek(team_id, gameweek)
    except Exception as e:
        logger.error(f"Error fetching team data: {e}")
        return {
            "error": f"Failed to retrieve team data for gameweek {gameweek}: {str(e)}"
        }
    
    # Get player data to enrich team information
    # Use the players, teams, and position resources for better caching
    all_players = await api.get_players()
    all_teams = await api.get_teams()
    
    # Create lookup dictionaries
    players = {p["id"]: p for p in all_players}
    teams = {t["id"]: t for t in all_teams}
    
    # Process team data
    picks = gw_picks_data.get("picks", [])
    entry_history = gw_picks_data.get("entry_history", {})
    
    # Format each player
    formatted_picks = []
    captain_id = None
    vice_captain_id = None
    
    # Find captain and vice captain
    for pick in picks:
        if pick.get("is_captain"):
            captain_id = pick.get("element")
        if pick.get("is_vice_captain"):
            vice_captain_id = pick.get("element")
    
    # Format players with detailed info
    for pick in picks:
        player_id = pick.get("element")
        player_data = players.get(player_id, {})
        
        if not player_data:
            logger.warning(f"Player {player_id} not found in bootstrap data")
            continue
        
        # Get team ID from player data
        player_team_id = player_data.get("team")
        
        # Look up team details using the team ID
        team_data = teams.get(player_team_id, {})
        team_name = team_data.get("name", "Unknown")
        team_short = team_data.get("short_name", "UNK")
        
        # Extract position from player data
        position = player_data.get("element_type")
        
        # Convert position ID to position code
        position_map = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
        position_code = position_map.get(position, "UNK")
        
        # Create enriched player data
        formatted_player = {
            "id": player_id,
            "position_order": pick.get("position"),
            "multiplier": pick.get("multiplier"),
            "is_captain": pick.get("is_captain", False),
            "is_vice_captain": pick.get("is_vice_captain", False),
            
            # Player details - using field names from players.py resource
            "web_name": player_data.get("web_name", "Unknown"),
            "full_name": f"{player_data.get('first_name', '')} {player_data.get('second_name', '')}".strip() or "Unknown",
            "price": player_data.get("now_cost", 0) / 10.0 if player_data.get("now_cost") else 0,
            "form": player_data.get("form", "0.0"),
            "points_per_game": player_data.get("points_per_game", "0.0"),
            "total_points": player_data.get("total_points", 0),
            "minutes": player_data.get("minutes", 0),
            "goals": player_data.get("goals_scored", 0),
            "assists": player_data.get("assists", 0),
            "clean_sheets": player_data.get("clean_sheets", 0),
            "bonus": player_data.get("bonus", 0),
            "status": player_data.get("status"),
            "news": player_data.get("news", ""),
            
            # Team details
            "team": team_name,
            "team_short": team_short,
            
            # Position details
            "position": position_code,
        }
        
        formatted_picks.append(formatted_player)
    
    # Sort by position order
    formatted_picks.sort(key=lambda p: p["position_order"])
    
    # Split into active and bench
    active_players = [p for p in formatted_picks if p["multiplier"] > 0]
    bench_players = [p for p in formatted_picks if p["multiplier"] == 0]
    
    # Try to get team manager information
    try:
        async def fetch_manager_info():
            entry_data = await auth_manager.get_entry_data(team_id)
            return {
                "team_name": entry_data.get("name", "Unknown"),
                "manager_name": f"{entry_data.get('player_first_name', '')} {entry_data.get('player_last_name', '')}".strip(),
                "manager_region": entry_data.get("player_region_name", ""),
                "overall_rank": entry_data.get("summary_overall_rank", 0),
                "overall_points": entry_data.get("summary_overall_points", 0),
            }

        manager_info = await cache.get_or_fetch(
            f"team_manager_info_{team_id}",
            fetch_func=fetch_manager_info,
            ttl=3600,
        )
    except Exception as e:
        logger.warning(f"Could not get manager info for team {team_id}: {e}")
        manager_info = {
            "team_name": "Unknown",
            "manager_name": "Unknown",
        }
    
    # Build full result
    result = {
        "gameweek": gameweek,
        "team_id": team_id,
        "team_name": manager_info.get("team_name", "Unknown"),
        "manager_name": manager_info.get("manager_name", "Unknown"),
        "active": active_players,
        "bench": bench_players,
        "captain": next((p for p in formatted_picks if p["is_captain"]), None),
        "vice_captain": next((p for p in formatted_picks if p["is_vice_captain"]), None),
    }
    
    # Add gameweek history data if available
    if entry_history:
        result["points"] = entry_history.get("points", 0)
        result["total_points"] = entry_history.get("total_points", 0)
        result["rank"] = entry_history.get("rank", None)
        result["overall_rank"] = entry_history.get("overall_rank", None) or manager_info.get("overall_rank", 0)
        result["bank"] = entry_history.get("bank", 0) / 10.0
        result["team_value"] = entry_history.get("value", 0) / 10.0
        result["transfers"] = {
            "made": entry_history.get("event_transfers", 0),
            "cost": entry_history.get("event_transfers_cost", 0),
        }
    
    return result

async def get_manager_info(team_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a team manager
    
    Args:
        team_id: FPL team ID to look up
        
    Returns:
        Manager information including history, name, and team details
    """
    # Get auth manager
    auth_manager = get_auth_manager()

    try:
        async def fetch_manager_info():
            entry_data = await auth_manager.get_entry_data(team_id)
            return {
                "team_id": team_id,
                "team_name": entry_data.get("name", "Unknown"),
                "manager_name": f"{entry_data.get('player_first_name', '')} {entry_data.get('player_last_name', '')}".strip(),
                "started_event": entry_data.get("started_event"),
                "overall_rank": entry_data.get("summary_overall_rank"),
                "overall_points": entry_data.get("summary_overall_points"),
                "value": entry_data.get("last_deadline_value") / 10.0 if entry_data.get("last_deadline_value") else 0,
                "bank": entry_data.get("last_deadline_bank") / 10.0 if entry_data.get("last_deadline_bank") else 0,
                "kit": entry_data.get("kit"),
                "region": entry_data.get("player_region_name"),
                "joined_time": entry_data.get("joined_time"),
                "leagues": {
                    "classic": entry_data.get("leagues", {}).get("classic", []),
                    "h2h": entry_data.get("leagues", {}).get("h2h", []),
                    "cup": entry_data.get("leagues", {}).get("cup", {})
                }
            }

        # 1 hour cache
        return await cache.get_or_fetch(
            f"manager_info_{team_id}",
            fetch_func=fetch_manager_info,
            ttl=3600,
        )
    except Exception as e:
        logger.error(f"Error fetching manager info for team {team_id}: {e}")
        return {"error": f"Failed to retrieve manager info: {str(e)}"}

# Register these as MCP tools
def register_tools(mcp):
    @mcp.tool()
    async def get_team(team_id: int, gameweek: Optional[int] = None) -> Dict[str, Any]:
        """Get any team's players, captain, and other details for a specific gameweek
        
        Args:
            team_id: FPL team ID (required)
            gameweek: Gameweek number (defaults to current gameweek)
            
        Returns:
            Detailed team information including player details, captain, and value
        """
        try:
            # Always use the specified team_id, no default
            return await get_team_for_gameweek(gameweek, team_id)
        except Exception as e:
            logger.error(f"Error in get_team: {e}")
            return {"error": str(e)}
    
    @mcp.tool()
    async def get_my_team(gameweek: Optional[int] = None) -> Dict[str, Any]:
        """Get your own FPL team for a specific gameweek
        
        Args:
            gameweek: Gameweek number (defaults to current gameweek)
            
        Returns:
            Detailed team information including player details, captain, and value
            
        Note:
            This uses your authenticated team ID from the FPL credentials.
            To get another team's details, use get_team and provide a team_id.
        """
        try:
            # Get the authenticated user's team ID
            auth_manager = get_auth_manager()
            team_id = auth_manager.team_id
            
            if not team_id:
                return {
                    "error": "No default team ID found in credentials",
                    "suggestion": "Check your authentication settings or use get_team with an explicit team_id"
                }
                
            logger.info(f"Getting authenticated user's team: {team_id}")
            return await get_team_for_gameweek(gameweek, team_id)
        except Exception as e:
            logger.error(f"Error in get_my_team: {e}")
            return {"error": str(e)}
            
    @mcp.tool()
    async def get_manager(team_id: int) -> Dict[str, Any]:
        """Get detailed information about an FPL manager

        Args:
            team_id: FPL team ID to look up

        Returns:
            Manager information including history, name, team details, and leagues
        """
        try:
            return await get_manager_info(team_id)
        except Exception as e:
            logger.error(f"Error in get_manager: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def check_fpl_authentication() -> Dict[str, Any]:
        """Check if FPL authentication is working correctly

        Returns:
            Authentication status and basic team information
        """
        try:
            auth_manager = get_auth_manager()
            team_id = auth_manager.team_id

            if not team_id:
                return {
                    "authenticated": False,
                    "error": "No team ID found in credentials",
                    "setup_instructions": "Run 'fpl-mcp-config setup' to configure your FPL credentials"
                }

            # Try to get basic team info as authentication test
            try:
                entry_data = await auth_manager.get_entry_data()

                return {
                    "authenticated": True,
                    "team_name": entry_data.get("name"),
                    "manager_name": f"{entry_data.get('player_first_name')} {entry_data.get('player_last_name')}",
                    "overall_rank": entry_data.get("summary_overall_rank"),
                    "team_id": team_id
                }
            except Exception as e:
                return {
                    "authenticated": False,
                    "error": f"Authentication failed: {str(e)}",
                    "setup_instructions": "Check your FPL credentials and ensure they are correct"
                }

        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
            return {
                "authenticated": False,
                "error": str(e),
                "setup_instructions": "Run 'fpl-mcp-config setup' to configure your FPL credentials"
            }

    @mcp.tool()
    async def update_fpl_credentials(refresh_token: str, team_id: str = "") -> Dict[str, Any]:
        """Store a new FPL refresh token when the current one has expired.

        Use this when authenticated FPL tools fail with an invalid/expired refresh
        token error. Ask the user to fetch a fresh token first: log in at
        https://fantasy.premierleague.com, open the DevTools Console (F12), run

            copy(JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k=>k.startsWith('oidc.user:')))).refresh_token)

        (typing 'allow pasting' first if Chrome refuses), and paste the clipboard
        contents here. Copying the whole 'oidc.user:...' JSON value from DevTools ->
        Application -> Local storage works too.

        Args:
            refresh_token: The copied oidc.user JSON value (or just its
                refresh_token field)
            team_id: FPL team ID; omit to keep the currently stored one

        Returns:
            Whether the new token was stored and validated against the FPL API
        """
        from ..credential_manager import extract_refresh_token

        token = extract_refresh_token(refresh_token)
        if not token:
            return {
                "updated": False,
                "error": "No refresh token found in the provided value. Pass the "
                         "full oidc.user JSON or its refresh_token field."
            }

        auth_manager = get_auth_manager()
        team_id = team_id.strip() or auth_manager.team_id
        if not team_id:
            return {
                "updated": False,
                "error": "No team ID stored. Ask the user for their FPL team ID "
                         "(the number in their team page URL) and pass it as team_id."
            }

        auth_manager.set_credentials(token, str(team_id))

        # Validate immediately: the exchange claims the token before the user's
        # browser can rotate it away, and /my-team/ proves the API accepts it.
        try:
            team_data = await auth_manager.get_my_team()
        except Exception as e:
            return {
                "updated": False,
                "error": f"Token was stored but failed validation: {e}. Ask the "
                         "user to copy a fresh oidc.user value and try again."
            }

        return {
            "updated": True,
            "team_id": team_id,
            "squad_picks": len(team_data.get("picks", [])),
            "note": "Token validated and stored. The copy in the user's browser "
                    "has been superseded; their browser session will recover on "
                    "its own."
        }