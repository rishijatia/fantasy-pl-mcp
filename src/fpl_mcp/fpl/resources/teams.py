import json
from typing import Any, Dict, List, Optional

from ..api import api

async def get_teams_resource() -> List[Dict[str, Any]]:
    """
    Format teams data for the MCP resource.
    
    Returns:
        Formatted teams data
    """
    # Get raw data from API
    data = await api.get_bootstrap_static()
    
    # Format team data
    teams = []
    for team in data["teams"]:
        team_data = {
            "id": team["id"],
            "name": team["name"],
            "short_name": team["short_name"],
            "code": team["code"],
            
            # Strength ratings
            "strength": team["strength"],
            "strength_overall_home": team["strength_overall_home"],
            "strength_overall_away": team["strength_overall_away"],
            "strength_attack_home": team["strength_attack_home"],
            "strength_attack_away": team["strength_attack_away"],
            "strength_defence_home": team["strength_defence_home"],
            "strength_defence_away": team["strength_defence_away"],
            
            # Performance stats
            "position": team["position"]
        }
        
        teams.append(team_data)
    
    # Sort by position (league standing)
    teams.sort(key=lambda t: t["position"])
    
    return teams

async def get_team_by_id(team_id: int) -> Optional[Dict[str, Any]]:
    """
    Get team data by ID.
    
    Args:
        team_id: FPL team ID
        
    Returns:
        Team data or None if not found
    """
    teams = await get_teams_resource()
    
    for team in teams:
        if team["id"] == team_id:
            return team
            
    return None

async def get_team_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Get team data by name (full or partial match).
    
    Args:
        name: Team name to search for
        
    Returns:
        Team data or None if not found
    """
    teams = await get_teams_resource()
    name_lower = name.lower()
    
    # Try exact match first
    for team in teams:
        if team["name"].lower() == name_lower or team["short_name"].lower() == name_lower:
            return team
    
    # Then try partial match
    for team in teams:
        if name_lower in team["name"].lower() or name_lower in team["short_name"].lower():
            return team
            
    return None