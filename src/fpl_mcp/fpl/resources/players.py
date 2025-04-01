import json
from typing import Any, Dict, List, Optional
import logging
from ..api import api

async def get_players_resource(name_filter: Optional[str] = None, team_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Format player data for the MCP resource.
    
    Args:
        name_filter: Optional filter for player name (case-insensitive partial match)
        team_filter: Optional filter for team name (case-insensitive partial match)
        
    Returns:
        Formatted player data
    """
    # Get raw data from API
    data = await api.get_bootstrap_static()
    
    # Create team and position lookup maps
    team_map = {t["id"]: t for t in data["teams"]}
    position_map = {p["id"]: p for p in data["element_types"]}
    logging.info(f"Team map: {team_map}")
    logging.info(f"Position map: {position_map}")
    
    # Format player data
    players = []
    for player in data["elements"]:
        # Extract team and position info
        team = team_map.get(player["team"], {})
        position = position_map.get(player["element_type"], {})
        
        player_name = f"{player['first_name']} {player['second_name']}"
        team_name = team.get("name", "Unknown")
        
        # Apply filters if specified
        if name_filter and name_filter.lower() not in player_name.lower():
            continue
            
        if team_filter and team_filter.lower() not in team_name.lower():
            continue
        
        # Build comprehensive player object with all available stats
        player_data = {
            "id": player["id"],
            "name": player_name,
            "web_name": player["web_name"],
            "team": team_name,
            "team_short": team.get("short_name", "UNK"),
            "position": position.get("singular_name_short", "UNK"),
            "price": player["now_cost"] / 10.0,
            "form": player["form"],
            "points": player["total_points"],
            "points_per_game": player["points_per_game"],
            
            # Playing time
            "minutes": player["minutes"],
            "starts": player["starts"],
            
            # Key stats
            "goals": player["goals_scored"],
            "assists": player["assists"],
            "clean_sheets": player["clean_sheets"],
            "goals_conceded": player["goals_conceded"],
            "own_goals": player["own_goals"],
            "penalties_saved": player["penalties_saved"],
            "penalties_missed": player["penalties_missed"],
            "yellow_cards": player["yellow_cards"],
            "red_cards": player["red_cards"],
            "saves": player["saves"],
            "bonus": player["bonus"],
            "bps": player["bps"],
            
            # Advanced metrics
            "influence": player["influence"],
            "creativity": player["creativity"],
            "threat": player["threat"],
            "ict_index": player["ict_index"],
            
            # Expected stats (if available)
            "expected_goals": player.get("expected_goals", "N/A"),
            "expected_assists": player.get("expected_assists", "N/A"),
            "expected_goal_involvements": player.get("expected_goal_involvements", "N/A"),
            "expected_goals_conceded": player.get("expected_goals_conceded", "N/A"),
            
            # Ownership & transfers
            "selected_by_percent": player["selected_by_percent"],
            "transfers_in_event": player["transfers_in_event"],
            "transfers_out_event": player["transfers_out_event"],
            
            # Price changes
            "cost_change_event": player["cost_change_event"] / 10.0,
            "cost_change_start": player["cost_change_start"] / 10.0,
            
            # Status info
            "status": player["status"],
            "news": player["news"],
            "chance_of_playing_next_round": player["chance_of_playing_next_round"],
        }
        
        players.append(player_data)
    logging.info(f"Formatted {len(players)} players")
    return players

async def get_player_by_id(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed information for a specific player by ID.
    
    Args:
        player_id: FPL player ID
        
    Returns:
        Player data or None if not found
    """
    # Get all players
    all_players = await get_players_resource()
    
    # Find player by ID
    for player in all_players:
        if player["id"] == player_id:
            # Get additional detail data
            try:
                summary = await api.get_player_summary(player_id)
                
                # Add fixture history
                player["history"] = summary.get("history", [])
                
                # Add upcoming fixtures
                player["fixtures"] = summary.get("fixtures", [])
                
                return player
            except Exception as e:
                # Return basic player data if detailed data not available
                return player
    
    return None

async def find_players_by_name(name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Find players by partial name match with advanced matching.
    
    Args:
        name: Player name to search for (supports partial names, nicknames, and initials)
        limit: Maximum number of results to return
        
    Returns:
        List of matching players sorted by relevance and points
    """
    # Get all players
    logger = logging.getLogger(__name__)
    logger.info(f"Finding players by name: {name}")
    all_players = await get_players_resource()
    logger.info(f"Found {len(all_players)} players")
    
    # Normalize search term
    search_term = name.lower().strip()
    if not search_term:
        return []
    
    # Common nickname and abbreviation mapping
    nicknames = {
        "kdb": "kevin de bruyne",
        "vvd": "virgil van dijk",
        "taa": "trent alexander-arnold",
        "cr7": "cristiano ronaldo",
        "bobby": "roberto firmino",
        "mo salah": "mohamed salah",
        "mane": "sadio mane",
        "auba": "aubameyang",
        "lewa": "lewandowski",
        "kane": "harry kane",
        "rashford": "marcus rashford",
        "son": "heung-min son",
    }
    
    # Check for nickname match
    if search_term in nicknames:
        search_term = nicknames[search_term]
    
    # Split search term into parts for multi-part matching
    search_parts = search_term.split()

    
    # Store scored results
    scored_players = []
    
    for player in all_players:
        # Extract player name components
        full_name = player["name"].lower()
        web_name = player.get("web_name", "").lower()
        
        # Try to extract first and last name
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[-1] if len(name_parts) > 1 else ""
        
        # Initialize score and tracking reasons
        score = 0
        
        # 1. Exact full name match
        if search_term == full_name:
            score += 100
        
        # 2. Exact match on web_name (common name)
        elif search_term == web_name:
            score += 90
        
        # 3. Exact match on last name
        elif len(search_parts) == 1 and search_term == last_name:
            score += 80
        
        # 4. Exact match on first name
        elif len(search_parts) == 1 and search_term == first_name:
            score += 70
            
        # 5. Check for initials match (e.g., "KDB")
        if len(search_term) <= 5 and all(c.isalpha() for c in search_term):
            # Try to match initials
            initials = ''.join(part[0] for part in full_name.split() if part)
            if search_term.lower() == initials.lower():
                score += 85
        
        # 6. Multi-part name matching (e.g., "Mo Salah")
        if len(search_parts) > 1:
            # Check if first part matches first name and last part matches last name
            if (search_parts[0] in first_name and 
                search_parts[-1] in last_name):
                score += 75
            
            # Check if parts appear in order in the full name
            search_combined = ''.join(search_parts)
            full_combined = ''.join(full_name.split())
            if search_combined in full_combined:
                score += 50
        
        # 7. Substring matches
        if search_term in full_name:
            score += 40
        
        # 8. Partial word matches in full name
        for part in search_parts:
            if part in full_name:
                score += 30
                
        # 9. Partial word matches in web name
        for part in search_parts:
            if part in web_name:
                score += 25
        
        # 10. Add a bonus score for high-point players (tiebreaker)
        points_score = min(20, float(player["points"]) / 50)  # Up to 20 extra points
        
        # Total score
        total_score = score + (points_score if score > 0 else 0)
        
        # Add to results if there's any match
        if score > 0:
            scored_players.append((total_score, player))
    
    # Sort by score (highest first)
    sorted_players = [player for _, player in sorted(scored_players, key=lambda x: x[0], reverse=True)]
    # If no matches with good confidence, fall back to simple contains match
    if not sorted_players or (sorted_players and scored_players[0][0] < 30):
        fallback_players = [
            p for p in all_players 
            if search_term in p["name"].lower() or search_term in p.get("web_name", "").lower()
        ]
        # Sort fallback by points
        fallback_players.sort(key=lambda p: float(p["points"]), reverse=True)
        
        # Merge results, prioritizing scored results
        merged = []
        seen_ids = set(p["id"] for p in sorted_players)
        
        merged.extend(sorted_players)
        for p in fallback_players:
            if p["id"] not in seen_ids:
                merged.append(p)
                seen_ids.add(p["id"])
        
        sorted_players = merged
    
    # Return limited results
    return sorted_players[:limit]