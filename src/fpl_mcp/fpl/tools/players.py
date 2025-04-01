"""Player information tools for Fantasy Premier League."""

import logging
from typing import Any, Dict, Optional

from ..resources.players import get_player_by_id, find_players_by_name
from ..resources.gameweeks import get_current_gameweek_resource
from ..resources.fixtures import get_player_fixtures, get_player_gameweek_history


async def get_player_info(
    player_id: Optional[int] = None,
    player_name: Optional[str] = None,
    start_gameweek: Optional[int] = None,
    end_gameweek: Optional[int] = None,
    include_history: bool = True,
    include_fixtures: bool = True
) -> Dict[str, Any]:
    """
    Get detailed information for a specific player, optionally filtering stats by gameweek range.

    Args:
        player_id: FPL player ID (if provided, takes precedence over player_name)
        player_name: Player name to search for (used if player_id not provided)
        start_gameweek: Starting gameweek for filtering player history
        end_gameweek: Ending gameweek for filtering player history
        include_history: Whether to include gameweek-by-gameweek history
        include_fixtures: Whether to include upcoming fixtures

    Returns:
        Detailed player information including stats and history
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Getting player info: ID={player_id}, name={player_name}")

    # Get current gameweek
    current_gw_info = await get_current_gameweek_resource()
    current_gw = current_gw_info.get("id", 1)

    # Find player by ID or name
    player = None
    if player_id is not None:
        player = await get_player_by_id(player_id)
    elif player_name:
        matches = await find_players_by_name(player_name)
        if matches:
            player = matches[0]
            player_id = player.get("id")

    if not player:
        return {
            "error": f"Player not found: ID={player_id}, name={player_name}"
        }

    # Prepare result with basic player info
    result = {
        "player_id": player.get("id"),
        "name": player.get("name"),
        "web_name": player.get("web_name"),
        "team": player.get("team"),
        "team_short": player.get("team_short"),
        "position": player.get("position"),
        "price": player.get("price"),
        "season_stats": {
            "total_points": player.get("points"),
            "points_per_game": player.get("points_per_game"),
            "minutes": player.get("minutes"),
            "goals": player.get("goals"),
            "assists": player.get("assists"),
            "clean_sheets": player.get("clean_sheets"),
            "bonus": player.get("bonus"),
            "form": player.get("form"),
        },
        "ownership": {
            "selected_by_percent": player.get("selected_by_percent"),
            "transfers_in_event": player.get("transfers_in_event"),
            "transfers_out_event": player.get("transfers_out_event"),
        },
        "status": {
            "status": "available" if player.get("status") == "a" else "unavailable",
            "news": player.get("news"),
            "chance_of_playing_next_round": player.get("chance_of_playing_next_round"),
        }
    }

    # Add expected stats if available
    if "expected_goals" in player:
        result["expected_stats"] = {
            "expected_goals": player.get("expected_goals"),
            "expected_assists": player.get("expected_assists"),
            "expected_goal_involvements": player.get("expected_goal_involvements"),
            "expected_goals_conceded": player.get("expected_goals_conceded"),
        }

    # Add advanced metrics
    result["advanced_metrics"] = {
        "influence": player.get("influence"),
        "creativity": player.get("creativity"),
        "threat": player.get("threat"),
        "ict_index": player.get("ict_index"),
        "bps": player.get("bps"),
    }

    # Determine and validate gameweek range
    # Convert Optional[int] to int with defaults
    start_gw: int = 1 if start_gameweek is None else max(1, start_gameweek)
    end_gw: int = current_gw if end_gameweek is None else min(current_gw, end_gameweek)
    
    # Ensure start <= end
    if start_gw > end_gw:
        start_gw = end_gw
        
    # Set the validated values as int (not Optional[int])
    start_gameweek = start_gw
    end_gameweek = end_gw

    # Include gameweek history if requested
    if include_history and "history" in player:
        # Filter history by gameweek range
        filtered_history = [
            gw for gw in player.get("history", [])
            if start_gameweek <= gw.get("round", 0) <= end_gameweek
        ]

        # Get detailed gameweek history
        player_id_value = player.get("id")
        if player_id_value is not None:
            gw_count = max(1, end_gameweek - start_gameweek + 1)
            gameweek_history = await get_player_gameweek_history(
                [player_id_value], gw_count)
        else:
            gameweek_history = None

        # Combine data
        history_data = filtered_history

        if gameweek_history and "players" in gameweek_history:
            player_id_str = str(player.get("id", ""))
            if player_id_str in gameweek_history["players"]:
                detailed_history = gameweek_history["players"][player_id_str]

                # Enrich with additional stats if available
                for gw_data in history_data:
                    gw_num = gw_data.get("round")
                    # Find matching detailed gameweek
                    matching_detailed = next((
                        gw for gw in detailed_history
                        if gw.get("round") == gw_num or gw.get("gameweek") == gw_num
                    ), None)

                    if matching_detailed:
                        for key, value in matching_detailed.items():
                            # Don't overwrite existing keys
                            if key not in gw_data:
                                gw_data[key] = value

        # Add summary stats for the filtered period
        period_stats = {}
        if history_data:
            # Calculate sums
            minutes = sum(gw.get("minutes", 0) for gw in history_data)
            points = sum(gw.get("total_points", 0) for gw in history_data)
            goals = sum(gw.get("goals_scored", 0) for gw in history_data)
            assists = sum(gw.get("assists", 0) for gw in history_data)
            bonus = sum(gw.get("bonus", 0) for gw in history_data)
            clean_sheets = sum(gw.get("clean_sheets", 0) for gw in history_data)

            # Calculate averages
            games_played = len(history_data)
            games_started = sum(1 for gw in history_data if gw.get("minutes", 0) >= 60)
            points_per_game = points / games_played if games_played > 0 else 0

            period_stats = {
                "gameweeks_analyzed": games_played,
                "games_started": games_started,
                "minutes": minutes,
                "total_points": points,
                "points_per_game": round(points_per_game, 1),
                "goals": goals,
                "assists": assists,
                "goal_involvements": goals + assists,
                "clean_sheets": clean_sheets,
                "bonus": bonus,
            }

        result["gameweek_range"] = {
            "start": start_gameweek,
            "end": end_gameweek,
        }

        result["gameweek_history"] = history_data
        result["period_stats"] = period_stats

    # Include upcoming fixtures if requested
    if include_fixtures and player_id is not None:
        fixtures_data = await get_player_fixtures(player_id, 5)  # Next 5 fixtures

        if fixtures_data:
            result["upcoming_fixtures"] = fixtures_data

            # Calculate average fixture difficulty
            difficulty_values = [f.get("difficulty", 3) for f in fixtures_data]
            avg_difficulty = (
                sum(difficulty_values) / len(difficulty_values) if difficulty_values else 3
            )

            # Convert to a 1-10 scale where 10 is best (easiest fixtures)
            fixture_score = (6 - avg_difficulty) * 2

            result["fixture_analysis"] = {
                "difficulty_score": round(fixture_score, 1),
                "fixtures_analyzed": len(fixtures_data),
                "home_matches": sum(1 for f in fixtures_data if f.get("location") == "home"),
                "away_matches": sum(1 for f in fixtures_data if f.get("location") == "away"),
            }

            # Add fixture difficulty assessment
            if "fixture_analysis" in result and isinstance(result["fixture_analysis"], dict):
                fixture_analysis = result["fixture_analysis"]
                if fixture_score >= 8:
                    fixture_analysis["assessment"] = "Excellent fixtures"
                elif fixture_score >= 6:
                    fixture_analysis["assessment"] = "Good fixtures"
                elif fixture_score >= 4:
                    fixture_analysis["assessment"] = "Average fixtures"
                else:
                    fixture_analysis["assessment"] = "Difficult fixtures"

    return result


async def search_players(
    query: str,
    position: Optional[str] = None,
    team: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Search for players by name with optional filtering by position and team.

    Args:
        query: Player name or partial name to search for
        position: Optional position filter (GKP, DEF, MID, FWD)
        team: Optional team name filter
        limit: Maximum number of results to return

    Returns:
        List of matching players with details
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Searching players: query={query}, position={position}, team={team}")

    # Find players by name
    matches = await find_players_by_name(query, limit=limit * 2)  # Get more than needed for filtering

    # Apply position filter if specified
    if position and matches:
        matches = [p for p in matches if p.get("position") == position.upper()]

    # Apply team filter if specified
    if team and matches:
        matches = [
            p for p in matches
            if team.lower() in p.get("team", "").lower() or
            team.lower() in p.get("team_short", "").lower()
        ]

    # Limit results
    matches = matches[:limit]

    return {
        "query": query,
        "filters": {
            "position": position,
            "team": team,
        },
        "total_matches": len(matches),
        "players": matches
    }


def register_tools(mcp):
    """Register player-related tools with MCP."""
    @mcp.tool()
    async def get_player_information(
        player_id: Optional[int] = None,
        player_name: Optional[str] = None,
        start_gameweek: Optional[int] = None,
        end_gameweek: Optional[int] = None,
        include_history: bool = True,
        include_fixtures: bool = True
    ) -> Dict[str, Any]:
        """Get detailed information and statistics for a specific player

        Args:
            player_id: FPL player ID (if provided, takes precedence over player_name)
            player_name: Player name to search for (used if player_id not provided)
            start_gameweek: Starting gameweek for filtering player history
            end_gameweek: Ending gameweek for filtering player history
            include_history: Whether to include gameweek-by-gameweek history
            include_fixtures: Whether to include upcoming fixtures

        Returns:
            Comprehensive player information including stats and history
        """
        # Handle case when a dictionary is passed instead of expected types
        if isinstance(player_name, dict):
            if 'player_name' in player_name:
                player_name = player_name['player_name']
            elif 'query' in player_name:
                player_name = player_name['query']
                
        return await get_player_info(
            player_id,
            player_name,
            start_gameweek,
            end_gameweek,
            include_history,
            include_fixtures
        )

    @mcp.tool()
    async def search_fpl_players(
        query: str,
        position: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Search for FPL players by name with optional filtering

        Args:
            query: Player name or partial name to search for
            position: Optional position filter (GKP, DEF, MID, FWD)
            team: Optional team name filter
            limit: Maximum number of results to return

        Returns:
            List of matching players with details
        """
        # Handle case when a dictionary is passed instead of string
        if isinstance(query, dict) and 'query' in query:
            query = query['query']
            
        return await search_players(query, position, team, limit)


# Register tools
register_tools = register_tools