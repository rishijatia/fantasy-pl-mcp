# src/fpl_mcp/fpl/tools/managers.py
import logging
from typing import Any, Dict, Optional

from ..auth_manager import get_auth_manager

logger = logging.getLogger(__name__)


async def get_manager_data(team_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get raw manager data from the FPL API

    Args:
        team_id: FPL team ID (defaults to authenticated user)

    Returns:
        Raw manager data from the API
    """
    auth_manager = get_auth_manager()

    # Use default team ID if not provided
    if team_id is None:
        team_id = auth_manager.team_id
        if not team_id:
            return {
                "error": "No team ID specified and no default team ID found"
            }

    # Get manager data
    try:
        data = await auth_manager.get_entry_data(team_id)
        return data
    except Exception as e:
        logger.error(f"Error fetching manager data: {e}")
        return {"error": f"Failed to retrieve manager data: {str(e)}"}


def parse_manager_basic_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse basic manager information"""
    first_name = data.get('player_first_name', '')
    last_name = data.get('player_last_name', '')
    return {
        "team_id": data.get("id"),
        "team_name": data.get("name"),
        "manager_name": f"{first_name} {last_name}",
        "region": data.get("player_region_name"),
        "started_event": data.get("started_event"),
        "favourite_team": data.get("favourite_team"),
        "joined_time": data.get("joined_time"),
        "kit": data.get("kit"),
        "years_active": data.get("years_active"),
    }


def parse_manager_performance(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse manager performance information"""
    return {
        "overall_points": data.get("summary_overall_points"),
        "overall_rank": data.get("summary_overall_rank"),
        "current_event": data.get("current_event"),
        "current_event_points": data.get("summary_event_points"),
        "current_event_rank": data.get("summary_event_rank"),
        "team_value": (
            data.get("last_deadline_value", 0) / 10
            if data.get("last_deadline_value")
            else None
        ),
        "bank": (
            data.get("last_deadline_bank", 0) / 10
            if data.get("last_deadline_bank")
            else None
        ),
        "total_transfers": data.get("last_deadline_total_transfers"),
    }


def parse_manager_leagues(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse manager league information"""
    leagues = data.get("leagues", {})
    classic_leagues = leagues.get("classic", [])

    # Parse classic leagues (filter to reasonable size)
    parsed_classic_leagues = []
    for league in classic_leagues:
        is_public = league.get("league_type") == "s"
        parsed_league = {
            "id": league.get("id"),
            "name": league.get("name"),
            "type": "Public" if is_public else "Private",
            "rank": league.get("entry_rank"),
            "last_rank": league.get("entry_last_rank"),
            "total_teams": league.get("entry_can_leave", False),
            "percentile": league.get("entry_percentile_rank"),
        }
        parsed_classic_leagues.append(parsed_league)

    # Parse cup matches
    cup_matches = leagues.get("cup_matches", [])
    parsed_cup_matches = []
    for match in cup_matches:
        my_entry = data.get("id")
        is_entry1 = match.get("entry_1_entry") == my_entry

        parsed_match = {
            "event": match.get("event"),
            "opponent_name": (
                match.get("entry_1_name")
                if not is_entry1
                else match.get("entry_2_name")
            ),
            "opponent_id": (
                match.get("entry_1_entry")
                if not is_entry1
                else match.get("entry_2_entry")
            ),
            "user_points": (
                match.get("entry_1_points")
                if is_entry1
                else match.get("entry_2_points")
            ),
            "opponent_points": (
                match.get("entry_2_points")
                if is_entry1
                else match.get("entry_1_points")
            ),
            "result": "win" if match.get("winner") == my_entry else "loss",
            "knockout_name": match.get("knockout_name"),
        }
        parsed_cup_matches.append(parsed_match)

    # Parse H2H leagues if available
    h2h_leagues = leagues.get("h2h", [])
    parsed_h2h_leagues = []
    for league in h2h_leagues:
        parsed_h2h = {
            "id": league.get("id"),
            "name": league.get("name"),
            "rank": league.get("entry_rank"),
            "last_rank": league.get("entry_last_rank"),
        }
        parsed_h2h_leagues.append(parsed_h2h)

    return {
        "classic_leagues": parsed_classic_leagues,
        "h2h_leagues": parsed_h2h_leagues,
        "cup_matches": parsed_cup_matches,
    }


async def _get_manager_info(team_id: Optional[int] = None) -> Dict[str, Any]:
    """Get detailed information about an FPL manager"""
    # Get raw manager data
    data = await get_manager_data(team_id)

    # Check for errors
    if "error" in data:
        return data

    # Parse different sections
    basic_info = parse_manager_basic_info(data)
    performance = parse_manager_performance(data)
    leagues = parse_manager_leagues(data)

    # Return combined data
    return {
        "basic_info": basic_info,
        "performance": performance,
        "leagues": leagues
    }


def register_tools(mcp):
    """Register manager tools with the MCP server"""

    @mcp.tool()
    async def get_manager_info(
        team_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get detailed information about an FPL manager

        Args:
            team_id: FPL team ID (defaults to authenticated user)

        Returns:
            Manager info with leagues and performance stats
        """
        return await _get_manager_info(team_id)
