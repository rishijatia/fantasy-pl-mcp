# src/fpl_mcp/fpl/tools/fixtures.py
import logging
from typing import Any, Dict, Optional

from ..cache import get_cached_player_data
from ..resources import fixtures, players, teams
from ..utils.difficulty import assess_fixtures, fixture_score
from ..utils.gameweek import get_current_gameweek_id, get_next_gameweek_id
from ..utils.params import unwrap
from ..utils.position_utils import normalize_position

logger = logging.getLogger(__name__)


def register_tools(mcp):
    """Register fixture analysis tools with the MCP server"""

    @mcp.tool()
    async def analyze_player_fixtures(player_name: str, num_fixtures: int = 5) -> Dict[str, Any]:
        """Analyze upcoming fixtures for a player and provide a difficulty rating

        Args:
            player_name: Player name to search for
            num_fixtures: Number of upcoming fixtures to analyze (default: 5)

        Returns:
            Analysis of player's upcoming fixtures with difficulty ratings
        """
        logger.info(f"Tool called: analyze_player_fixtures({player_name}, {num_fixtures})")

        player_name = unwrap(player_name, "player_name", "query")
        num_fixtures = unwrap(num_fixtures, "num_fixtures", default=5)

        # Find the player
        player_matches = await players.find_players_by_name(player_name)
        if not player_matches:
            return {"error": f"No player found matching '{player_name}'"}

        player = player_matches[0]
        analysis = await fixtures.analyze_player_fixtures(player["id"], num_fixtures)

        return analysis

    @mcp.tool()
    async def analyze_fixtures(
        entity_type: str = "player",
        entity_name: Optional[str] = None,
        num_gameweeks: int = 5,
        include_blanks: bool = True,
        include_doubles: bool = True
    ) -> Dict[str, Any]:
        """Analyze upcoming fixtures for players, teams, or positions

        Args:
            entity_type: Type of entity to analyze ("player", "team", or "position")
            entity_name: Name of the specific entity
            num_gameweeks: Number of gameweeks to look ahead
            include_blanks: Whether to include blank gameweek info
            include_doubles: Whether to include double gameweek info

        Returns:
            Fixture analysis with difficulty ratings and summary
        """
        logger.info(f"Tool called: analyze_fixtures({entity_type}, {entity_name}, ...)")

        entity_type = unwrap(entity_type, "entity_type", default="player")
        entity_name = unwrap(entity_name, "entity_name", "player_name", "query")
        num_gameweeks = unwrap(num_gameweeks, "num_gameweeks", default=5)
        include_blanks = unwrap(include_blanks, "include_blanks", default=True)
        include_doubles = unwrap(include_doubles, "include_doubles", default=True)

        # If entity_name is None, we can't proceed with certain entity types
        if entity_name is None and entity_type in ["player", "team"]:
            return {"error": f"Please provide a {entity_type} name to analyze"}

        # Normalize entity type
        entity_type = entity_type.lower()
        if entity_type not in ["player", "team", "position"]:
            return {"error": f"Invalid entity type: {entity_type}. Must be 'player', 'team', or 'position'"}

        # Get current gameweek, plus the next one still to be played: the
        # analysis window starts there so that gameweek 1 is covered before
        # the season begins rather than being skipped.
        current_gameweek = await get_current_gameweek_id()
        if current_gameweek is None:
            return {"error": "Could not determine current gameweek"}

        next_gameweek = await get_next_gameweek_id()
        if next_gameweek is None:
            next_gameweek = current_gameweek + 1

        # Base result structure
        result = {
            "entity_type": entity_type,
            "entity_name": entity_name,
            "current_gameweek": current_gameweek,
            "analysis_range": list(range(next_gameweek, next_gameweek + num_gameweeks))
        }

        # Handle each entity type
        if entity_type == "player":
            # Find player and their team
            player_matches = await players.find_players_by_name(entity_name)
            if not player_matches:
                return {"error": f"No player found matching '{entity_name}'"}

            player = player_matches[0]
            result["player"] = {
                "id": player["id"],
                "name": player["name"],
                "team": player["team"],
                "position": player["position"],
                "status": "available" if player["status"] == "a" else "unavailable"
            }

            # Get fixtures for player's team
            player_fixtures = await fixtures.get_player_fixtures(player["id"], num_gameweeks)

            score = fixture_score(player_fixtures)

            result["fixtures"] = player_fixtures
            result["fixture_analysis"] = {
                "difficulty_score": score,
                "fixtures_analyzed": len(player_fixtures),
                "home_matches": sum(1 for f in player_fixtures if f["location"] == "home"),
                "away_matches": sum(1 for f in player_fixtures if f["location"] == "away"),
                "assessment": assess_fixtures(score),
            }

        elif entity_type == "team":
            # Find team
            team = await teams.get_team_by_name(entity_name)
            if not team:
                return {"error": f"No team found matching '{entity_name}'"}

            result["team"] = {
                "id": team["id"],
                "name": team["name"],
                "short_name": team["short_name"]
            }

            # Get fixtures for team
            team_fixtures = await fixtures.get_fixtures_resource(team_name=team["name"])

            # Filter to upcoming fixtures
            upcoming_fixtures = [
                f for f in team_fixtures
                if f["gameweek"] in result["analysis_range"]
            ]

            # Format fixtures
            formatted_fixtures = []
            for fixture in upcoming_fixtures:
                is_home = fixture["home_team"]["name"] == team["name"]
                opponent = fixture["away_team"] if is_home else fixture["home_team"]
                difficulty = fixture["difficulty"]["home" if is_home else "away"]

                formatted_fixtures.append({
                    "gameweek": fixture["gameweek"],
                    "opponent": opponent["name"],
                    "location": "home" if is_home else "away",
                    "difficulty": difficulty
                })

            result["fixtures"] = formatted_fixtures

            # Calculate difficulty metrics
            if formatted_fixtures:
                score = fixture_score(formatted_fixtures)

                result["fixture_analysis"] = {
                    "difficulty_score": score,
                    "fixtures_analyzed": len(formatted_fixtures),
                    "home_matches": sum(1 for f in formatted_fixtures if f["location"] == "home"),
                    "away_matches": sum(1 for f in formatted_fixtures if f["location"] == "away"),
                    "assessment": assess_fixtures(score),
                }
            else:
                result["fixture_analysis"] = {
                    "difficulty_score": 0,
                    "fixtures_analyzed": 0,
                    "assessment": "No upcoming fixtures found"
                }

        elif entity_type == "position":
            # Normalize position
            normalized_position = normalize_position(entity_name)
            if not normalized_position or normalized_position not in ["GKP", "DEF", "MID", "FWD"]:
                return {"error": f"Invalid position: {entity_name}"}

            result["position"] = normalized_position

            # Get all players in this position
            all_players = await get_cached_player_data()
            position_players = [p for p in all_players if p.get("position") == normalized_position]

            # Get teams with players in this position
            teams_with_position = set(p.get("team") for p in position_players)

            # Get upcoming fixtures for these teams
            all_fixtures = await fixtures.get_fixtures_resource()
            upcoming_fixtures = [
                f for f in all_fixtures
                if f["gameweek"] in result["analysis_range"]
            ]

            # Calculate average fixture difficulty by team
            team_difficulties = {}

            for team in teams_with_position:
                team_fixtures = []

                for fixture in upcoming_fixtures:
                    is_home = fixture["home_team"]["name"] == team
                    is_away = fixture["away_team"]["name"] == team

                    if is_home or is_away:
                        difficulty = fixture["difficulty"]["home" if is_home else "away"]
                        team_fixtures.append({
                            "gameweek": fixture["gameweek"],
                            "opponent": fixture["away_team"]["name"] if is_home else fixture["home_team"]["name"],
                            "location": "home" if is_home else "away",
                            "difficulty": difficulty
                        })

                if team_fixtures:
                    team_difficulties[team] = {
                        "fixtures": team_fixtures,
                        "difficulty_score": fixture_score(team_fixtures),
                        "fixtures_analyzed": len(team_fixtures)
                    }

            # Sort teams by fixture difficulty (best first)
            sorted_teams = sorted(
                team_difficulties.items(),
                key=lambda x: x[1]["difficulty_score"],
                reverse=True
            )

            result["team_fixtures"] = {
                team: data for team, data in sorted_teams[:10]  # Top 10 teams with best fixtures
            }

            # Add recommendation of teams with best fixtures
            if sorted_teams:
                best_teams = [team for team, data in sorted_teams[:3]]
                result["recommendations"] = {
                    "teams_with_best_fixtures": best_teams,
                    "analysis": f"Teams with players in position {normalized_position} with the best upcoming fixtures: {', '.join(best_teams)}"
                }

        # Add blank and double gameweek information if requested
        if include_blanks:
            blank_gameweeks = await fixtures.get_blank_gameweeks(num_gameweeks)
            result["blank_gameweeks"] = blank_gameweeks

        if include_doubles:
            double_gameweeks = await fixtures.get_double_gameweeks(num_gameweeks)
            result["double_gameweeks"] = double_gameweeks

        return result
