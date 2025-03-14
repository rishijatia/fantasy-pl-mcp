import json
import datetime
from typing import Any, Dict, List, Optional

from ..api import api
from .players import find_players_by_name

async def get_gameweeks_resource() -> List[Dict[str, Any]]:
    """
    Format gameweek data for the MCP resource.
    
    Returns:
        Formatted gameweeks data
    """
    # Get raw data from API
    gameweeks = await api.get_gameweeks()
    
    # Format data
    formatted_gameweeks = []
    for gw in gameweeks:
        gw_data = {
            "id": gw["id"],
            "name": gw["name"],
            "deadline_time": gw["deadline_time"],
            "is_current": gw["is_current"],
            "is_next": gw["is_next"],
            "is_previous": gw["is_previous"],
            "finished": gw["finished"],
            "data_checked": gw["data_checked"],
            "highest_score": gw.get("highest_score", None),
            "most_selected": gw.get("most_selected", None),
            "most_transferred_in": gw.get("most_transferred_in", None),
            "most_captained": gw.get("most_captained", None),
            "most_vice_captained": gw.get("most_vice_captained", None),
            "average_entry_score": gw.get("average_entry_score", None),
        }
        
        formatted_gameweeks.append(gw_data)
    
    return formatted_gameweeks

async def get_current_gameweek_resource() -> Dict[str, Any]:
    """
    Get current gameweek data with additional details.
    
    Returns:
        Current gameweek data with enhanced information
    """
    # Get current gameweek
    current_gw = await api.get_current_gameweek()
    
    # Get raw data to extract player details
    all_data = await api.get_bootstrap_static()
    
    # Create enhanced gameweek data
    gw_data = {
        "id": current_gw["id"],
        "name": current_gw["name"],
        "deadline_time": current_gw["deadline_time"],
        "is_current": current_gw["is_current"],
        "is_next": current_gw["is_next"],
        "finished": current_gw["finished"],
        "data_checked": current_gw["data_checked"],
        "status": "Current" if current_gw.get("is_current", False) else "Next",
    }
    
    # Format deadline time to be more readable
    try:
        deadline = datetime.datetime.strptime(current_gw["deadline_time"], "%Y-%m-%dT%H:%M:%SZ")
        gw_data["deadline_formatted"] = deadline.strftime("%A, %d %B %Y at %H:%M UTC")
        
        # Calculate time until deadline
        now = datetime.datetime.utcnow()
        if deadline > now:
            delta = deadline - now
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            
            time_parts = []
            if days > 0:
                time_parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                time_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0:
                time_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                
            gw_data["time_until_deadline"] = ", ".join(time_parts)
        else:
            gw_data["time_until_deadline"] = "Deadline passed"
    except (ValueError, TypeError):
        gw_data["deadline_formatted"] = current_gw["deadline_time"]
    
    # Add stats if available
    if current_gw.get("highest_score") is not None:
        gw_data["stats"] = {
            "highest_score": current_gw["highest_score"],
            "average_score": current_gw.get("average_entry_score", "N/A"),
            "chip_plays": current_gw.get("chip_plays", []),
        }
    
    # Add most popular players if available
    popular_players = {}
    player_map = {p["id"]: p for p in all_data.get("elements", [])}
    
    popular_fields = [
        ("most_selected", "Most Selected"),
        ("most_transferred_in", "Most Transferred In"),
        ("most_captained", "Most Captained"),
        ("most_vice_captained", "Most Vice Captained")
    ]
    
    for field_key, field_name in popular_fields:
        player_id = current_gw.get(field_key)
        if player_id:
            player = player_map.get(player_id)
            if player:
                popular_players[field_name] = {
                    "id": player["id"],
                    "name": f"{player['first_name']} {player['second_name']}",
                    "web_name": player["web_name"],
                    "team": player["team"],
                }
    
    if popular_players:
        gw_data["popular_players"] = popular_players
    
    # Add fixtures if the API has them
    fixtures = await api.get_fixtures()
    if fixtures:
        gw_fixtures = [f for f in fixtures if f.get("event") == current_gw["id"]]
        if gw_fixtures:
            gw_data["fixture_count"] = len(gw_fixtures)
    
    return gw_data