#!/usr/bin/env python3

import datetime
import json
import logging
import asyncio
import os
import sys
import atexit
from typing import List, Dict, Any, Optional
from collections import Counter

# Import MCP
from mcp.server.fastmcp import FastMCP, Context
import mcp.types as types

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fpl-mcp-server")

# Create MCP server
mcp = FastMCP(
    "Fantasy Premier League",
    description="Access Fantasy Premier League data and tools",
    dependencies=["httpx", "diskcache", "jsonschema"],
)

# Import modules that use the mcp variable
from .fpl.api import api  
from .fpl.resources import players, teams, gameweeks, fixtures
from .fpl.tools import comparisons, register_team_tools, register_manager_tools, register_league_tools, register_player_tools
from .fpl.utils.position_utils import normalize_position
from .fpl.cache import get_cached_player_data

# Register resources
@mcp.resource("fpl://static/players")
async def get_all_players() -> List[Dict[str, Any]]:
    """Get a formatted list of all players with comprehensive statistics"""
    logger.info("Resource requested: fpl://static/players")
    players_data = await players.get_players_resource()
    return players_data

@mcp.resource("fpl://static/players/{name}")
async def get_player_by_name(name: str) -> Dict[str, Any]:
    """Get player information by searching for their name"""
    logger.info(f"Resource requested: fpl://static/players/{name}")
    player_matches = await players.find_players_by_name(name)
    if not player_matches:
        return {"error": f"No player found matching '{name}'"}
    return player_matches[0]

@mcp.resource("fpl://static/teams")
async def get_all_teams() -> List[Dict[str, Any]]:
    """Get a formatted list of all Premier League teams with strength ratings"""
    logger.info("Resource requested: fpl://static/teams")
    teams_data = await teams.get_teams_resource()
    return teams_data

@mcp.resource("fpl://static/teams/{name}")
async def get_team_by_name(name: str) -> Dict[str, Any]:
    """Get team information by searching for their name"""
    logger.info(f"Resource requested: fpl://static/teams/{name}")
    team = await teams.get_team_by_name(name)
    if not team:
        return {"error": f"No team found matching '{name}'"}
    return team

@mcp.resource("fpl://gameweeks/current")
async def get_current_gameweek() -> Dict[str, Any]:
    """Get information about the current gameweek"""
    logger.info("Resource requested: fpl://gameweeks/current")
    gameweek_data = await gameweeks.get_current_gameweek_resource()
    return gameweek_data

@mcp.resource("fpl://gameweeks/all")
async def get_all_gameweeks() -> List[Dict[str, Any]]:
    """Get information about all gameweeks"""
    logger.info("Resource requested: fpl://gameweeks/all")
    gameweeks_data = await gameweeks.get_gameweeks_resource()
    return gameweeks_data

@mcp.resource("fpl://fixtures")
async def get_all_fixtures() -> List[Dict[str, Any]]:
    """Get all fixtures for the current Premier League season"""
    logger.info("Resource requested: fpl://fixtures")
    fixtures_data = await fixtures.get_fixtures_resource()
    return fixtures_data

@mcp.resource("fpl://fixtures/gameweek/{gameweek_id}")
async def get_gameweek_fixtures(gameweek_id: int) -> List[Dict[str, Any]]:
    """Get fixtures for a specific gameweek"""
    logger.info(f"Resource requested: fpl://fixtures/gameweek/{gameweek_id}")
    fixtures_data = await fixtures.get_fixtures_resource(gameweek_id=gameweek_id)
    return fixtures_data

@mcp.resource("fpl://fixtures/team/{team_name}")
async def get_team_fixtures(team_name: str) -> List[Dict[str, Any]]:
    """Get fixtures for a specific team"""
    logger.info(f"Resource requested: fpl://fixtures/team/{team_name}")
    fixtures_data = await fixtures.get_fixtures_resource(team_name=team_name)
    return fixtures_data

@mcp.resource("fpl://players/{player_name}/fixtures")
async def get_player_fixtures_by_name(player_name: str) -> Dict[str, Any]:
    """Get upcoming fixtures for a specific player"""
    logger.info(f"Resource requested: fpl://players/{player_name}/fixtures")
    
    # Find the player
    player_matches = await players.find_players_by_name(player_name)
    if not player_matches:
        return {"error": f"No player found matching '{player_name}'"}
    
    player = player_matches[0]
    player_fixtures = await fixtures.get_player_fixtures(player["id"])
    
    return {
        "player": {
            "name": player["name"],
            "team": player["team"],
            "position": player["position"]
        },
        "fixtures": player_fixtures
    }

