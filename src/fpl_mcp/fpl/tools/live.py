# src/fpl_mcp/fpl/tools/live.py
import logging
from typing import Any, Dict, List, Optional

from ..api import api
from ..cache import get_player_map
from ..utils.gameweek import get_current_gameweek_id
from ..utils.params import unwrap

logger = logging.getLogger(__name__)


async def _team_name_maps():
    teams = await api.get_teams()
    return (
        {t["id"]: t.get("name", "Unknown") for t in teams},
        {t["id"]: t.get("short_name", "") for t in teams},
    )

_POSITIONS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def register_tools(mcp):
    """Register live gameweek tools with the MCP server"""

    @mcp.tool()
    async def get_gameweek_live_scores(
        gameweek_id: Optional[int] = None,
        player_ids: Optional[List[int]] = None,
        limit: int = 25
    ) -> Dict[str, Any]:
        """Get live player points and stats for a gameweek while matches are being played

        Args:
            gameweek_id: Gameweek to fetch (defaults to the current gameweek)
            player_ids: Optional list of FPL player IDs to restrict the result to
            limit: Maximum number of players to return when player_ids is not given

        Returns:
            Live scores sorted by points, plus bonus-processing status
        """
        logger.info(f"Tool called: get_gameweek_live_scores({gameweek_id}, {player_ids})")

        gameweek_id = unwrap(gameweek_id, "gameweek_id", default=None)
        player_ids = unwrap(player_ids, "player_ids", default=None)
        limit = unwrap(limit, "limit", default=25)

        if gameweek_id is None:
            gameweek_id = await get_current_gameweek_id()
            if gameweek_id is None:
                return {"error": "Could not determine current gameweek"}

        try:
            live_data = await api.get_live_event_data(gameweek_id)
        except Exception as e:
            return {"error": f"Could not fetch live data for gameweek {gameweek_id}: {e}"}

        player_map = await get_player_map()
        team_names, team_short = await _team_name_maps()

        wanted = set(player_ids) if player_ids else None
        players = []
        for element in live_data.get("elements", []):
            pid = element.get("id")
            if wanted is not None and pid not in wanted:
                continue

            stats = element.get("stats", {})
            info = player_map.get(pid, {})
            players.append({
                "id": pid,
                "name": info.get("web_name", f"Player {pid}"),
                "team": team_names.get(info.get("team"), "Unknown"),
                "team_short": team_short.get(info.get("team"), ""),
                "position": _POSITIONS.get(info.get("element_type"), "UNK"),
                "points": stats.get("total_points", 0),
                "minutes": stats.get("minutes", 0),
                "goals": stats.get("goals_scored", 0),
                "assists": stats.get("assists", 0),
                "clean_sheets": stats.get("clean_sheets", 0),
                "saves": stats.get("saves", 0),
                "bonus": stats.get("bonus", 0),
                "bps": stats.get("bps", 0),
                "yellow_cards": stats.get("yellow_cards", 0),
                "red_cards": stats.get("red_cards", 0),
                "expected_goals": stats.get("expected_goals", "0.0"),
                "expected_assists": stats.get("expected_assists", "0.0"),
                "in_dreamteam": stats.get("in_dreamteam", False),
            })

        # Sort by live points; when specific players were requested keep them all
        players.sort(key=lambda p: (p["points"], p["bps"]), reverse=True)
        played = [p for p in players if p["minutes"] > 0]
        if wanted is None:
            players = played[:limit]

        # Bonus-processing status for context
        bonus_added = None
        try:
            status_data = await api.get_event_status()
            day_statuses = [
                s for s in status_data.get("status", [])
                if s.get("event") == gameweek_id
            ]
            if day_statuses:
                bonus_added = all(s.get("bonus_added", False) for s in day_statuses)
        except Exception as e:
            logger.warning(f"Could not fetch event status: {e}")

        return {
            "gameweek": gameweek_id,
            "bonus_added": bonus_added,
            "players_with_minutes": len(played),
            "players": players,
            "note": (
                "Points are live and may change until the gameweek is finalized"
                if bonus_added is not True
                else "Bonus points have been added for this gameweek"
            ),
        }

    @mcp.tool()
    async def get_dream_team(gameweek_id: Optional[int] = None) -> Dict[str, Any]:
        """Get the official dream team (highest-scoring XI) for a gameweek

        Args:
            gameweek_id: Gameweek to fetch (defaults to the current gameweek)

        Returns:
            The dream team with player names, teams, positions, and points
        """
        logger.info(f"Tool called: get_dream_team({gameweek_id})")

        gameweek_id = unwrap(gameweek_id, "gameweek_id", default=None)

        if gameweek_id is None:
            gameweek_id = await get_current_gameweek_id()
            if gameweek_id is None:
                return {"error": "Could not determine current gameweek"}

        try:
            dream_data = await api.get_dream_team(gameweek_id)
        except Exception as e:
            return {"error": f"Could not fetch dream team for gameweek {gameweek_id}: {e}"}

        player_map = await get_player_map()
        team_names, _ = await _team_name_maps()

        def format_entry(entry):
            pid = entry.get("element")
            info = player_map.get(pid, {})
            return {
                "id": pid,
                "name": info.get("web_name", f"Player {pid}"),
                "team": team_names.get(info.get("team"), "Unknown"),
                "position": _POSITIONS.get(info.get("element_type"), "UNK"),
                "points": entry.get("points", 0),
            }

        team = [format_entry(e) for e in dream_data.get("team", [])]

        top = dream_data.get("top_player") or {}
        top_info = player_map.get(top.get("id"), {})

        return {
            "gameweek": gameweek_id,
            "team": team,
            "total_points": sum(p["points"] for p in team),
            "top_player": {
                "id": top.get("id"),
                "name": top_info.get("web_name", "Unknown"),
                "points": top.get("points", 0),
            },
        }
