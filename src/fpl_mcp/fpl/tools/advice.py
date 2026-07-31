# src/fpl_mcp/fpl/tools/advice.py
import logging
from typing import Any, Dict, Optional

from ..api import api
from ..auth_manager import get_auth_manager
from ..cache import get_player_map
from ..resources.fixtures import get_player_fixtures
from ..utils.concurrency import gather_limited
from ..utils.difficulty import assess_fixtures, fixture_score
from ..utils.gameweek import get_current_gameweek_id
from ..utils.params import unwrap

logger = logging.getLogger(__name__)

_POSITIONS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# Weights for the captain score; components are all roughly on a 0-10 scale
_WEIGHTS = {
    "expected_points": 0.35,
    "form": 0.25,
    "points_per_game": 0.20,
    "fixtures": 0.20,
}


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def register_tools(mcp):
    """Register advice tools with the MCP server"""

    @mcp.tool()
    async def suggest_captain(
        team_id: Optional[int] = None,
        gameweek_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Suggest who to captain from a team's current squad, ranked with reasoning

        Combines FPL's own expected points (ep_next), form, points per game,
        and upcoming fixture difficulty into a transparent captain score.

        Args:
            team_id: FPL team ID (defaults to your authenticated team)
            gameweek_id: Gameweek whose squad to analyze (defaults to current)

        Returns:
            Squad ranked by captain score with per-component breakdown
        """
        logger.info(f"Tool called: suggest_captain({team_id}, {gameweek_id})")

        team_id = unwrap(team_id, "team_id", default=None)
        gameweek_id = unwrap(gameweek_id, "gameweek_id", default=None)

        auth_manager = get_auth_manager()
        if team_id is None:
            team_id = auth_manager.team_id
        if not team_id:
            return {
                "error": "No team ID provided and no authenticated team found",
                "suggestion": "Pass team_id, or run 'fpl-mcp-config setup' to store your credentials",
            }

        if gameweek_id is None:
            gameweek_id = await get_current_gameweek_id()
            if gameweek_id is None:
                return {"error": "Could not determine current gameweek"}

        try:
            picks_data = await auth_manager.get_team_for_gameweek(int(team_id), gameweek_id)
        except Exception as e:
            return {"error": f"Could not fetch squad for team {team_id}, gameweek {gameweek_id}: {e}"}

        picks = picks_data.get("picks", [])
        if not picks:
            return {"error": f"No squad found for team {team_id} in gameweek {gameweek_id}"}

        player_map = await get_player_map()
        teams = await api.get_teams()
        team_names = {t["id"]: t.get("name", "Unknown") for t in teams}

        player_ids = [p.get("element") for p in picks if p.get("element")]

        # Fetch each squad player's next fixtures concurrently
        fixtures_lists = await gather_limited(
            (get_player_fixtures(pid, 3) for pid in player_ids),
            limit=5,
            return_exceptions=True,
        )

        candidates = []
        for pick, player_fixtures in zip(picks, fixtures_lists):
            pid = pick.get("element")
            info = player_map.get(pid)
            if not info:
                continue

            if isinstance(player_fixtures, Exception):
                logger.warning(f"Could not fetch fixtures for player {pid}: {player_fixtures}")
                player_fixtures = []

            expected_points = _to_float(info.get("ep_next"))
            form = _to_float(info.get("form"))
            ppg = _to_float(info.get("points_per_game"))
            fix_score = fixture_score(player_fixtures)

            score = (
                expected_points * _WEIGHTS["expected_points"]
                + form * _WEIGHTS["form"]
                + ppg * _WEIGHTS["points_per_game"]
                + fix_score * _WEIGHTS["fixtures"]
            )

            # Penalize doubtful or unavailable players
            availability = 1.0
            if info.get("status") != "a":
                chance = info.get("chance_of_playing_next_round")
                availability = (chance / 100.0) if isinstance(chance, (int, float)) else 0.5
            score *= availability

            next_fixture = player_fixtures[0] if player_fixtures else None

            candidates.append({
                "id": pid,
                "name": info.get("web_name", f"Player {pid}"),
                "team": team_names.get(info.get("team"), "Unknown"),
                "position": _POSITIONS.get(info.get("element_type"), "UNK"),
                "captain_score": round(score, 2),
                "components": {
                    "expected_points_next": expected_points,
                    "form": form,
                    "points_per_game": ppg,
                    "fixture_score": fix_score,
                    "fixture_assessment": assess_fixtures(fix_score),
                    "availability": availability,
                },
                "next_fixture": next_fixture,
                "ownership_percent": info.get("selected_by_percent"),
                "status": "available" if info.get("status") == "a" else "doubtful/unavailable",
                "news": info.get("news", ""),
                "was_captain": bool(pick.get("is_captain")),
            })

        candidates.sort(key=lambda c: c["captain_score"], reverse=True)

        top = candidates[0] if candidates else None
        return {
            "team_id": int(team_id),
            "gameweek": gameweek_id,
            "recommendation": top and {
                "name": top["name"],
                "captain_score": top["captain_score"],
                "reason": (
                    f"{top['name']} leads on captain score "
                    f"({top['captain_score']}): expected points "
                    f"{top['components']['expected_points_next']}, form "
                    f"{top['components']['form']}, "
                    f"{top['components']['fixture_assessment'].lower()}"
                ),
            },
            "candidates": candidates,
            "methodology": {
                "description": "Weighted blend of FPL expected points (ep_next), form, points per game, and upcoming fixture difficulty; doubtful players are scaled by availability",
                "weights": _WEIGHTS,
            },
        }
