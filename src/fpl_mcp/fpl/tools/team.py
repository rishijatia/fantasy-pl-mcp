# src/fpl_mcp/fpl/tools/team.py
import logging
from typing import Dict, Any, Optional, List

from ..auth_manager import get_auth_manager
from ..api import api

logger = logging.getLogger(__name__)

async def get_team_for_gameweek(gameweek: Optional[int] = None, team_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get a user's team for a specific gameweek with rich data
    
    Args:
        gameweek: The gameweek number (defaults to current)
        team_id: FPL team ID (defaults to authenticated user)
        
    Returns:
        Detailed team information including player details
    """
    # Get auth manager and verify credentials
    auth_manager = get_auth_manager()
    
    # Use default team ID if not provided
    if team_id is None:
        team_id = auth_manager.team_id
        if not team_id:
            return {
                "error": "No team ID specified and no default team ID found in credentials"
            }
    
    # Use current gameweek if not specified
    if gameweek is None:
        gameweek = await api.get_current_gameweek()
    
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
        
        team_id = player_data.get("team")
        # For team data, use the team information directly from the player_data
        team_name = player_data.get("team", "Unknown")
        team_short = player_data.get("team_short", "UNK")
        
        # For position data, use the position information directly from the player_data
        position = player_data.get("position", "UNK")
        
        # Create enriched player data
        formatted_player = {
            "id": player_id,
            "position_order": pick.get("position"),
            "multiplier": pick.get("multiplier"),
            "is_captain": pick.get("is_captain", False),
            "is_vice_captain": pick.get("is_vice_captain", False),
            
            # Player details - using field names from players.py resource
            "web_name": player_data.get("web_name", "Unknown"),
            "full_name": player_data.get("name", "Unknown"),
            "price": player_data.get("price", 0),
            "form": player_data.get("form", "0.0"),
            "points_per_game": player_data.get("points_per_game", "0.0"),
            "total_points": player_data.get("points", 0),
            "minutes": player_data.get("minutes", 0),
            "goals": player_data.get("goals", 0),
            "assists": player_data.get("assists", 0),
            "clean_sheets": player_data.get("clean_sheets", 0),
            "bonus": player_data.get("bonus", 0),
            "status": player_data.get("status"),
            "news": player_data.get("news", ""),
            
            # Team details
            "team": team_name,
            "team_short": team_short,
            
            # Position details
            "position": position,
        }
        
        formatted_picks.append(formatted_player)
    
    # Sort by position order
    formatted_picks.sort(key=lambda p: p["position_order"])
    
    # Split into active and bench
    active_players = [p for p in formatted_picks if p["multiplier"] > 0]
    bench_players = [p for p in formatted_picks if p["multiplier"] == 0]
    
    # Build full result
    result = {
        "gameweek": gameweek,
        "team_id": team_id,
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
        result["overall_rank"] = entry_history.get("overall_rank", None)
        result["bank"] = entry_history.get("bank", 0) / 10.0
        result["team_value"] = entry_history.get("value", 0) / 10.0
        result["transfers"] = {
            "made": entry_history.get("event_transfers", 0),
            "cost": entry_history.get("event_transfers_cost", 0),
        }
    
    return result

# Register this as an MCP tool
def register_tools(mcp):
    @mcp.tool()
    async def get_my_team(gameweek: Optional[int] = None) -> Dict[str, Any]:
        """Get your FPL team for a specific gameweek
        
        Args:
            gameweek: Gameweek number (defaults to current gameweek)
            
        Returns:
            Detailed team information including player details
        """
        try:
            return await get_team_for_gameweek(gameweek)
        except Exception as e:
            logger.error(f"Error in get_my_team: {e}")
            return {"error": str(e)}