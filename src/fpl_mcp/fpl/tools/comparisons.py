import json
from typing import Any, Dict, List, Optional, Tuple

from ..api import api
from ..resources.players import find_players_by_name, get_player_by_id

async def compare_players_by_name(player1_name: str, player2_name: str) -> Dict[str, Any]:
    """
    Compare two players based on their names.
    
    Args:
        player1_name: First player's name or partial name to search
        player2_name: Second player's name or partial name to search
        
    Returns:
        Dictionary with comparison results
    """
    # Find matching players
    player1_matches = await find_players_by_name(player1_name)
    player2_matches = await find_players_by_name(player2_name)
    
    # Check if we found any matches
    if not player1_matches:
        return {
            "error": f"No player found matching '{player1_name}'"
        }
        
    if not player2_matches:
        return {
            "error": f"No player found matching '{player2_name}'"
        }
    
    # Get the closest matches
    player1 = player1_matches[0]
    player2 = player2_matches[0]
    
    # Get detailed player data if possible
    try:
        detailed_player1 = await get_player_by_id(player1["id"])
        if detailed_player1:
            player1 = detailed_player1
    except Exception:
        pass
        
    try:
        detailed_player2 = await get_player_by_id(player2["id"])
        if detailed_player2:
            player2 = detailed_player2
    except Exception:
        pass
    
    # Perform comparison
    return await compare_players(player1, player2)

async def compare_players_by_id(player1_id: int, player2_id: int) -> Dict[str, Any]:
    """
    Compare two players based on their IDs.
    
    Args:
        player1_id: First player's FPL ID
        player2_id: Second player's FPL ID
        
    Returns:
        Dictionary with comparison results
    """
    # Get detailed player data
    player1 = await get_player_by_id(player1_id)
    player2 = await get_player_by_id(player2_id)
    
    # Check if players were found
    if not player1:
        return {
            "error": f"No player found with ID {player1_id}"
        }
        
    if not player2:
        return {
            "error": f"No player found with ID {player2_id}"
        }
    
    # Perform comparison
    return await compare_players(player1, player2)

async def compare_players(player1: Dict[str, Any], player2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two player objects.
    
    Args:
        player1: First player data
        player2: Second player data
        
    Returns:
        Dictionary with comparison results
    """
    # Basic information for both players
    comparison = {
        "player1": {
            "id": player1["id"],
            "name": player1["name"],
            "web_name": player1["web_name"],
            "team": player1["team"],
            "position": player1["position"],
            "price": player1["price"],
        },
        "player2": {
            "id": player2["id"],
            "name": player2["name"],
            "web_name": player2["web_name"],
            "team": player2["team"],
            "position": player2["position"],
            "price": player2["price"],
        }
    }
    
    # Detailed comparison with differences
    key_stats = [
        ("points", "Total Points"),
        ("form", "Form"),
        ("points_per_game", "Points Per Game"),
        ("minutes", "Minutes Played"),
        ("goals", "Goals"),
        ("assists", "Assists"),
        ("clean_sheets", "Clean Sheets"),
        ("goals_conceded", "Goals Conceded"),
        ("bonus", "Bonus Points"),
        ("bps", "BPS"),
        ("influence", "Influence"),
        ("creativity", "Creativity"),
        ("threat", "Threat"),
        ("ict_index", "ICT Index"),
        ("selected_by_percent", "Selected By %"),
    ]
    
    # Add comparison of all stats
    comparison["stats"] = {}
    
    for key, display_name in key_stats:
        if key in player1 and key in player2:
            # Get values, handling potential string values
            try:
                val1 = float(player1[key])
            except (ValueError, TypeError):
                val1 = player1[key]
                
            try:
                val2 = float(player2[key])
            except (ValueError, TypeError):
                val2 = player2[key]
            
            # Calculate difference if both are numeric
            difference = None
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                difference = val1 - val2
            
            comparison["stats"][key] = {
                "name": display_name,
                "player1_value": player1[key],
                "player2_value": player2[key],
                "difference": difference,
                "better_player": "player1" if difference and difference > 0 else 
                                ("player2" if difference and difference < 0 else "equal")
            }
    
    # Value for money comparison
    if "points" in player1 and "points" in player2 and "price" in player1 and "price" in player2:
        try:
            points1 = float(player1["points"])
            points2 = float(player2["points"])
            price1 = float(player1["price"])
            price2 = float(player2["price"])
            
            if price1 > 0 and price2 > 0:
                value1 = points1 / price1
                value2 = points2 / price2
                difference = value1 - value2
                
                comparison["value_for_money"] = {
                    "name": "Points Per £1m",
                    "player1_value": round(value1, 2),
                    "player2_value": round(value2, 2),
                    "difference": round(difference, 2),
                    "better_player": "player1" if difference > 0 else 
                                    ("player2" if difference < 0 else "equal")
                }
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    
    # Overall summary
    player1_wins = sum(1 for stat in comparison["stats"].values() 
                        if stat.get("better_player") == "player1")
    player2_wins = sum(1 for stat in comparison["stats"].values() 
                        if stat.get("better_player") == "player2")
    
    # Sort the stats by name to ensure consistent ordering
    sorted_stats = {}
    for key in sorted(comparison["stats"].keys()):
        sorted_stats[key] = comparison["stats"][key]
    comparison["stats"] = sorted_stats
    
    comparison["summary"] = {
        "player1_better_stats": player1_wins,
        "player2_better_stats": player2_wins,
        "equal_stats": len(comparison["stats"]) - player1_wins - player2_wins,
        "overall_recommendation": "player1" if player1_wins > player2_wins else 
                                 ("player2" if player2_wins > player1_wins else "equal")
    }
    
    return comparison