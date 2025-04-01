# src/fpl_mcp/fpl/tools/leagues.py
import logging
import time
import asyncio
from typing import Dict, Any, List, Optional

from ..auth_manager import get_auth_manager
from ..api import api
from ..cache import cache, cached
from ...config import FPL_API_BASE_URL, LEAGUE_RESULTS_LIMIT
from .simplified_decision import get_simplified_league_decision_analysis

logger = logging.getLogger(__name__)

# Cache league standings for 1 hour
@cached("league_standings", ttl=3600)
async def get_league_standings_data(league_id: int) -> Dict[str, Any]:
    """
    Get raw league standings data from the FPL API
    
    Args:
        league_id: ID of the league to fetch

    Returns:
        Raw league data from the API or error message
    """
    auth_manager = get_auth_manager()
    
    # Construct the URL
    url = f"{FPL_API_BASE_URL}/leagues-classic/{league_id}/standings/"
    
    # Get league data
    try:
        data = await auth_manager.make_authed_request(url)
        return data
    except Exception as e:
        logger.error(f"Error fetching league standings: {e}")
        return {
            "error": f"Failed to retrieve league standings: {str(e)}"
        }

def parse_league_standings(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse league standings data into a more usable format
    
    Args:
        data: Raw league data from the API
        
    Returns:
        Parsed league data
    """
    # Handle error responses
    if "error" in data:
        return data
    
    # Parse league info
    league_info = {
        "id": data.get("league", {}).get("id"),
        "name": data.get("league", {}).get("name"),
        "created": data.get("league", {}).get("created"),
        "type": "Public" if data.get("league", {}).get("league_type") == "s" else "Private",
        "scoring": "Classic" if data.get("league", {}).get("scoring") == "c" else "Head-to-Head",
        "admin_entry": data.get("league", {}).get("admin_entry"),
        "start_event": data.get("league", {}).get("start_event"),
    }
    
    # Parse standings
    standings = data.get("standings", {}).get("results", [])
    
    # Get total count
    total_count = len(standings)
    
    # Format standings
    formatted_standings = []
    for standing in standings:
        team = {
            "id": standing.get("id"),
            "team_id": standing.get("entry"),
            "team_name": standing.get("entry_name"),
            "manager_name": standing.get("player_name"),
            "rank": standing.get("rank"),
            "last_rank": standing.get("last_rank"),
            "rank_change": standing.get("last_rank", 0) - standing.get("rank", 0) if standing.get("last_rank") and standing.get("rank") else 0,
            "total_points": standing.get("total"),
            "event_total": standing.get("event_total"),
        }
        formatted_standings.append(team)
    
    response = {
        "league_info": league_info,
        # if more than LEAGUE_RESULTS_LIMIT teams, only show top 25
        "standings": formatted_standings[:LEAGUE_RESULTS_LIMIT],
        "total_teams": total_count,
    }
    
    if len(formatted_standings) > LEAGUE_RESULTS_LIMIT:
        response["disclaimers"] = ["Limited to top 25 teams"]
    
    return response

# Core function for getting historical data for multiple teams
async def get_teams_historical_data(team_ids: List[int], start_gw: Optional[int] = None, end_gw: Optional[int] = None) -> Dict[str, Any]:
    """
    Get historical data for multiple teams
    
    Args:
        team_ids: List of team IDs to fetch
        start_gw: Starting gameweek (defaults to 1)
        end_gw: Ending gameweek (defaults to current)
        
    Returns:
        Dictionary mapping team IDs to their historical data
    """
    auth_manager = get_auth_manager()
    results = {}
    errors = {}
    
    # Validate and process gameweek range
    try:
        # Get current gameweek if needed for end_gw
        if end_gw is None or end_gw == "current":
            current_gw_data = await api.get_current_gameweek()
            current_gw = current_gw_data.get("id", 38)
            end_gw = current_gw
        elif isinstance(end_gw, str) and end_gw.startswith("current-"):
            current_gw_data = await api.get_current_gameweek()
            current_gw = current_gw_data.get("id", 38)
            offset = int(end_gw.split("-")[1])
            end_gw = max(1, current_gw - offset)
        
        # Default start_gw to 1 if not specified
        if start_gw is None:
            start_gw = 1
        elif isinstance(start_gw, str) and start_gw.startswith("current-"):
            current_gw_data = await api.get_current_gameweek()
            current_gw = current_gw_data.get("id", 38)
            offset = int(start_gw.split("-")[1])
            start_gw = max(1, current_gw - offset)
        
        # Ensure we have valid integers
        start_gw = int(start_gw) if start_gw is not None else 1
        end_gw = int(end_gw) if end_gw is not None else 38
        
        # Validate range
        if start_gw < 1:
            start_gw = 1
        if end_gw > 38:
            end_gw = 38
        if start_gw > end_gw:
            start_gw, end_gw = end_gw, start_gw
            
    except Exception as e:
        logger.error(f"Error processing gameweek range: {e}")
        return {
            "error": f"Invalid gameweek range: {str(e)}",
            "suggestion": "Use numeric values or 'current'/'current-N' format"
        }
    
    # Get history data for each team
    for team_id in team_ids:
        try:
            # Try to get from cache first (1 hour TTL)
            cache_key = f"team_history_{team_id}"
            cached_data = cache.cache.get(cache_key)
            
            current_time = time.time()
            if cached_data and cached_data[0] + 3600 > current_time:
                history_data = cached_data[1]
            else:
                # Fetch fresh data if not cached
                url = f"{FPL_API_BASE_URL}/entry/{team_id}/history/"
                history_data = await auth_manager.make_authed_request(url)
                
                # Cache the data
                cache.cache[cache_key] = (current_time, history_data)
            
            # Filter to requested gameweek range
            if "current" in history_data:
                current = [gw for gw in history_data["current"] if start_gw <= gw.get("event", 0) <= end_gw]
                
                # Create a new filtered data object
                filtered_data = {
                    "current": current,
                    "past": history_data.get("past", []),
                    "chips": history_data.get("chips", [])
                }
                
                results[team_id] = filtered_data
            else:
                errors[team_id] = "No historical data found"
                
        except Exception as e:
            logger.error(f"Error fetching team {team_id} history: {e}")
            errors[team_id] = str(e)
    
    return {
        "teams_data": results,
        "errors": errors,
        "gameweek_range": {"start": start_gw, "end": end_gw},
        "success_rate": len(results) / len(team_ids) if team_ids else 0
    }

async def _get_league_standings(league_id: int) -> Dict[str, Any]:
    """
    Get standings for a specified FPL league    
    Args:
        league_id: ID of the league to fetch
    Returns:
        League information with standings and team details
    """
    # Get raw league data
    data = await get_league_standings_data(league_id)
    
    # Check for errors
    if "error" in data:
        return data
    
    # Parse league standings and limit results if needed
    parsed_data = parse_league_standings(data)
    
    # If we have too many teams but aren't checking size, limit the results
    if "standings" in parsed_data and len(parsed_data["standings"]) > LEAGUE_RESULTS_LIMIT:
        parsed_data["standings"] = parsed_data["standings"][:LEAGUE_RESULTS_LIMIT]
        parsed_data["limited"] = True
    
    return parsed_data

async def _get_league_historical_performance(
    league_id: int, 
    start_gw: Optional[int] = None, 
    end_gw: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get historical performance data for teams in a league
    
    Args:
        league_id: ID of the league to analyze
        start_gw: Starting gameweek (defaults to 1)
        end_gw: Ending gameweek (defaults to current)
        
    Returns:
        Historical performance data for visualization
    """
    # Get league standings
    league_data = await _get_league_standings(league_id)
    
    # Check for errors
    if "error" in league_data:
        return league_data
    
    # Limit to top N teams based on config
    if "standings" in league_data and len(league_data["standings"]) > LEAGUE_RESULTS_LIMIT:
        league_data["standings"] = league_data["standings"][:LEAGUE_RESULTS_LIMIT]
        league_data["limited_to_top"] = LEAGUE_RESULTS_LIMIT
    
    # Extract team IDs from the top teams
    team_ids = [team["team_id"] for team in league_data["standings"]]
    
    logger.info(f"Analyzing historical performance for top {len(team_ids)} teams in the league")
    
    # Get historical data for all teams
    historical_data = await get_teams_historical_data(team_ids, start_gw, end_gw)
    
    # Check for complete failure
    if "error" in historical_data:
        return historical_data
    
    # Process into visualization-friendly format
    teams_data = historical_data["teams_data"]
    gameweek_range = historical_data["gameweek_range"]
    
    # Create gameweeks array for x-axis
    gameweeks = list(range(gameweek_range["start"], gameweek_range["end"] + 1))
    
    # Build team series data
    series = []
    for team in league_data["standings"]:
        team_id = team["team_id"]
        
        # Skip if we don't have historical data
        if team_id not in teams_data:
            continue
        
        # Get current season data
        current = teams_data[team_id].get("current", [])
        
        # Extract points and ranks
        points_series = []
        rank_series = []
        value_series = []
        
        for gw in gameweeks:
            # Find the gameweek in the current data
            gw_data = next((g for g in current if g.get("event") == gw), None)
            
            if gw_data:
                points_series.append(gw_data.get("points", 0))
                rank_series.append(gw_data.get("overall_rank", 0))
                value_series.append(gw_data.get("value", 0) / 10.0 if gw_data.get("value") else 0)
            else:
                # Use 0 for missing data
                points_series.append(0)
                rank_series.append(0)
                value_series.append(0)
        
        # Add to series
        series.append({
            "team_id": team_id,
            "name": team["team_name"],
            "manager": team["manager_name"],
            "points_series": points_series,
            "rank_series": rank_series,
            "value_series": value_series,
            "current_rank": team["rank"],
            "total_points": team["total_points"]
        })
    
    # Find gameweek winners
    gameweek_winners = {}
    for gw_index, gw in enumerate(gameweeks):
        max_points = 0
        winner = None
        
        for team in series:
            points = team["points_series"][gw_index]
            if points > max_points:
                max_points = points
                winner = {
                    "team_id": team["team_id"],
                    "name": team["name"],
                    "points": points
                }
        
        if winner:
            gameweek_winners[str(gw)] = winner
    
    # Calculate consistency scores (lower rank variance = higher consistency)
    for team in series:
        rank_variance = 0
        valid_ranks = [r for r in team["rank_series"] if r > 0]
        
        if valid_ranks:
            mean_rank = sum(valid_ranks) / len(valid_ranks)
            rank_variance = sum((r - mean_rank) ** 2 for r in valid_ranks) / len(valid_ranks)
            
            # Invert and scale to make higher values mean more consistent
            consistency_score = 10.0 - min(10.0, (rank_variance / 1000000) * 10)
            team["consistency_score"] = round(consistency_score, 1)
        else:
            team["consistency_score"] = 0
    
    # Return visualization-friendly format
    return {
        "league_info": league_data["league_info"],
        "gameweeks": gameweeks,
        "teams": series,
        "gameweek_winners": gameweek_winners,
        "errors": historical_data["errors"],
        "success_rate": historical_data["success_rate"]
    }

async def _get_league_team_composition(
    league_id: int,
    gameweek: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get team composition analysis for a league, showing player ownership
    and value distribution across teams
    
    Args:
        league_id: ID of the league to analyze
        gameweek: Gameweek to analyze (defaults to current)
        
    Returns:
        Team composition data structured for visualization
    """
    # Get league standings
    league_data = await _get_league_standings(league_id)
    
    # Check for errors
    if "error" in league_data:
        return league_data
    
    # Limit to top N teams based on config
    if "standings" in league_data and len(league_data["standings"]) > LEAGUE_RESULTS_LIMIT:
        league_data["standings"] = league_data["standings"][:LEAGUE_RESULTS_LIMIT]
        league_data["limited_to_top"] = LEAGUE_RESULTS_LIMIT
    
    # Extract team IDs from the top teams
    team_ids = [team["team_id"] for team in league_data["standings"]]
    
    logger.info(f"Analyzing team composition for top {len(team_ids)} teams in the league")
    
    # Get current gameweek if not specified
    if gameweek is None:
        current_gw_data = await api.get_current_gameweek()
        gameweek = current_gw_data.get("id", 1)
    
    # Ensure gameweek is an integer
    try:
        gameweek = int(gameweek)
    except (ValueError, TypeError):
        return {"error": f"Invalid gameweek value: {gameweek}"}
    
    # Get static data with all the information we need
    static_data = await api.get_bootstrap_static()
    all_players = static_data.get("elements", [])
    
    # Create mapping tables for teams and positions
    teams_map = {t["id"]: t for t in static_data.get("teams", [])}
    positions_map = {p["id"]: p for p in static_data.get("element_types", [])}
    
    # Create enriched player map with proper team and position info
    players_map = {}
    for p in all_players:
        player = dict(p)
        
        # Add team info
        team_id = player.get("team")
        if team_id and team_id in teams_map:
            player["team_short"] = teams_map[team_id].get("short_name")
        
        # Add position info
        position_id = player.get("element_type")
        if position_id and position_id in positions_map:
            player["position"] = positions_map[position_id].get("singular_name_short")
            
        players_map[player["id"]] = player
    
    # Get all teams' compositions
    teams_data = {}
    errors = {}
    
    auth_manager = get_auth_manager()
    for team_id in team_ids:
        try:
            # Try to get from cache first
            cache_key = f"team_picks_{team_id}_{gameweek}"
            cached_data = cache.cache.get(cache_key)
            
            current_time = time.time()
            if cached_data and cached_data[0] + 3600 > current_time:
                picks_data = cached_data[1]
            else:
                # Fetch team data for the gameweek
                try:
                    picks_data = await auth_manager.get_team_for_gameweek(team_id, gameweek)
                    
                    # Cache the data (1 hour TTL)
                    cache.cache[cache_key] = (current_time, picks_data)
                except Exception as e:
                    logger.error(f"Error fetching team {team_id} for gameweek {gameweek}: {e}")
                    errors[team_id] = str(e)
                    continue
            
            teams_data[team_id] = picks_data
        except Exception as e:
            logger.error(f"Error processing team {team_id}: {e}")
            errors[team_id] = str(e)
    
    # Process team compositions
    if not teams_data:
        return {
            "error": "Failed to retrieve team data for any teams in the league",
            "errors": errors
        }
    
    # Count player ownership
    player_ownership = {}
    captain_picks = {}
    vice_captain_picks = {}
    position_distribution = {"GKP": {}, "DEF": {}, "MID": {}, "FWD": {}}
    team_values = {}
    
    # Process each team's data
    for team_id, team_data in teams_data.items():
        # Get team info from league standings
        team_info = next((t for t in league_data["standings"] if t["team_id"] == team_id), None)
        if not team_info:
            continue
            
        # Get picks
        picks = team_data.get("picks", [])
        entry_history = team_data.get("entry_history", {})
        
        # Add team value info
        team_values[team_id] = {
            "team_name": team_info["team_name"],
            "manager_name": team_info["manager_name"],
            "bank": entry_history.get("bank", 0) / 10.0 if entry_history else 0,
            "value": entry_history.get("value", 0) / 10.0 if entry_history else 0
        }
        
        # Process each pick
        for pick in picks:
            player_id = pick.get("element")
            if not player_id:
                continue
                
            player_data = players_map.get(player_id, {})
            if not player_data:
                continue
                
            # Initialize player in ownership map if not exists
            if player_id not in player_ownership:
                position = player_data.get("position", "UNK")
                full_name = f"{player_data.get('first_name', '')} {player_data.get('second_name', '')}"
                player_ownership[player_id] = {
                    "id": player_id,
                    "name": player_data.get("web_name", "Unknown"),
                    "full_name": full_name.strip() or "Unknown",
                    "position": position,
                    "team": player_data.get("team_short", "UNK"),
                    "price": player_data.get("now_cost", 0) / 10.0 if player_data.get("now_cost") else 0,
                    "form": float(player_data.get("form", "0.0")) if player_data.get("form") else 0,
                    "total_points": player_data.get("total_points", 0),
                    "points_per_game": float(player_data.get("points_per_game", "0.0")) if player_data.get("points_per_game") else 0,
                    "ownership_count": 0,
                    "ownership_percent": 0,
                    "captain_count": 0,
                    "vice_captain_count": 0,
                    "teams": []
                }
                
            # Update ownership count
            player_ownership[player_id]["ownership_count"] += 1
            player_ownership[player_id]["teams"].append({
                "team_id": team_id,
                "team_name": team_info["team_name"],
                "manager_name": team_info["manager_name"],
                "is_captain": pick.get("is_captain", False),
                "is_vice_captain": pick.get("is_vice_captain", False),
                "multiplier": pick.get("multiplier", 0),
                "position": pick.get("position", 0)
            })
            
            # Update captain picks
            if pick.get("is_captain", False):
                if player_id not in captain_picks:
                    captain_picks[player_id] = 0
                captain_picks[player_id] += 1
                player_ownership[player_id]["captain_count"] += 1
            
            # Update vice captain picks
            if pick.get("is_vice_captain", False):
                if player_id not in vice_captain_picks:
                    vice_captain_picks[player_id] = 0
                vice_captain_picks[player_id] += 1
                player_ownership[player_id]["vice_captain_count"] += 1
            
            # Update position distribution
            position = player_data.get("position", "UNK")
            if position in position_distribution:
                if player_id not in position_distribution[position]:
                    position_distribution[position][player_id] = 0
                position_distribution[position][player_id] += 1
    
    # Calculate ownership percentages
    team_count = len(teams_data)
    for player_id, player in player_ownership.items():
        player["ownership_percent"] = round((player["ownership_count"] / team_count) * 100, 1)
    
    # Sort players by ownership percentage (descending)
    players_by_ownership = sorted(
        player_ownership.values(), 
        key=lambda p: (p["ownership_percent"], p["total_points"]), 
        reverse=True
    )
    
    # Generate template vs. differential lists
    template_threshold = 30.0  # Players owned by > 30% teams
    differential_threshold = 10.0  # Players owned by < 10% teams
    
    template_players = [p for p in players_by_ownership if p["ownership_percent"] > template_threshold]
    differential_players = [p for p in players_by_ownership if 0 < p["ownership_percent"] < differential_threshold]
    
    # Sort by position for better organization
    position_order = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4, "UNK": 5}
    template_players.sort(key=lambda p: (position_order.get(p["position"], 5), -p["ownership_percent"]))
    differential_players.sort(key=lambda p: (position_order.get(p["position"], 5), -p["total_points"]))
    
    # Get most common captains
    captain_data = []
    for player_id, count in sorted(captain_picks.items(), key=lambda x: x[1], reverse=True):
        if player_id in player_ownership:
            player = player_ownership[player_id]
            captain_data.append({
                "id": player_id,
                "name": player["name"],
                "count": count,
                "percent": round((count / team_count) * 100, 1),
                "position": player["position"],
                "team": player["team"],
                "points": player["total_points"]
            })
    
    # Calculate value distribution stats
    value_stats = {}
    for team_id, value_data in team_values.items():
        value_stats[team_id] = {
            "team_name": value_data["team_name"],
            "manager_name": value_data["manager_name"],
            "bank": value_data["bank"],
            "team_value": value_data["value"]
        }
    
    # Sort value stats by team value
    sorted_value_stats = sorted(
        value_stats.values(),
        key=lambda v: v["team_value"],
        reverse=True
    )
    
    # Return visualization-friendly format with consistent player limits
    # Use the configured limit to determine the player limits
    PLAYER_LIMIT = LEAGUE_RESULTS_LIMIT  # Use the same limit for players as for teams
    
    return {
        "league_info": league_data["league_info"],
        "gameweek": gameweek,
        "teams_analyzed": team_count,
        "player_ownership": {
            "all_players": players_by_ownership[:PLAYER_LIMIT],  # Use configurable limit
            "template_players": template_players[:PLAYER_LIMIT],
            "differential_players": differential_players[:PLAYER_LIMIT],
            "captain_picks": captain_data[:PLAYER_LIMIT] if len(captain_data) > PLAYER_LIMIT else captain_data
        },
        "team_values": sorted_value_stats,
        "errors": errors,
        "success_rate": len(teams_data) / len(team_ids) if team_ids else 0
    }

def get_captain_success_category(points: int) -> str:
    """
    Categorize captain success based on points
    
    Args:
        points: Captain points (already multiplied)
        
    Returns:
        Success category string
    """
    if points >= 15:
        return "strong"
    elif points >= 10:
        return "moderate"
    elif points >= 5:
        return "average"
    elif points > 0:
        return "weak"
    else:
        return "none"

async def _get_league_fixture_analysis(
    league_id: int,
    start_gw: Optional[int] = None,
    end_gw: Optional[int] = None
) -> Dict[str, Any]:
    """
    Analyze upcoming fixtures for teams in a league
    
    Args:
        league_id: ID of the league to analyze
        start_gw: Starting gameweek (defaults to current gameweek)
        end_gw: Ending gameweek (for future analysis)
        
    Returns:
        Fixture analysis data for visualization
    """
    logger.info(f"Analyzing fixtures for league {league_id}, gameweeks {start_gw} to {end_gw}")
    
    # Get league standings
    league_data = await _get_league_standings(league_id)
    
    # Check for errors
    if "error" in league_data:
        return league_data
        
    # Limit to top N teams based on config
    if "standings" in league_data and len(league_data["standings"]) > LEAGUE_RESULTS_LIMIT:
        league_data["standings"] = league_data["standings"][:LEAGUE_RESULTS_LIMIT]
        league_data["limited_to_top"] = LEAGUE_RESULTS_LIMIT
    
    # Get current gameweek if not specified
    if start_gw is None:
        current_gw_data = await api.get_current_gameweek()
        start_gw = current_gw_data.get("id", 1)
    
    # Default end_gw to 5 gameweeks after start_gw if not specified
    if end_gw is None:
        end_gw = start_gw + 4  # Look at 5 gameweeks (inclusive)
    
    # Ensure they're integers
    start_gw = int(start_gw)
    end_gw = int(end_gw)
    
    # Extract team IDs from league standings
    team_ids = []
    for team in league_data["standings"]:
        team_ids.append(team["team_id"])
    
    # Get all fixtures for the specified gameweek range
    all_fixtures = await api.get_fixtures()
    gameweek_fixtures = [
        f for f in all_fixtures 
        if f.get("event") and start_gw <= f.get("event") <= end_gw
    ]
    
    # Get team data for mapping IDs and getting strength ratings
    teams_data = await api.get_teams()
    team_map = {t["id"]: t for t in teams_data}
    fpl_team_map = {t.get("pulse_id", t["id"]): t for t in teams_data}
    
    # Get all FPL teams to map to manager teams
    fpl_team_ids = set(t["id"] for t in teams_data)
    
    # Get all players to find team squads
    all_players = await api.get_players()
    
    # Get the list of gameweeks in this range
    gameweeks = list(range(start_gw, end_gw + 1))
    
    # For each manager team, identify their players' teams and analyze fixtures
    team_fixture_analysis = []
    
    auth_manager = get_auth_manager()
    
    # Cache for API calls to avoid repetition
    team_picks_cache = {}
    
    # Process only the top N teams based on the configured limit
    # This uses the rank from the standings to get only the top teams by rank
    top_teams = league_data["standings"][:LEAGUE_RESULTS_LIMIT]
    logger.info(f"Analyzing fixtures for top {len(top_teams)} teams in the league")
    
    # Process each fantasy team
    for rank, fantasy_team in enumerate(top_teams):
        team_id = fantasy_team["team_id"]
        
        try:
            # Get team picks for the first gameweek to analyze team composition
            cache_key = f"team_picks_{team_id}_{start_gw}"
            picks_data = None
            
            if cache_key in team_picks_cache:
                picks_data = team_picks_cache[cache_key]
            else:
                # Fetch team data for the gameweek 
                try:
                    picks_data = await auth_manager.get_team_for_gameweek(team_id, start_gw)
                    team_picks_cache[cache_key] = picks_data
                except Exception as e:
                    logger.error(f"Error fetching team {team_id} for gameweek {start_gw}: {e}")
                    continue
            
            if not picks_data or "picks" not in picks_data:
                logger.warning(f"No picks data found for team {team_id}")
                continue
            
            # Extract the players in this fantasy team
            player_ids = [pick.get("element") for pick in picks_data.get("picks", [])]
            
            # Map these player IDs to their FPL teams
            player_teams = {}
            for player_id in player_ids:
                for player in all_players:
                    if player.get("id") == player_id:
                        player_teams[player_id] = player.get("team")
                        break
            
            # Count how many players from each FPL team
            fpl_team_counts = {}
            for team_id in fpl_team_ids:
                count = len([p for p, t in player_teams.items() if t == team_id])
                if count > 0:
                    fpl_team_counts[team_id] = count
            
            # Get fixture difficulty for each FPL team in the squad
            team_fixtures = {}
            
            for fpl_team_id in fpl_team_counts.keys():
                team_fixtures[fpl_team_id] = []
                
                # Find fixtures for this team in the specified gameweeks
                for fixture in gameweek_fixtures:
                    gw = fixture.get("event")
                    
                    # Check if this team is playing in this fixture
                    is_home = fixture.get("team_h") == fpl_team_id
                    is_away = fixture.get("team_a") == fpl_team_id
                    
                    if is_home or is_away:
                        # Get opponent information
                        opponent_id = fixture.get("team_a") if is_home else fixture.get("team_h")
                        opponent_team = team_map.get(opponent_id, {})
                        
                        # Get difficulty rating
                        difficulty = fixture.get("team_h_difficulty" if is_home else "team_a_difficulty", 3)
                        
                        team_fixtures[fpl_team_id].append({
                            "gameweek": gw,
                            "opponent": opponent_team.get("name", f"Team {opponent_id}"),
                            "opponent_short": opponent_team.get("short_name", ""),
                            "location": "home" if is_home else "away",
                            "difficulty": difficulty
                        })
            
            # Calculate an overall fixture difficulty score for this fantasy team
            # Based on:
            # 1. How many players they have from each team
            # 2. The fixture difficulty for those teams
            
            gameweek_difficulty = {}
            
            for gw in gameweeks:
                gameweek_difficulty[gw] = {
                    "total_players": 0,
                    "total_difficulty": 0,
                    "teams_with_fixtures": 0
                }
                
                for fpl_team_id, player_count in fpl_team_counts.items():
                    # Find this team's fixture for this gameweek
                    fixtures = [f for f in team_fixtures.get(fpl_team_id, []) if f["gameweek"] == gw]
                    
                    if fixtures:
                        # Team has a fixture this gameweek
                        gameweek_difficulty[gw]["teams_with_fixtures"] += 1
                        gameweek_difficulty[gw]["total_players"] += player_count
                        
                        # Sum difficulty (weighted by player count)
                        if len(fixtures) == 1:
                            # Single fixture
                            difficulty = fixtures[0]["difficulty"]
                            gameweek_difficulty[gw]["total_difficulty"] += difficulty * player_count
                        else:
                            # Double gameweek! Average the difficulties
                            avg_difficulty = sum(f["difficulty"] for f in fixtures) / len(fixtures)
                            # Double gameweeks are valuable - reduce difficulty
                            adjusted_difficulty = avg_difficulty * 0.7
                            gameweek_difficulty[gw]["total_difficulty"] += adjusted_difficulty * player_count
                    else:
                        # Team doesn't play this gameweek - maximum difficulty
                        blank_difficulty = 6  # Higher than normal max (5)
                        gameweek_difficulty[gw]["total_difficulty"] += blank_difficulty * player_count
            
            # Overall fixture difficulty for this fantasy team
            # Average across gameweeks, weighted by players affected
            total_difficulty = 0
            total_players = 0
            
            for gw, data in gameweek_difficulty.items():
                if data["total_players"] > 0:
                    difficulty_score = data["total_difficulty"] / data["total_players"]
                    total_difficulty += difficulty_score
                    total_players += 1
            
            avg_difficulty = total_difficulty / total_players if total_players > 0 else 3
            
            # Scale difficulty from 0-10 (10 is best fixtures)
            # Normal FPL difficulty is 1-5 where 5 is hardest
            
            fixture_score = (6 - avg_difficulty) * 2
            fixture_score = max(1, min(10, fixture_score))
            
            # Simplify the fixtures for the top 3 teams with most players
            # This gives a summary of key fixtures
            top_teams = sorted(
                [(fpl_id, count) for fpl_id, count in fpl_team_counts.items()], 
                key=lambda x: x[1], 
                reverse=True
            )[:3]
            
            key_fixtures = []
            for fpl_id, count in top_teams:
                team_name = team_map.get(fpl_id, {}).get("name", f"Team {fpl_id}")
                team_short = team_map.get(fpl_id, {}).get("short_name", "")
                
                key_fixtures.append({
                    "team": team_name,
                    "team_short": team_short,
                    "player_count": count,
                    "fixtures": team_fixtures.get(fpl_id, [])
                })
            
            # Generate a text analysis of fixture difficulty
            if fixture_score >= 8:
                analysis = "Excellent upcoming fixtures"
            elif fixture_score >= 6.5:
                analysis = "Good upcoming fixtures"
            elif fixture_score >= 5:
                analysis = "Average upcoming fixtures"
            elif fixture_score >= 3.5:
                analysis = "Difficult upcoming fixtures"
            else:
                analysis = "Very difficult upcoming fixtures"
            
            # Create the team fixture analysis
            team_fixture_analysis.append({
                "team_id": team_id,
                "rank": rank + 1,
                "team_name": fantasy_team["team_name"],
                "manager_name": fantasy_team["manager_name"],
                "fixture_score": round(fixture_score, 1),
                "analysis": analysis,
                "key_team_fixtures": key_fixtures,
                "gameweek_difficulty": gameweek_difficulty,
                "blank_gameweek_impact": [] if "blank_gameweeks" not in locals() else [
                    {
                        "gameweek": bw["gameweek"],
                        "teams_affected": [
                            {"name": t["name"], "players": fpl_team_counts.get(t["id"], 0)}
                            for t in bw["teams_without_fixtures"]
                            if t["id"] in fpl_team_counts
                        ]
                    } for bw in blank_gameweeks if any(t["id"] in fpl_team_counts for t in bw["teams_without_fixtures"])
                ]
            })
            
        except Exception as e:
            logger.error(f"Error analyzing fixtures for team {team_id}: {e}")
            continue
    
    # Sort teams by fixture score (best fixtures first)
    team_fixture_analysis.sort(key=lambda x: x["fixture_score"], reverse=True)
    
    # Get double and blank gameweeks in the specified range
    try:
        from ..resources.fixtures import get_blank_gameweeks, get_double_gameweeks
        
        blank_gameweeks = await get_blank_gameweeks(end_gw - start_gw + 1)
        double_gameweeks = await get_double_gameweeks(end_gw - start_gw + 1)
    except Exception as e:
        logger.error(f"Error getting blank/double gameweeks: {e}")
        blank_gameweeks = []
        double_gameweeks = []
    
    # Final result with league and fixture data
    return {
        "league_info": league_data["league_info"],
        "gameweek_range": {
            "start": start_gw,
            "end": end_gw,
            "gameweeks": gameweeks
        },
        "team_fixture_analysis": team_fixture_analysis,
        "special_gameweeks": {
            "blank_gameweeks": blank_gameweeks,
            "double_gameweeks": double_gameweeks
        }
    }

async def _get_league_analytics(
    league_id: int,
    analysis_type: str = "overview",
    start_gw: Optional[int] = None,
    end_gw: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get rich analytics for a Fantasy Premier League mini-league
    
    Returns visualization-optimized data for various types of league analysis.
    
    Args:
        league_id: ID of the league to analyze
        analysis_type: Type of analysis to perform:
            - "overview": General league overview (default)
            - "historical": Historical performance analysis
            - "team_composition": Team composition analysis
            - "decisions": Captain and transfer decision analysis
            - "fixtures": Fixture difficulty comparison
        start_gw: Starting gameweek (defaults to 1)
        end_gw: Ending gameweek (defaults to current)
        
    Returns:
        Rich analytics data structured for visualization
    """
    # Add logging for debugging
    logger.info(f"Starting league analytics: {analysis_type} for league {league_id}")
    
    # Validate analysis type
    valid_types = ["overview", "historical", "team_composition", "decisions", "fixtures"]
    if analysis_type not in valid_types:
        return {
            "error": f"Invalid analysis type: {analysis_type}",
            "valid_types": valid_types
        }
    
    # Get current gameweek
    try:
        current_gw_data = await api.get_current_gameweek()
        current_gw = current_gw_data.get("id", 1)
        logger.info(f"Current gameweek: {current_gw}")
    except Exception as e:
        logger.error(f"Error getting current gameweek: {e}")
        current_gw = 1
    
    # Use the configured limit for all analysis types
    logger.info(f"Using configured limit of {LEAGUE_RESULTS_LIMIT} teams for {analysis_type} analysis")
    
    # Process gameweek range to ensure it's not too large
    effective_start_gw = start_gw
    effective_end_gw = end_gw
    
    # Handle start gameweek - using a consistent default (last 5 gameweeks) for all analysis types
    DEFAULT_GW_LOOKBACK = 5
    
    if effective_start_gw is None:
        effective_start_gw = max(1, current_gw - DEFAULT_GW_LOOKBACK + 1)
        logger.info(f"Using default start gameweek: {effective_start_gw}")
    elif isinstance(effective_start_gw, str) and effective_start_gw.startswith("current-"):
        try:
            offset = int(effective_start_gw.split("-")[1])
            effective_start_gw = max(1, current_gw - offset)
            logger.info(f"Parsed relative start gameweek: {effective_start_gw}")
        except ValueError:
            effective_start_gw = max(1, current_gw - DEFAULT_GW_LOOKBACK + 1)
            logger.info(f"Invalid relative start gameweek, using default: {effective_start_gw}")
    
    # Handle end gameweek
    if effective_end_gw is None or effective_end_gw == "current":
        effective_end_gw = current_gw
        logger.info(f"Using current end gameweek: {effective_end_gw}")
    elif isinstance(effective_end_gw, str) and effective_end_gw.startswith("current-"):
        try:
            offset = int(effective_end_gw.split("-")[1])
            effective_end_gw = max(1, current_gw - offset)
            logger.info(f"Parsed relative end gameweek: {effective_end_gw}")
        except ValueError:
            effective_end_gw = current_gw
            logger.info(f"Invalid relative end gameweek, using current: {effective_end_gw}")
    
    # Convert to integers if necessary
    try:
        effective_start_gw = int(effective_start_gw)
        effective_end_gw = int(effective_end_gw)
    except (ValueError, TypeError):
        logger.error(f"Invalid gameweek values: start={effective_start_gw}, end={effective_end_gw}")
        return {"error": "Invalid gameweek values"}
    
    # Ensure the range is valid and not too large
    if effective_start_gw < 1:
        effective_start_gw = 1
    if effective_end_gw > current_gw:
        effective_end_gw = current_gw
    if effective_start_gw > effective_end_gw:
        effective_start_gw, effective_end_gw = effective_end_gw, effective_start_gw
    
    # Apply consistent gameweek range limit to prevent performance issues
    gw_range = effective_end_gw - effective_start_gw + 1
    # MAX_GW_RANGE = 5  # Use a consistent max range for all analysis types
    
    # if gw_range > MAX_GW_RANGE:
    #     logger.info(f"Reducing gameweek range from {gw_range} to {MAX_GW_RANGE}")
    #     effective_start_gw = max(1, effective_end_gw - MAX_GW_RANGE + 1)
    
    # logger.info(f"Final gameweek range: {effective_start_gw} to {effective_end_gw}")
    
    # Get league standings first
    logger.info(f"Fetching league standings for league {league_id}")
    try:
        # Don't check size limit, just fetch all and filter
        league_data = await _get_league_standings(league_id)
        
        # Check for errors
        if "error" in league_data:
            logger.error(f"Error getting league standings: {league_data['error']}")
            return league_data
        
        logger.info(f"Successfully fetched standings for {len(league_data['standings'])} teams")
    except Exception as e:
        logger.error(f"Exception getting league standings: {e}")
        return {"error": f"Failed to get league standings: {str(e)}"}
    
    # Route to the appropriate analysis function (with timeout protection)
    try:
        if analysis_type == "overview" or analysis_type == "historical":
            # For overview analysis, use the regular function but with reduced range
            return await _get_league_historical_performance(
                league_id, effective_start_gw, effective_end_gw
            )
            
        elif analysis_type == "team_composition":
            # For team composition, use specified gameweek
            # Previously this only used end_gw, but we'll now pass both for consistency
            return await _get_league_team_composition(
                league_id, effective_end_gw
            )
            
        elif analysis_type == "decisions":
            # For decisions, use our new simplified analysis function
            return await get_simplified_league_decision_analysis(
                league_id, effective_start_gw, effective_end_gw,
                _get_league_standings, get_teams_historical_data,
                league_data=league_data  # Pass league data to avoid fetching again
            )
            
        elif analysis_type == "fixtures":
            # Call the league fixture analysis function
            return await _get_league_fixture_analysis(
                league_id, effective_start_gw, effective_end_gw
            )
    except Exception as e:
        logger.error(f"Error in league analytics: {e}")
        return {
            "error": f"Analysis failed: {str(e)}",
            "league_info": league_data["league_info"],
            "standings": league_data["standings"],
            "status": "error"
        }
    
    # This shouldn't happen due to earlier validation
    return {"error": "Unknown analysis type"}

def register_tools(mcp):
    """Register league analytics tools with the MCP server"""
    
    @mcp.tool()
    async def get_league_standings(league_id: int) -> Dict[str, Any]:
        """Get standings for a specified FPL league
        
        Args:
            league_id: ID of the league to fetch
            
        Returns:
            League information with standings and team details
        """
        # When directly using the tool, enforce size check
        return await _get_league_standings(league_id)
    
    @mcp.tool()
    async def get_league_analytics(
        league_id: int,
        analysis_type: str = "overview",
        start_gw: Optional[int] = None,
        end_gw: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get rich analytics for a Fantasy Premier League mini-league
        
        Returns visualization-optimized data for various types of league analysis.
        
        Args:
            league_id: ID of the league to analyze
            analysis_type: Type of analysis to perform:
                - "overview": General league overview (default)
                - "historical": Historical performance analysis
                - "team_composition": Team composition analysis
                - "decisions": Captain and transfer decision analysis
                - "fixtures": Fixture difficulty comparison
            start_gw: Starting gameweek (defaults to 1 or use "current-N" format)
            end_gw: Ending gameweek (defaults to current)
            
        Returns:
            Rich analytics data structured for visualization
        """
        return await _get_league_analytics(league_id, analysis_type, start_gw, end_gw)