@mcp.resource("fpl://gameweeks/blank")
async def get_blank_gameweeks_resource() -> List[Dict[str, Any]]:
    """Get information about upcoming blank gameweeks"""
    logger.info("Resource requested: fpl://gameweeks/blank")
    blank_gameweeks = await fixtures.get_blank_gameweeks()
    return blank_gameweeks

@mcp.resource("fpl://gameweeks/double")
async def get_double_gameweeks_resource() -> List[Dict[str, Any]]:
    """Get information about upcoming double gameweeks"""
    logger.info("Resource requested: fpl://gameweeks/double")
    double_gameweeks = await fixtures.get_double_gameweeks()
    return double_gameweeks

# Register team, manager, league, and player tools
register_team_tools(mcp)
register_manager_tools(mcp)
register_league_tools(mcp)
register_player_tools(mcp)

# Add authentication check tool
@mcp.tool()
async def check_fpl_authentication() -> Dict[str, Any]:
    """Check if FPL authentication is working correctly
    
    Returns:
        Authentication status and basic team information
    """
    try:
        from .fpl.auth_manager import get_auth_manager
        
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

# Register tools
@mcp.tool()
async def get_gameweek_status() -> Dict[str, Any]:
    """Get precise information about current, previous, and next gameweeks
    
    Returns:
        Detailed information about gameweek timing, including exact status
    """
    gameweeks = await api.get_gameweeks()
    
    # Find current, previous, and next gameweeks
    current_gw = next((gw for gw in gameweeks if gw.get("is_current")), None)
    previous_gw = next((gw for gw in gameweeks if gw.get("is_previous")), None)
    next_gw = next((gw for gw in gameweeks if gw.get("is_next")), None)
    
    # Determine exact current gameweek status
    current_status = "Not Started"
    if current_gw:
        deadline = datetime.datetime.strptime(current_gw["deadline_time"], "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.datetime.utcnow()
        
        if now < deadline:
            current_status = "Upcoming"
            time_until = deadline - now
            hours_until = time_until.total_seconds() / 3600
            
            if hours_until < 24:
                current_status = "Imminent (< 24h)"
        else:
            if current_gw.get("finished"):
                current_status = "Complete"
            else:
                current_status = "In Progress"
    
    return {
        "current_gameweek": current_gw and current_gw["id"],
        "current_status": current_status,
        "previous_gameweek": previous_gw and previous_gw["id"],
        "next_gameweek": next_gw and next_gw["id"],
        "season_progress": f"GW {current_gw and current_gw['id']}/38" if current_gw else "Unknown",
        "exact_timing": {
            "current_deadline": current_gw and current_gw["deadline_time"],
            "next_deadline": next_gw and next_gw["deadline_time"]
        }
    }

# Register tools for fixture analysis
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
    
    # Handle case when a dictionary is passed instead of string (error case)
    if isinstance(player_name, dict):
        if 'player_name' in player_name:
            player_name = player_name['player_name']
        elif 'query' in player_name:
            player_name = player_name['query']
        else:
            # If we can't find a usable key, convert the dict to a string
            player_name = str(player_name)
    
    # Handle case when num_fixtures is a dict
    if isinstance(num_fixtures, dict):
        if 'num_fixtures' in num_fixtures:
            num_fixtures = num_fixtures['num_fixtures']
        else:
            # Default to 5 if we can't find a usable value
            num_fixtures = 5
    
    # Find the player
    player_matches = await players.find_players_by_name(player_name)
    if not player_matches:
        return {"error": f"No player found matching '{player_name}'"}

    
    player = player_matches[0]
    analysis = await fixtures.analyze_player_fixtures(player["id"], num_fixtures)
    
    return analysis

@mcp.tool()
async def get_blank_gameweeks(num_gameweeks: int = 5) -> Dict[str, Any]:
    """Get information about upcoming blank gameweeks where teams don't have fixtures
    
    Args:
        num_gameweeks: Number of upcoming gameweeks to check (default: 5)
    
    Returns:
        Information about blank gameweeks and affected teams
    """
    logger.info(f"Tool called: get_blank_gameweeks({num_gameweeks})")
    
    # Handle case when num_gameweeks is a dictionary
    if isinstance(num_gameweeks, dict):
        if 'num_gameweeks' in num_gameweeks:
            num_gameweeks = num_gameweeks['num_gameweeks']
        else:
            # Default to 5 if we can't find a usable value
            num_gameweeks = 5
            
    blank_gameweeks = await fixtures.get_blank_gameweeks(num_gameweeks)
    
    if not blank_gameweeks:
        return {
            "blank_gameweeks": [],
            "summary": f"No blank gameweeks found in the next {num_gameweeks} gameweeks"
        }
    
    return {
        "blank_gameweeks": blank_gameweeks,
        "summary": f"Found {len(blank_gameweeks)} blank gameweeks in the next {num_gameweeks} gameweeks"
    }

@mcp.tool()
async def get_double_gameweeks(num_gameweeks: int = 5) -> Dict[str, Any]:
    """Get information about upcoming double gameweeks where teams play multiple times
    
    Args:
        num_gameweeks: Number of upcoming gameweeks to check (default: 5)
    
    Returns:
        Information about double gameweeks and affected teams
    """
    logger.info(f"Tool called: get_double_gameweeks({num_gameweeks})")
    
    # Handle case when num_gameweeks is a dictionary
    if isinstance(num_gameweeks, dict):
        if 'num_gameweeks' in num_gameweeks:
            num_gameweeks = num_gameweeks['num_gameweeks']
        else:
            # Default to 5 if we can't find a usable value
            num_gameweeks = 5
            
    double_gameweeks = await fixtures.get_double_gameweeks(num_gameweeks)
    
    if not double_gameweeks:
        return {
            "double_gameweeks": [],
            "summary": f"No double gameweeks found in the next {num_gameweeks} gameweeks"
        }
    
    return {
        "double_gameweeks": double_gameweeks,
        "summary": f"Found {len(double_gameweeks)} double gameweeks in the next {num_gameweeks} gameweeks"
    }

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
    
    # Handle dictionary parameters
    if isinstance(position, dict):
        if 'position' in position:
            position = position['position']
        else:
            position = None
            
    if isinstance(team, dict):
        if 'team' in team:
            team = team['team']
        else:
            team = None
    
    if isinstance(min_price, dict):
        if 'min_price' in min_price:
            min_price = min_price['min_price']
        else:
            min_price = None
            
    if isinstance(max_price, dict):
        if 'max_price' in max_price:
            max_price = max_price['max_price']
        else:
            max_price = None
            
    if isinstance(min_points, dict):
        if 'min_points' in min_points:
            min_points = min_points['min_points']
        else:
            min_points = None
            
    if isinstance(min_ownership, dict):
        if 'min_ownership' in min_ownership:
            min_ownership = min_ownership['min_ownership']
        else:
            min_ownership = None
            
    if isinstance(max_ownership, dict):
        if 'max_ownership' in max_ownership:
            max_ownership = max_ownership['max_ownership']
        else:
            max_ownership = None
            
    if isinstance(form_threshold, dict):
        if 'form_threshold' in form_threshold:
            form_threshold = form_threshold['form_threshold']
        else:
            form_threshold = None
            
    if isinstance(include_gameweeks, dict):
        if 'include_gameweeks' in include_gameweeks:
            include_gameweeks = include_gameweeks['include_gameweeks']
        else:
            include_gameweeks = False
            
    if isinstance(num_gameweeks, dict):
        if 'num_gameweeks' in num_gameweeks:
            num_gameweeks = num_gameweeks['num_gameweeks']
        else:
            num_gameweeks = 5
            
    if isinstance(sort_by, dict):
        if 'sort_by' in sort_by:
            sort_by = sort_by['sort_by']
        else:
            sort_by = "total_points"
            
    if isinstance(sort_order, dict):
        if 'sort_order' in sort_order:
            sort_order = sort_order['sort_order']
        else:
            sort_order = "desc"
            
    if isinstance(limit, dict):
        if 'limit' in limit:
            limit = limit['limit']
        else:
            limit = 20
    
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

# Register prompts
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
    
    # Handle case when parameters are dictionaries
    if isinstance(entity_type, dict):
        if 'entity_type' in entity_type:
            entity_type = entity_type['entity_type']
        else:
            entity_type = "player"  # Default
    
    if isinstance(entity_name, dict):
        if 'entity_name' in entity_name:
            entity_name = entity_name['entity_name']
        elif 'player_name' in entity_name:
            entity_name = entity_name['player_name']
        elif 'query' in entity_name:
            entity_name = entity_name['query']
        else:
            # Convert to string as fallback
            entity_name = str(entity_name)
    
    # If entity_name is None, we can't proceed with certain entity types
    if entity_name is None and entity_type in ["player", "team"]:
        return {"error": f"Please provide a {entity_type} name to analyze"}
    
    if isinstance(num_gameweeks, dict):
        if 'num_gameweeks' in num_gameweeks:
            num_gameweeks = num_gameweeks['num_gameweeks']
        else:
            num_gameweeks = 5  # Default
    
    if isinstance(include_blanks, dict):
        if 'include_blanks' in include_blanks:
            include_blanks = include_blanks['include_blanks']
        else:
            include_blanks = True  # Default
    
    if isinstance(include_doubles, dict):
        if 'include_doubles' in include_doubles:
            include_doubles = include_doubles['include_doubles']
        else:
            include_doubles = True  # Default
    
    # Normalize entity type
    entity_type = entity_type.lower()
    if entity_type not in ["player", "team", "position"]:
        return {"error": f"Invalid entity type: {entity_type}. Must be 'player', 'team', or 'position'"}

    
    # Get current gameweek
    gameweeks_data = await api.get_gameweeks()
    current_gameweek = None
    
    for gw in gameweeks_data:
        if gw.get("is_current"):
            current_gameweek = gw.get("id")
            break
            
    if current_gameweek is None:
        # If no current gameweek found, try to find next gameweek
        for gw in gameweeks_data:
            if gw.get("is_next"):
                current_gameweek = gw.get("id") - 1
                break
                
    if current_gameweek is None:
        return {"error": "Could not determine current gameweek"}
    
    # Base result structure
    result = {
        "entity_type": entity_type,
        "entity_name": entity_name,
        "current_gameweek": current_gameweek,
        "analysis_range": list(range(current_gameweek + 1, current_gameweek + num_gameweeks + 1))
    }
    
    # Handle each entity type
    if entity_type == "player":
        # Find player and their team
        player_matches = await players.find_players_by_name(entity_name)
        if not player_matches:
            return {"error": f"No player found matching '{entity_name}'"}
            
        active_players = [p for p in player_matches]

        player = active_players[0]
        result["player"] = {
            "id": player["id"],
            "name": player["name"],
            "team": player["team"],
            "position": player["position"],
            "status": "available" if player["status"] == "a" else "unavailable"
        }
        
        # Get fixtures for player's team
        player_fixtures = await fixtures.get_player_fixtures(player["id"], num_gameweeks)
        
        # Calculate difficulty score
        total_difficulty = sum(f["difficulty"] for f in player_fixtures)
        avg_difficulty = total_difficulty / len(player_fixtures) if player_fixtures else 0
        
        # Scale difficulty (5 is hardest, 1 is easiest - invert so 10 is best)
        fixture_score = (6 - avg_difficulty) * 2 if player_fixtures else 0
        
        result["fixtures"] = player_fixtures
        result["fixture_analysis"] = {
            "difficulty_score": round(fixture_score, 1),
            "fixtures_analyzed": len(player_fixtures),
            "home_matches": sum(1 for f in player_fixtures if f["location"] == "home"),
            "away_matches": sum(1 for f in player_fixtures if f["location"] == "away"),
        }
        
        # Add fixture difficulty assessment
        if fixture_score >= 8:
            result["fixture_analysis"]["assessment"] = "Excellent fixtures"
        elif fixture_score >= 6:
            result["fixture_analysis"]["assessment"] = "Good fixtures"
        elif fixture_score >= 4:
            result["fixture_analysis"]["assessment"] = "Average fixtures"
        else:
            result["fixture_analysis"]["assessment"] = "Difficult fixtures"
    
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
            total_difficulty = sum(f["difficulty"] for f in formatted_fixtures)
            avg_difficulty = total_difficulty / len(formatted_fixtures)
            fixture_score = (6 - avg_difficulty) * 2
            
            result["fixture_analysis"] = {
                "difficulty_score": round(fixture_score, 1),
                "fixtures_analyzed": len(formatted_fixtures),
                "home_matches": sum(1 for f in formatted_fixtures if f["location"] == "home"),
                "away_matches": sum(1 for f in formatted_fixtures if f["location"] == "away"),
            }
            
            # Add fixture difficulty assessment
            if fixture_score >= 8:
                result["fixture_analysis"]["assessment"] = "Excellent fixtures"
            elif fixture_score >= 6:
                result["fixture_analysis"]["assessment"] = "Good fixtures"
            elif fixture_score >= 4:
                result["fixture_analysis"]["assessment"] = "Average fixtures"
            else:
                result["fixture_analysis"]["assessment"] = "Difficult fixtures"
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
                total_diff = sum(f["difficulty"] for f in team_fixtures)
                avg_diff = total_diff / len(team_fixtures)
                fixture_score = (6 - avg_diff) * 2
                
                team_difficulties[team] = {
                    "fixtures": team_fixtures,
                    "difficulty_score": round(fixture_score, 1),
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
    
    # Handle case when parameters are dictionaries
    if isinstance(player_names, dict):
        # Try to extract player names from the dictionary
        if 'player_names' in player_names:
            player_names = player_names['player_names']
        else:
            return {"error": "Could not find player names in the provided data"}
    
    # Handle metrics as a dictionary
    if isinstance(metrics, dict):
        if 'metrics' in metrics:
            metrics = metrics['metrics']
        else:
            # Use default metrics
            metrics = ["total_points", "form", "goals_scored", "assists", "bonus"]
    
    # Handle other parameters as dictionaries
    if isinstance(include_gameweeks, dict):
        if 'include_gameweeks' in include_gameweeks:
            include_gameweeks = include_gameweeks['include_gameweeks']
        else:
            include_gameweeks = False
    
    if isinstance(num_gameweeks, dict):
        if 'num_gameweeks' in num_gameweeks:
            num_gameweeks = num_gameweeks['num_gameweeks']
        else:
            num_gameweeks = 5
    
    if isinstance(include_fixture_analysis, dict):
        if 'include_fixture_analysis' in include_fixture_analysis:
            include_fixture_analysis = include_fixture_analysis['include_fixture_analysis']
        else:
            include_fixture_analysis = True
    
    if not player_names or len(player_names) < 2:
        return {"error": "Please provide at least two player names to compare"}
    
    # Find all players by name
    players_data = {}
    for name in player_names:
        matches = await players.find_players_by_name(name, limit=3)  # Get more matches to find active players
        if not matches:
            return {"error": f"No player found matching '{name}'"}
            
        # Filter to active players
        active_matches = [p for p in matches]
            
        # Use first active match
        player = active_matches[0]
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
            
            # Get gameweek data for each player
            for name, player in players_data.items():
                player_history = await fixtures.get_player_gameweek_history([player["id"]], num_gameweeks)
                
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
                blank_gws = await fixtures.get_blank_gameweeks(num_gameweeks)
                blank_impact = []
                
                for blank_gw in blank_gws:
                    for team_info in blank_gw.get("teams_without_fixtures", []):
                        if team_info.get("name") == team_name:
                            blank_impact.append(blank_gw["gameweek"])
                
                blank_gameweek_impacts[name] = blank_impact
                
                # Check for double gameweeks
                double_gws = await fixtures.get_double_gameweeks(num_gameweeks)
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

@mcp.prompt()
def transfer_advice_prompt(budget: float, position: str = None, team_to_sell: str = None) -> str:
    """Create a prompt for getting detailed FPL transfer advice
    
    Args:
        budget: Available budget in millions (e.g., 8.5)
        position: Optional position to target (e.g., MID, FWD, DEF, GKP)
        team_to_sell: Optional team name if selling a player from that team
    """
    position_text = f"a {position}" if position else "any position"
    team_text = f" to replace a player from {team_to_sell}" if team_to_sell else ""
    
    return (
        f"I need transfer advice for my Fantasy Premier League team. "
        f"I have £{budget}m to spend on {position_text}{team_text}. "
        f"\n\nPlease recommend the best options considering:"
        f"\n1. Current form and consistency"
        f"\n2. Upcoming fixture difficulty"
        f"\n3. Value for money compared to similar players"
        f"\n4. Blank/double gameweeks that might affect performance"
        f"\n5. Expected returns based on xG, xA, and other advanced metrics"
        f"\n\nFor each recommendation, please explain your reasoning and any potential risks."
    )

@mcp.prompt()
def player_analysis_prompt(player_name: str, include_comparisons: bool = True) -> str:
    """Create a prompt for analyzing an FPL player in depth
    
    Args:
        player_name: Name of the player to analyze
        include_comparisons: Whether to compare with similar players
    """
    comparison_text = (
        "\n5. How they compare to similar players in their position and price range" 
        if include_comparisons else ""
    )
    
    return (
        f"Please provide a comprehensive analysis of {player_name} as an FPL asset. "
        f"I'd like to understand:"
        f"\n\n1. Recent form, performance statistics, and underlying metrics (xG, xA)"
        f"\n2. Upcoming fixtures and their difficulty ratings"
        f"\n3. Value for money compared to their price point"
        f"\n4. Consistency of returns and minutes played (rotation risks) {comparison_text}"
        f"\n5. Consider other similar players in the same position and price range"
        f"\n6. Any potential blank or double gameweeks that might affect their performance"
        f"\n7. Any injury concerns or fitness issues"
        f"\n8. Any other relevant factors that could impact their performance"
        f"\n\nBased on this analysis, would you recommend buying, holding, or selling this player for the upcoming gameweeks?"
    )


@mcp.prompt()
def team_rating_prompt(player_list: str, budget_remaining: float = 0.0) -> str:
    """Create a prompt for rating and analyzing an FPL team
    
    Args:
        player_list: Comma-separated list of players in the team
        budget_remaining: Remaining budget in millions
    """
    return (
        f"Please rate and analyze my Fantasy Premier League team consisting of the following players:\n\n{player_list}"
        f"\n\nI have £{budget_remaining}m remaining in my budget."
        f"\n\nPlease provide:"
        f"\n1. An overall rating of my team (1-10)"
        f"\n2. Strengths and weaknesses in my team structure"
        f"\n3. Analysis of fixture coverage for the upcoming gameweeks"
        f"\n4. Suggested improvements or transfers to consider based on player form, fixtures and value"
        f"\n5. Players who might be rotation risks (based on minutes played) or have challenging fixtures"
        f"\n6. Any players I should consider captaining in the upcoming gameweek"
        f"\n7. Any injury concerns or fitness issues that might affect my players"
        f"\n\nFor each recommendation, please explain your reasoning and any potential risks."
    )


@mcp.prompt()
def differential_players_prompt(max_ownership: float = 10.0, budget: float = None) -> str:
    """Create a prompt for finding differential players with low ownership
    
    Args:
        max_ownership: Maximum ownership percentage to consider
        budget: Optional maximum budget per player in millions
    """
    budget_text = f" with a maximum price of £{budget}m" if budget else ""
    
    return (
        f"I'm looking for differential players with less than {max_ownership}% ownership{budget_text} "
        f"who could provide good value in the coming gameweeks."
        f"\n\nPlease suggest differentials for each position (GKP, DEF, MID, FWD) considering:"
        f"\n1. Recent form and underlying performance statistics"
        f"\n2. Upcoming fixture difficulty"
        f"\n3. Expected minutes and rotation risk"
        f"\n4. Set-piece involvement and penalty duties"
        f"\n5. Team attacking/defensive strength"
        f"\n\nFor each player, please explain why they might outperform their ownership percentage."
    )

@mcp.prompt()
def chip_strategy_prompt(available_chips: str) -> str:
    """Create a prompt for chip strategy advice
    
    Args:
        available_chips: Comma-separated list of available chips (e.g., "Wildcard, Free Hit, Bench Boost")
    """
    return (
        f"I still have the following FPL chips available: {available_chips}."
        f"\n\nPlease advise on the optimal strategy for using these chips considering:"
        f"\n1. Upcoming blank and double gameweeks"
        f"\n2. Fixture difficulty swings for top teams"
        f"\n3. Potential injury crises or international breaks"
        f"\n4. The current stage of the season"
        f"\n\nFor each chip, suggest specific gameweeks or scenarios when I should consider using them, "
        f"and explain the reasoning behind your recommendations."
    )


# Add cleanup for auth manager
def cleanup_auth():
    """Clean up authentication resources"""
    try:
        from .fpl.auth_manager import get_auth_manager
        auth_manager = get_auth_manager()
        
        # Create an event loop if none exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the close method
        if loop.is_running():
            loop.create_task(auth_manager.close())
        else:
            loop.run_until_complete(auth_manager.close())
    except Exception as e:
        logger.error(f"Error during authentication cleanup: {e}")

# Register cleanup
atexit.register(cleanup_auth)

# Main function for direct execution and entry point
def main():
    """Run the Fantasy Premier League MCP server."""
    logger.info("Starting Fantasy Premier League MCP Server")
    mcp.run()

# Run the server if executed directly
if __name__ == "__main__":
    main()