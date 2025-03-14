#!/usr/bin/env python3

import logging
from typing import List, Dict, Any, Optional, Union

from ..api import api

# Set up logging following project conventions
logger = logging.getLogger("fpl-mcp-server.fixtures")


async def get_fixtures_resource(gameweek_id: Optional[int] = None, team_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get fixtures from the FPL API with optional filtering by gameweek or team

    Args:
        gameweek_id: Optional ID of gameweek to filter by
        team_name: Optional team name to filter by

    Returns:
        List of fixtures with formatted data
    """
    logger.info(f"Getting fixtures (gameweek_id={gameweek_id}, team_name={team_name})")
    
    # Get raw fixtures data
    fixtures = await api.get_fixtures()
    if not fixtures:
        logger.warning("No fixtures data found")
        return []
    
    # Get teams data for mapping IDs to names
    teams_data = await api.get_teams()
    team_map = {t["id"]: t for t in teams_data}
    
    # Format each fixture
    formatted_fixtures = []
    for fixture in fixtures:
        # Get team data
        home_team = team_map.get(fixture.get("team_h", 0), {})
        away_team = team_map.get(fixture.get("team_a", 0), {})
        
        # Format fixture data
        formatted_fixture = {
            "id": fixture.get("id", 0),
            "gameweek": fixture.get("event", 0),
            "home_team": {
                "id": fixture.get("team_h", 0),
                "name": home_team.get("name", f"Team {fixture.get('team_h', 0)}"),
                "short_name": home_team.get("short_name", ""),
                "strength": home_team.get("strength_overall_home", 0)
            },
            "away_team": {
                "id": fixture.get("team_a", 0),
                "name": away_team.get("name", f"Team {fixture.get('team_a', 0)}"),
                "short_name": away_team.get("short_name", ""),
                "strength": away_team.get("strength_overall_away", 0)
            },
            "kickoff_time": fixture.get("kickoff_time", ""),
            "difficulty": {
                "home": fixture.get("team_h_difficulty", 0),
                "away": fixture.get("team_a_difficulty", 0)
            },
            "stats": fixture.get("stats", [])
        }
        
        formatted_fixtures.append(formatted_fixture)
    
    # Apply gameweek filter if provided
    if gameweek_id is not None:
        formatted_fixtures = [
            f for f in formatted_fixtures if f["gameweek"] == gameweek_id
        ]
    
    # Apply team filter if provided
    if team_name is not None:
        team_name_lower = team_name.lower()
        filtered_fixtures = []
        
        for fixture in formatted_fixtures:
            home_name = fixture["home_team"]["name"].lower()
            away_name = fixture["away_team"]["name"].lower()
            home_short = fixture["home_team"]["short_name"].lower()
            away_short = fixture["away_team"]["short_name"].lower()
            
            if (team_name_lower in home_name or team_name_lower in home_short or
                team_name_lower in away_name or team_name_lower in away_short):
                filtered_fixtures.append(fixture)
        
        formatted_fixtures = filtered_fixtures
    
    # Sort by gameweek and then by kickoff time
    formatted_fixtures.sort(key=lambda x: (x["gameweek"] or 0, x["kickoff_time"] or ""))
    
    return formatted_fixtures


async def get_player_fixtures(player_id: int, num_fixtures: int = 5) -> List[Dict[str, Any]]:
    """Get upcoming fixtures for a specific player

    Args:
        player_id: FPL ID of the player
        num_fixtures: Number of upcoming fixtures to return

    Returns:
        List of upcoming fixtures for the player
    """
    logger.info(f"Getting player fixtures (player_id={player_id}, num_fixtures={num_fixtures})")
    
    # Get player data to find their team
    players_data = await api.get_players()
    player = None
    for p in players_data:
        if p.get("id") == player_id:
            player = p
            break
    
    if not player:
        logger.warning(f"Player with ID {player_id} not found")
        return []
    
    team_id = player.get("team")
    if not team_id:
        logger.warning(f"Team ID not found for player {player_id}")
        return []
    
    # Get all fixtures
    all_fixtures = await api.get_fixtures()
    if not all_fixtures:
        logger.warning("No fixtures data found")
        return []
    
    # Get gameweeks to determine current gameweek
    gameweeks = await api.get_gameweeks()
    current_gameweek = None
    for gw in gameweeks:
        if gw.get("is_current"):
            current_gameweek = gw.get("id")
            break
    
    if not current_gameweek:
        for gw in gameweeks:
            if gw.get("is_next"):
                current_gameweek = gw.get("id") - 1
                break
    
    if not current_gameweek:
        logger.warning("Could not determine current gameweek")
        return []
    
    # Filter upcoming fixtures for player's team
    upcoming_fixtures = []
    
    for fixture in all_fixtures:
        # Only include fixtures from current gameweek onwards
        if fixture.get("event") and fixture.get("event") >= current_gameweek:
            # Check if player's team is involved
            if fixture.get("team_h") == team_id or fixture.get("team_a") == team_id:
                upcoming_fixtures.append(fixture)
    
    # Sort by gameweek
    upcoming_fixtures.sort(key=lambda x: x.get("event", 0))
    
    # Limit to requested number of fixtures
    upcoming_fixtures = upcoming_fixtures[:num_fixtures]
    
    # Get teams data for mapping IDs to names
    teams_data = await api.get_teams()
    team_map = {t["id"]: t for t in teams_data}
    
    # Format fixtures
    formatted_fixtures = []
    for fixture in upcoming_fixtures:
        home_id = fixture.get("team_h", 0)
        away_id = fixture.get("team_a", 0)
        
        # Determine if player's team is home or away
        is_home = home_id == team_id
        
        # Get opponent team data
        opponent_id = away_id if is_home else home_id
        opponent_team = team_map.get(opponent_id, {})
        
        # Determine difficulty - higher is more difficult
        difficulty = fixture.get("team_h_difficulty" if is_home else "team_a_difficulty", 3)
        
        formatted_fixture = {
            "gameweek": fixture.get("event"),
            "kickoff_time": fixture.get("kickoff_time", ""),
            "location": "home" if is_home else "away",
            "opponent": opponent_team.get("name", f"Team {opponent_id}"),
            "opponent_short": opponent_team.get("short_name", ""),
            "difficulty": difficulty,
        }
        
        formatted_fixtures.append(formatted_fixture)
    
    return formatted_fixtures


async def analyze_player_fixtures(player_id: int, num_fixtures: int = 5) -> Dict[str, Any]:
    """Analyze upcoming fixtures for a player and provide a difficulty rating

    Args:
        player_id: FPL ID of the player
        num_fixtures: Number of upcoming fixtures to analyze

    Returns:
        Analysis of player's upcoming fixtures with difficulty ratings
    """
    logger.info(f"Analyzing player fixtures (player_id={player_id}, num_fixtures={num_fixtures})")
    
    # Get player data
    players_data = await api.get_players()
    player = None
    for p in players_data:
        if p.get("id") == player_id:
            player = p
            break
    
    if not player:
        logger.warning(f"Player with ID {player_id} not found")
        return {"error": f"Player with ID {player_id} not found"}
    
    # Get player's fixtures
    fixtures = await get_player_fixtures(player_id, num_fixtures)
    if not fixtures:
        return {
            "player": {
                "id": player_id,
                "name": player.get("web_name", "Unknown player"),
                "team": player.get("team_name", "Unknown team"),
                "position": player.get("element_type_name", "Unknown position"),
            },
            "fixture_analysis": {
                "fixtures_analyzed": [],
                "difficulty_score": 0,
                "analysis": "No upcoming fixtures found"
            }
        }
    
    # Calculate difficulty score (lower is better)
    total_difficulty = sum(f["difficulty"] for f in fixtures)
    avg_difficulty = total_difficulty / len(fixtures)
    
    # Adjust for home/away balance (home advantage)
    home_fixtures = [f for f in fixtures if f["location"] == "home"]
    home_percentage = len(home_fixtures) / len(fixtures) * 100
    
    # Scale to 1-10 (invert so higher is better)
    # Difficulty is originally 1-5, where 5 is most difficult
    # We want 1-10 where 10 is best fixtures
    fixture_score = (6 - avg_difficulty) * 2
    
    # Adjust for home advantage (up to +0.5 for all home, -0.5 for all away)
    home_adjustment = (home_percentage - 50) / 100
    adjusted_score = fixture_score + home_adjustment
    
    # Cap between 1-10
    final_score = max(1, min(10, adjusted_score))
    
    # Generate text analysis
    if final_score >= 8.5:
        analysis = "Excellent fixtures - highly favorable schedule"
    elif final_score >= 7:
        analysis = "Good fixtures - favorable schedule"
    elif final_score >= 5.5:
        analysis = "Average fixtures - balanced schedule"
    elif final_score >= 4:
        analysis = "Difficult fixtures - challenging schedule"
    else:
        analysis = "Very difficult fixtures - extremely challenging schedule"
    
    # Return formatted analysis
    return {
        "player": {
            "id": player_id,
            "name": player.get("web_name", "Unknown player"),
            "team": player.get("team_name", "Unknown team"),
            "position": player.get("element_type_name", "Unknown position"),
        },
        "fixture_analysis": {
            "fixtures_analyzed": fixtures,
            "difficulty_score": round(final_score, 1),
            "analysis": analysis,
            "home_fixtures_percentage": round(home_percentage, 1)
        }
    }


async def get_blank_gameweeks(num_gameweeks: int = 5) -> List[Dict[str, Any]]:
    """
    Identify upcoming blank gameweeks where teams don't have a fixture.
    
    Args:
        num_gameweeks: Number of upcoming gameweeks to analyze
        
    Returns:
        List of blank gameweeks with affected teams
    """
    # Get gameweek data
    all_gameweeks = await api.get_gameweeks()
    all_fixtures = await api.get_fixtures()
    team_data = await api.get_teams()
    
    # Get current gameweek
    current_gw = None
    for gw in all_gameweeks:
        if gw.get("is_current", False) or gw.get("is_next", False):
            current_gw = gw
            break
    
    if not current_gw:
        return []
        
    current_gw_id = current_gw["id"]
    
    # Limit to specified number of upcoming gameweeks
    upcoming_gameweeks = [gw for gw in all_gameweeks 
                         if gw["id"] >= current_gw_id and 
                            gw["id"] < current_gw_id + num_gameweeks]
    
    # Map team IDs to names
    team_map = {t["id"]: t for t in team_data}
    
    # Results to return
    blank_gameweeks = []
    
    # Analyze each upcoming gameweek
    for gameweek in upcoming_gameweeks:
        gw_id = gameweek["id"]
        
        # Get fixtures for this gameweek
        gw_fixtures = [f for f in all_fixtures if f.get("event") == gw_id]
        
        # Get teams with fixtures this gameweek
        teams_with_fixtures = set()
        for fixture in gw_fixtures:
            teams_with_fixtures.add(fixture.get("team_h"))
            teams_with_fixtures.add(fixture.get("team_a"))
        
        # Identify teams without fixtures (blank gameweek)
        teams_without_fixtures = []
        for team_id, team in team_map.items():
            if team_id not in teams_with_fixtures:
                teams_without_fixtures.append({
                    "id": team_id,
                    "name": team.get("name", f"Team {team_id}"),
                    "short_name": team.get("short_name", "")
                })
        
        # If teams have blank gameweek, add to results
        if teams_without_fixtures:
            blank_gameweeks.append({
                "gameweek": gw_id,
                "name": gameweek.get("name", f"Gameweek {gw_id}"),
                "teams_without_fixtures": teams_without_fixtures,
                "count": len(teams_without_fixtures)
            })
    
    return blank_gameweeks


async def get_double_gameweeks(num_gameweeks: int = 5) -> List[Dict[str, Any]]:
    """
    Identify upcoming double gameweeks where teams have multiple fixtures.
    
    Args:
        num_gameweeks: Number of upcoming gameweeks to analyze
        
    Returns:
        List of double gameweeks with affected teams
    """
    # Get gameweek data
    all_gameweeks = await api.get_gameweeks()
    all_fixtures = await api.get_fixtures()
    team_data = await api.get_teams()
    
    # Get current gameweek
    current_gw = None
    for gw in all_gameweeks:
        if gw.get("is_current", False) or gw.get("is_next", False):
            current_gw = gw
            break
    
    if not current_gw:
        return []
        
    current_gw_id = current_gw["id"]
    
    # Limit to specified number of upcoming gameweeks
    upcoming_gameweeks = [gw for gw in all_gameweeks 
                         if gw["id"] >= current_gw_id and 
                            gw["id"] < current_gw_id + num_gameweeks]
    
    # Map team IDs to names
    team_map = {t["id"]: t for t in team_data}
    
    # Results to return
    double_gameweeks = []
    
    # Analyze each upcoming gameweek
    for gameweek in upcoming_gameweeks:
        gw_id = gameweek["id"]
        
        # Get fixtures for this gameweek
        gw_fixtures = [f for f in all_fixtures if f.get("event") == gw_id]
        
        # Count fixtures per team
        team_fixture_count = {}
        for fixture in gw_fixtures:
            home_team = fixture.get("team_h")
            away_team = fixture.get("team_a")
            
            team_fixture_count[home_team] = team_fixture_count.get(home_team, 0) + 1
            team_fixture_count[away_team] = team_fixture_count.get(away_team, 0) + 1
        
        # Identify teams with multiple fixtures (double gameweek)
        teams_with_doubles = []
        for team_id, count in team_fixture_count.items():
            if count > 1:
                team = team_map.get(team_id, {})
                teams_with_doubles.append({
                    "id": team_id,
                    "name": team.get("name", f"Team {team_id}"),
                    "short_name": team.get("short_name", ""),
                    "fixture_count": count
                })
        
        # If teams have double gameweek, add to results
        if teams_with_doubles:
            double_gameweeks.append({
                "gameweek": gw_id,
                "name": gameweek.get("name", f"Gameweek {gw_id}"),
                "teams_with_doubles": teams_with_doubles,
                "count": len(teams_with_doubles)
            })
    
    return double_gameweeks