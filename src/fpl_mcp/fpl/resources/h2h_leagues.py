# src/fpl_mcp/fpl/resources/h2h_leagues.py
import logging
from typing import Dict, Any, List, Optional

from ..auth_manager import get_auth_manager
from ..cache import cached
from ...config import FPL_API_BASE_URL

logger = logging.getLogger(__name__)


@cached("h2h_standings", ttl=3600)
async def get_h2h_standings(league_id: int, page_new_entries: int = 1, page_standings: int = 1) -> Dict[str, Any]:
    """
    Get H2H league standings

    Args:
        league_id: ID of the H2H league
        page_new_entries: Page number for new entries (default: 1)
        page_standings: Page number for standings (default: 1)

    Returns:
        H2H league standings data
    """
    auth_manager = get_auth_manager()

    # Construct the URL with query parameters
    url = f"{FPL_API_BASE_URL}/leagues-h2h/{league_id}/standings/?page_new_entries={page_new_entries}&page_standings={page_standings}"

    try:
        data = await auth_manager.make_authed_request(url)
        return data
    except Exception as e:
        logger.error(f"Error fetching H2H league standings: {e}")
        return {
            "error": f"Failed to retrieve H2H league standings: {str(e)}"
        }


@cached("h2h_fixtures", ttl=1800)  # 30 minute TTL for fixtures
async def get_h2h_fixtures(league_id: int, event: Optional[int] = None, page: int = 1) -> Dict[str, Any]:
    """
    Get H2H league fixtures/matches for a specific gameweek

    Args:
        league_id: ID of the H2H league
        event: Gameweek number (event ID). If None, returns all fixtures
        page: Page number (default: 1)

    Returns:
        H2H league fixtures data
    """
    auth_manager = get_auth_manager()

    # Construct the URL with query parameters
    if event is not None:
        url = f"{FPL_API_BASE_URL}/leagues-h2h-matches/league/{league_id}/?page={page}&event={event}"
    else:
        url = f"{FPL_API_BASE_URL}/leagues-h2h-matches/league/{league_id}/?page={page}"

    try:
        data = await auth_manager.make_authed_request(url)
        return data
    except Exception as e:
        logger.error(f"Error fetching H2H league fixtures: {e}")
        return {
            "error": f"Failed to retrieve H2H league fixtures: {str(e)}"
        }


@cached("h2h_entries", ttl=3600)
async def get_h2h_entries(league_id: int) -> Dict[str, Any]:
    """
    Get all entries (teams) in an H2H league

    Args:
        league_id: ID of the H2H league

    Returns:
        H2H league entries data
    """
    auth_manager = get_auth_manager()

    # Construct the URL
    url = f"{FPL_API_BASE_URL}/league/{league_id}/entries/"

    try:
        data = await auth_manager.make_authed_request(url)
        return data
    except Exception as e:
        logger.error(f"Error fetching H2H league entries: {e}")
        return {
            "error": f"Failed to retrieve H2H league entries: {str(e)}"
        }


def parse_h2h_standings(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse H2H league standings data into a more usable format

    Args:
        data: Raw H2H standings data from the API

    Returns:
        Parsed H2H standings data
    """
    if "error" in data:
        return data

    # Parse league info
    league_info = {
        "id": data.get("league", {}).get("id"),
        "name": data.get("league", {}).get("name"),
        "created": data.get("league", {}).get("created"),
        "type": "H2H",
        "scoring": data.get("league", {}).get("scoring"),
        "admin_entry": data.get("league", {}).get("admin_entry"),
        "start_event": data.get("league", {}).get("start_event"),
    }

    # Parse standings
    standings = data.get("standings", {}).get("results", [])

    formatted_standings = []
    for standing in standings:
        team = {
            "id": standing.get("id"),
            "team_id": standing.get("entry"),
            "team_name": standing.get("entry_name"),
            "manager_name": standing.get("player_name"),
            "rank": standing.get("rank"),
            "last_rank": standing.get("last_rank"),
            "rank_change": standing.get("rank_sort") - standing.get("last_rank") if standing.get("last_rank") and standing.get("rank_sort") else 0,
            "matches_won": standing.get("matches_won"),
            "matches_drawn": standing.get("matches_drawn"),
            "matches_lost": standing.get("matches_lost"),
            "matches_played": standing.get("matches_played"),
            "points_for": standing.get("points_for"),
            "total_points": standing.get("total"),
        }
        formatted_standings.append(team)

    return {
        "league_info": league_info,
        "standings": formatted_standings,
        "total_teams": len(formatted_standings),
        "has_next": data.get("standings", {}).get("has_next", False),
        "page": data.get("standings", {}).get("page", 1),
    }


def parse_h2h_fixtures(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse H2H league fixtures data into a more usable format

    Args:
        data: Raw H2H fixtures data from the API

    Returns:
        Parsed H2H fixtures data
    """
    if "error" in data:
        return data

    results = data.get("results", [])

    formatted_fixtures = []
    for fixture in results:
        match = {
            "id": fixture.get("id"),
            "event": fixture.get("event"),
            "finished": fixture.get("finished"),
            "started": fixture.get("started"),
            "entry_1_entry": fixture.get("entry_1_entry"),
            "entry_1_name": fixture.get("entry_1_name"),
            "entry_1_player_name": fixture.get("entry_1_player_name"),
            "entry_1_points": fixture.get("entry_1_points"),
            "entry_2_entry": fixture.get("entry_2_entry"),
            "entry_2_name": fixture.get("entry_2_name"),
            "entry_2_player_name": fixture.get("entry_2_player_name"),
            "entry_2_points": fixture.get("entry_2_points"),
            "winner": None,
        }

        # Determine winner
        if fixture.get("finished"):
            if fixture.get("entry_1_points") > fixture.get("entry_2_points"):
                match["winner"] = fixture.get("entry_1_entry")
            elif fixture.get("entry_2_points") > fixture.get("entry_1_points"):
                match["winner"] = fixture.get("entry_2_entry")
            else:
                match["winner"] = "draw"

        formatted_fixtures.append(match)

    return {
        "fixtures": formatted_fixtures,
        "total_fixtures": len(formatted_fixtures),
        "has_next": data.get("has_next", False),
        "page": data.get("page", 1),
    }


def parse_h2h_entries(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse H2H league entries data into a more usable format

    Args:
        data: Raw H2H entries data from the API

    Returns:
        Parsed H2H entries data
    """
    if "error" in data:
        return data

    results = data.get("results", [])

    formatted_entries = []
    for entry in results:
        team = {
            "id": entry.get("id"),
            "team_id": entry.get("entry"),
            "team_name": entry.get("entry_name"),
            "manager_name": entry.get("player_name"),
            "joined_time": entry.get("joined_time"),
        }
        formatted_entries.append(team)

    return {
        "entries": formatted_entries,
        "total_entries": len(formatted_entries),
    }
