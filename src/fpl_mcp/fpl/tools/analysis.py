# src/fpl_mcp/fpl/tools/analysis.py
import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from ..cache import get_cached_player_data
from ..resources import fixtures, players
from ..utils.params import unwrap
from ..utils.position_utils import normalize_position

logger = logging.getLogger(__name__)


def register_tools(mcp):
    """Register player analysis and comparison tools with the MCP server"""

    @mcp.tool()
    async def analyze_players(
        position: Optional[str] = None,
        team: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_points: Optional[int] = None,
        min_ownership: Optional[float] = None,
        max_ownership: Optional[float] = None,
        form_threshold: Optional[float] = None,
        include_gameweeks: bool = False,
        num_gameweeks: int = 5,
        sort_by: str = "total_points",
        sort_order: str = "desc",
        limit: int = 20
    ) -> Dict[str, Any]:
        """Filter and analyze FPL players based on multiple criteria

        Args:
            position: Player position (e.g., "midfielders", "defenders")
            team: Team name filter
            min_price: Minimum player price in millions
            max_price: Maximum player price in millions
            min_points: Minimum total points
            min_ownership: Minimum ownership percentage
            max_ownership: Maximum ownership percentage
            form_threshold: Minimum form rating
            include_gameweeks: Whether to include gameweek-by-gameweek data
            num_gameweeks: Number of recent gameweeks to include
            sort_by: Metric to sort results by (default: total_points)
            sort_order: Sort direction ("asc" or "desc")
            limit: Maximum number of players to return

        Returns:
            Filtered player data with summary statistics
        """
        logger.info(f"Tool called: analyze_players({position}, {team}, ...)")

        position = unwrap(position, "position", default=None)
        team = unwrap(team, "team", default=None)
        min_price = unwrap(min_price, "min_price", default=None)
        max_price = unwrap(max_price, "max_price", default=None)
        min_points = unwrap(min_points, "min_points", default=None)
        min_ownership = unwrap(min_ownership, "min_ownership", default=None)
        max_ownership = unwrap(max_ownership, "max_ownership", default=None)
        form_threshold = unwrap(form_threshold, "form_threshold", default=None)
        include_gameweeks = unwrap(include_gameweeks, "include_gameweeks", default=False)
        num_gameweeks = unwrap(num_gameweeks, "num_gameweeks", default=5)
        sort_by = unwrap(sort_by, "sort_by", default="total_points")
        sort_order = unwrap(sort_order, "sort_order", default="desc")
        limit = unwrap(limit, "limit", default=20)

        # Get cached complete player dataset
        all_players = await get_cached_player_data()

        # Normalize position if provided
        normalized_position = normalize_position(position) if position else None
        position_changed = normalized_position != position if position else False

        # Apply all filters
        filtered_players = []
        for player in all_players:
            # Check position filter
            if normalized_position and player.get("position") != normalized_position:
                continue

            # Check team filter
            if team and not (
                team.lower() in player.get("team", "").lower() or
                team.lower() in player.get("team_short", "").lower()
            ):
                continue

            # Check price range
            if min_price is not None and player.get("price", 0) < min_price:
                continue
            if max_price is not None and player.get("price", 0) > max_price:
                continue

            # Check points threshold
            if min_points is not None and player.get("points", 0) < min_points:
                continue

            # Check ownership range
            try:
                ownership = float(player.get("selected_by_percent", 0).replace("%", ""))
                if min_ownership is not None and ownership < min_ownership:
                    continue
                if max_ownership is not None and ownership > max_ownership:
                    continue
            except (ValueError, TypeError):
                # Skip ownership check if value can't be converted
                pass

            # Check form threshold
            try:
                form = float(player.get("form", 0))
                if form_threshold is not None and form < form_threshold:
                    continue
            except (ValueError, TypeError):
                # Skip form check if value can't be converted
                pass

            player['status'] = "available" if player.get("status") == "a" else "unavailable"

            # Player passed all filters
            filtered_players.append(player)

        # Sort results
        reverse = sort_order.lower() != "asc"
        try:
            # Handle numeric sorting properly
            numeric_fields = ["points", "price", "form", "selected_by_percent", "value"]
            if sort_by in numeric_fields:
                filtered_players.sort(
                    key=lambda p: float(p.get(sort_by, 0))
                    if p.get(sort_by) is not None else 0,
                    reverse=reverse
                )
            else:
                filtered_players.sort(
                    key=lambda p: p.get(sort_by, ""),
                    reverse=reverse
                )
        except (KeyError, ValueError):
            # Fall back to points sorting
            filtered_players.sort(
                key=lambda p: float(p.get("points", 0)),
                reverse=True
            )

        # Calculate summary statistics
        total_players = len(filtered_players)
        average_points = sum(float(p.get("points", 0)) for p in filtered_players) / max(1, total_players)
        average_price = sum(float(p.get("price", 0)) for p in filtered_players) / max(1, total_players)

        # Count position and team distributions
        position_counts = Counter(p.get("position") for p in filtered_players)
        team_counts = Counter(p.get("team") for p in filtered_players)

        # Build filter description
        applied_filters = []
        if normalized_position:
            applied_filters.append(f"Position: {normalized_position}")
        if team:
            applied_filters.append(f"Team: {team}")
        if min_price is not None:
            applied_filters.append(f"Min price: £{min_price}m")
        if max_price is not None:
            applied_filters.append(f"Max price: £{max_price}m")
        if min_points is not None:
            applied_filters.append(f"Min points: {min_points}")
        if min_ownership is not None:
            applied_filters.append(f"Min ownership: {min_ownership}%")
        if max_ownership is not None:
            applied_filters.append(f"Max ownership: {max_ownership}%")
        if form_threshold is not None:
            applied_filters.append(f"Min form: {form_threshold}")

        # Build results with summary and detail sections
        result = {
            "summary": {
                "total_matches": total_players,
                "filters_applied": applied_filters,
                "average_points": round(average_points, 1),
                "average_price": round(average_price, 2),
                "position_distribution": dict(position_counts),
                "team_distribution": dict(sorted(
                    team_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]),  # Top 10 teams
            },
            "players": filtered_players[:limit]  # Apply limit to detailed results
        }

        # Add position normalization note if relevant
        if position_changed:
            result["summary"]["position_note"] = f"'{position}' was interpreted as '{normalized_position}'"

        # Include gameweek history if requested
        if include_gameweeks and filtered_players:
            try:
                # Get history for top players (limit)
                player_ids = [p.get("id") for p in filtered_players[:limit]]
                gameweek_data = await fixtures.get_player_gameweek_history(player_ids, num_gameweeks)

                # Add gameweek data to the result
                result["gameweek_data"] = gameweek_data

                # Calculate and add recent form stats based on gameweek history
                recent_form_stats = {}

                if "players" in gameweek_data:
                    for player_id, history in gameweek_data["players"].items():
                        player_id = int(player_id)

                        # Find matching player in our filtered list
                        player_info = next((p for p in filtered_players if p.get("id") == player_id), None)
                        if not player_info:
                            continue

                        # Initialize stats
                        recent_stats = {
                            "player_name": player_info.get("name", "Unknown"),
                            "matches": len(history),
                            "minutes": 0,
                            "points": 0,
                            "goals": 0,
                            "assists": 0,
                            "clean_sheets": 0,
                            "bonus": 0,
                            "expected_goals": 0,
                            "expected_assists": 0,
                            "expected_goal_involvements": 0,
                            "points_per_game": 0,
                            "gameweeks_analyzed": gameweek_data.get("gameweeks", [])
                        }

                        # Sum up stats from gameweek history
                        for gw in history:
                            recent_stats["minutes"] += gw.get("minutes", 0)
                            recent_stats["points"] += gw.get("points", 0)
                            recent_stats["goals"] += gw.get("goals", 0)
                            recent_stats["assists"] += gw.get("assists", 0)
                            recent_stats["clean_sheets"] += gw.get("clean_sheets", 0)
                            recent_stats["bonus"] += gw.get("bonus", 0)
                            recent_stats["expected_goals"] += float(gw.get("expected_goals", 0))
                            recent_stats["expected_assists"] += float(gw.get("expected_assists", 0))
                            recent_stats["expected_goal_involvements"] += float(gw.get("expected_goal_involvements", 0))

                        # Calculate averages
                        if recent_stats["matches"] > 0:
                            recent_stats["points_per_game"] = round(recent_stats["points"] / recent_stats["matches"], 1)

                        # Round floating point values
                        recent_stats["expected_goals"] = round(recent_stats["expected_goals"], 2)
                        recent_stats["expected_assists"] = round(recent_stats["expected_assists"], 2)
                        recent_stats["expected_goal_involvements"] = round(recent_stats["expected_goal_involvements"], 2)

                        recent_form_stats[str(player_id)] = recent_stats

                # Add recent form stats to result
                result["recent_form"] = {
                    "description": f"Stats for the last {num_gameweeks} gameweeks only",
                    "player_stats": recent_form_stats
                }

                # Add labels to clarify which stats are season-long vs. recent
                for player in result["players"]:
                    player["stats_type"] = "season_totals"

            except Exception as e:
                logger.error(f"Error fetching gameweek data: {e}")
                result["gameweek_data_error"] = str(e)

        return result

    @mcp.tool()
    async def compare_players(
        player_names: List[str],
        metrics: List[str] = ["total_points", "form", "goals_scored", "assists", "bonus"],
        include_gameweeks: bool = False,
        num_gameweeks: int = 5,
        include_fixture_analysis: bool = True
    ) -> Dict[str, Any]:
        """Compare multiple players across various metrics

        Args:
            player_names: List of player names to compare (2-5 players recommended)
            metrics: List of metrics to compare
            include_gameweeks: Whether to include gameweek-by-gameweek comparison
            num_gameweeks: Number of recent gameweeks to include in comparison
            include_fixture_analysis: Whether to include fixture analysis including blanks and doubles

        Returns:
            Detailed comparison of players across the specified metrics
        """
        logger.info(f"Tool called: compare_players({player_names}, ...)")

        if isinstance(player_names, dict):
            player_names = unwrap(player_names, "player_names", default=None)
            if player_names is None:
                return {"error": "Could not find player names in the provided data"}

        metrics = unwrap(
            metrics, "metrics",
            default=["total_points", "form", "goals_scored", "assists", "bonus"],
        )
        include_gameweeks = unwrap(include_gameweeks, "include_gameweeks", default=False)
        num_gameweeks = unwrap(num_gameweeks, "num_gameweeks", default=5)
        include_fixture_analysis = unwrap(
            include_fixture_analysis, "include_fixture_analysis", default=True
        )

        if not player_names or len(player_names) < 2:
            return {"error": "Please provide at least two player names to compare"}

        # Find all players by name
        players_data = {}
        for name in player_names:
            matches = await players.find_players_by_name(name, limit=3)  # Get more matches to find active players
            if not matches:
                return {"error": f"No player found matching '{name}'"}

            # Use first match
            player = matches[0]
            players_data[name] = player

        # Build comparison structure
        comparison = {
            "players": {
                name: {
                    "id": player["id"],
                    "name": player["name"],
                    "team": player["team"],
                    "position": player["position"],
                    "price": player["price"],
                    "status": "available" if player["status"] == "a" else "unavailable",
                    "news": player.get("news", ""),
                } for name, player in players_data.items()
            },
            "metrics_comparison": {}
        }

        # Compare all requested metrics
        for metric in metrics:
            metric_values = {}

            for name, player in players_data.items():
                if metric in player:
                    # Try to convert to numeric if possible
                    try:
                        value = float(player[metric])
                    except (ValueError, TypeError):
                        value = player[metric]

                    metric_values[name] = value

            if metric_values:
                comparison["metrics_comparison"][metric] = metric_values

        # Include gameweek comparison if requested
        if include_gameweeks:
            try:
                gameweek_comparison = {}
                recent_form_comparison = {}
                gameweek_range = []

                # Get gameweek data for all players in one batched call
                all_ids = [player["id"] for player in players_data.values()]
                player_history = await fixtures.get_player_gameweek_history(all_ids, num_gameweeks)

                for name, player in players_data.items():
                    if "players" in player_history and player["id"] in player_history["players"]:
                        history = player_history["players"][player["id"]]
                        gameweek_comparison[name] = history

                        # Store gameweek range
                        if "gameweeks" in player_history and not gameweek_range:
                            gameweek_range = player_history["gameweeks"]

                        # Calculate aggregated recent form stats
                        recent_stats = {
                            "matches": len(history),
                            "minutes": 0,
                            "points": 0,
                            "goals": 0,
                            "assists": 0,
                            "clean_sheets": 0,
                            "bonus": 0,
                            "expected_goals": 0,
                            "expected_assists": 0,
                            "expected_goal_involvements": 0,
                            "points_per_game": 0
                        }

                        # Sum up stats from gameweek history
                        for gw in history:
                            recent_stats["minutes"] += gw.get("minutes", 0)
                            recent_stats["points"] += gw.get("points", 0)
                            recent_stats["goals"] += gw.get("goals", 0)
                            recent_stats["assists"] += gw.get("assists", 0)
                            recent_stats["clean_sheets"] += gw.get("clean_sheets", 0)
                            recent_stats["bonus"] += gw.get("bonus", 0)
                            recent_stats["expected_goals"] += float(gw.get("expected_goals", 0))
                            recent_stats["expected_assists"] += float(gw.get("expected_assists", 0))
                            recent_stats["expected_goal_involvements"] += float(gw.get("expected_goal_involvements", 0))

                        # Calculate averages
                        if recent_stats["matches"] > 0:
                            recent_stats["points_per_game"] = round(recent_stats["points"] / recent_stats["matches"], 1)

                        # Round floating point values
                        recent_stats["expected_goals"] = round(recent_stats["expected_goals"], 2)
                        recent_stats["expected_assists"] = round(recent_stats["expected_assists"], 2)
                        recent_stats["expected_goal_involvements"] = round(recent_stats["expected_goal_involvements"], 2)

                        recent_form_comparison[name] = recent_stats

                # Only add to result if we have data
                if gameweek_comparison:
                    comparison["gameweek_comparison"] = gameweek_comparison
                    comparison["gameweek_range"] = gameweek_range

                    # Add recent form comparison section
                    comparison["recent_form_comparison"] = {
                        "description": f"Aggregated stats for the last {num_gameweeks} gameweeks only",
                        "gameweeks_analyzed": gameweek_range,
                        "player_stats": recent_form_comparison
                    }

                    # Add best performer for recent form metrics
                    comparison["recent_form_best"] = {}

                    # Compare players on key recent form metrics
                    for metric in ["points", "goals", "assists", "expected_goals", "expected_assists"]:
                        values = {name: stats[metric] for name, stats in recent_form_comparison.items()}
                        if values and all(isinstance(v, (int, float)) for v in values.values()):
                            best_player = max(values.items(), key=lambda x: x[1])[0]
                            comparison["recent_form_best"][metric] = best_player

                    # Add label to metrics to indicate they're season-long stats
                    for metric, values in comparison["metrics_comparison"].items():
                        comparison["metrics_comparison"][metric] = {
                            "stats_type": "season_totals",
                            "values": values
                        }
            except Exception as e:
                logger.error(f"Error fetching gameweek comparison: {e}")
                comparison["gameweek_comparison_error"] = str(e)

        # Include fixture analysis if requested
        if include_fixture_analysis:
            fixture_comparison = {}
            fixture_scores = {}
            blank_gameweek_impacts = {}
            double_gameweek_impacts = {}

            # Blank/double gameweeks are the same for every player; fetch once
            blank_gws = await fixtures.get_blank_gameweeks(num_gameweeks)
            double_gws = await fixtures.get_double_gameweeks(num_gameweeks)

            # Get upcoming fixtures for each player
            for name, player in players_data.items():
                try:
                    # Get fixture analysis
                    player_fixture_analysis = await fixtures.analyze_player_fixtures(player["id"], num_gameweeks)

                    # Format fixture data
                    fixtures_data = []
                    if "fixture_analysis" in player_fixture_analysis and "fixtures_analyzed" in player_fixture_analysis["fixture_analysis"]:
                        fixtures_data = player_fixture_analysis["fixture_analysis"]["fixtures_analyzed"]

                    fixture_comparison[name] = fixtures_data

                    # Store fixture difficulty score
                    if "fixture_analysis" in player_fixture_analysis and "difficulty_score" in player_fixture_analysis["fixture_analysis"]:
                        fixture_scores[name] = player_fixture_analysis["fixture_analysis"]["difficulty_score"]

                    # Check for blank gameweeks
                    team_name = player["team"]
                    blank_impact = []

                    for blank_gw in blank_gws:
                        for team_info in blank_gw.get("teams_without_fixtures", []):
                            if team_info.get("name") == team_name:
                                blank_impact.append(blank_gw["gameweek"])

                    blank_gameweek_impacts[name] = blank_impact

                    # Check for double gameweeks
                    double_impact = []

                    for double_gw in double_gws:
                        for team_info in double_gw.get("teams_with_doubles", []):
                            if team_info.get("name") == team_name:
                                double_impact.append({
                                    "gameweek": double_gw["gameweek"],
                                    "fixture_count": team_info.get("fixture_count", 2)
                                })

                    double_gameweek_impacts[name] = double_impact

                except Exception as e:
                    logger.error(f"Error analyzing fixtures for {name}: {e}")

            # Add fixture data to comparison
            if fixture_comparison:
                comparison["fixture_comparison"] = {
                    "upcoming_fixtures": fixture_comparison,
                    "fixture_scores": fixture_scores,
                    "blank_gameweeks": blank_gameweek_impacts,
                    "double_gameweeks": double_gameweek_impacts
                }

                # Add fixture advantage assessment
                if len(fixture_scores) >= 2:
                    best_fixtures_player = max(fixture_scores.items(), key=lambda x: x[1])[0]
                    worst_fixtures_player = min(fixture_scores.items(), key=lambda x: x[1])[0]

                    comparison["fixture_comparison"]["fixture_advantage"] = {
                        "best_fixtures": best_fixtures_player,
                        "worst_fixtures": worst_fixtures_player,
                        "advantage": f"{best_fixtures_player} has easier upcoming fixtures than {worst_fixtures_player}"
                    }

        # Add summary of who's best for each metric
        comparison["best_performers"] = {}

        for metric, values in comparison["metrics_comparison"].items():
            # When gameweek comparison ran, metrics are nested under "values"
            if isinstance(values, dict) and "values" in values and "stats_type" in values:
                values = values["values"]

            # Determine which metrics should be ranked with higher values as better
            higher_is_better = metric not in ["price"]

            # Find the best player for this metric
            if all(isinstance(v, (int, float)) for v in values.values()):
                if higher_is_better:
                    best_name = max(values.items(), key=lambda x: x[1])[0]
                else:
                    best_name = min(values.items(), key=lambda x: x[1])[0]

                comparison["best_performers"][metric] = best_name

        # Overall comparison summary
        player_wins = {name: 0 for name in players_data.keys()}

        for metric, best_name in comparison["best_performers"].items():
            player_wins[best_name] = player_wins.get(best_name, 0) + 1

        # Add fixture advantage to wins if available
        if include_fixture_analysis and "fixture_comparison" in comparison and "fixture_advantage" in comparison["fixture_comparison"]:
            best_fixtures_player = comparison["fixture_comparison"]["fixture_advantage"]["best_fixtures"]
            player_wins[best_fixtures_player] = player_wins.get(best_fixtures_player, 0) + 1

        comparison["summary"] = {
            "metrics_won": player_wins,
            "overall_best": max(player_wins.items(), key=lambda x: x[1])[0] if player_wins else None
        }

        return comparison
