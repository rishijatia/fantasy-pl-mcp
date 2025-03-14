#!/usr/bin/env python3

import json
import logging
import asyncio
import os
import sys
from typing import List, Dict, Any, Optional

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
from .fpl.resources import players, teams, gameweeks
from .fpl.tools import comparisons

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

# Register tools
@mcp.tool()
async def compare_players(player1_name: str, player2_name: str) -> Dict[str, Any]:
    """Compare two players by searching their names and showing detailed statistical comparison
    
    Args:
        player1_name: First player's name or partial name to search
        player2_name: Second player's name or partial name to search
    
    Returns:
        Detailed comparison of the two players' statistics
    """
    logger.info(f"Tool called: compare_players({player1_name}, {player2_name})")
    comparison = await comparisons.compare_players_by_name(player1_name, player2_name)
    
    if "error" in comparison:
        return comparison
    
    # Build a formatted result
    formatted_results = {
        "players": {
            comparison["player1"]["name"]: {
                "team": comparison["player1"]["team"],
                "position": comparison["player1"]["position"],
                "price": f"£{comparison['player1']['price']}m",
            },
            comparison["player2"]["name"]: {
                "team": comparison["player2"]["team"],
                "position": comparison["player2"]["position"],
                "price": f"£{comparison['player2']['price']}m",
            },
        },
        "statistics_comparison": {},
        "summary": {
            "stats_won_by": {
                comparison["player1"]["name"]: comparison["summary"]["player1_better_stats"],
                comparison["player2"]["name"]: comparison["summary"]["player2_better_stats"],
            },
            "equal_stats": comparison["summary"]["equal_stats"],
        }
    }
    
    # Add detailed stat comparisons
    for stat_key, stat_data in comparison["stats"].items():
        formatted_results["statistics_comparison"][stat_data["name"]] = {
            comparison["player1"]["name"]: stat_data["player1_value"],
            comparison["player2"]["name"]: stat_data["player2_value"],
            "difference": stat_data["difference"],
            "better_player": (
                comparison["player1"]["name"] if stat_data["better_player"] == "player1" else
                comparison["player2"]["name"] if stat_data["better_player"] == "player2" else
                "Equal"
            )
        }
    
    # Add value for money if available
    if "value_for_money" in comparison:
        vfm = comparison["value_for_money"]
        formatted_results["statistics_comparison"]["Points Per £1m"] = {
            comparison["player1"]["name"]: vfm["player1_value"],
            comparison["player2"]["name"]: vfm["player2_value"],
            "difference": vfm["difference"],
            "better_player": (
                comparison["player1"]["name"] if vfm["better_player"] == "player1" else
                comparison["player2"]["name"] if vfm["better_player"] == "player2" else
                "Equal"
            )
        }
    
    # Add overall recommendation
    better_player = None
    if comparison["summary"]["overall_recommendation"] == "player1":
        better_player = comparison["player1"]["name"]
    elif comparison["summary"]["overall_recommendation"] == "player2":
        better_player = comparison["player2"]["name"]
    
    if better_player:
        formatted_results["summary"]["recommendation"] = f"{better_player} is statistically better"
    else:
        formatted_results["summary"]["recommendation"] = "Players are statistically similar"
    
    return formatted_results

@mcp.tool()
async def find_players(search_term: str, limit: int = 5) -> Dict[str, Any]:
    """Find FPL players by name or team
    
    Args:
        search_term: Player name or team to search for
        limit: Maximum number of results to return (default: 5)
    
    Returns:
        List of matching players with key stats
    """
    logger.info(f"Tool called: find_players({search_term}, {limit})")
    
    # Try searching by player name first
    player_matches = await players.find_players_by_name(search_term, limit=limit)
    
    if player_matches:
        # Format player data
        results = []
        for player in player_matches:
            results.append({
                "name": player["name"],
                "team": player["team"],
                "position": player["position"],
                "price": f"£{player['price']}m",
                "form": player["form"],
                "points": player["points"],
                "points_per_game": player["points_per_game"],
                "selected_by_percent": f"{player['selected_by_percent']}%",
            })
        
        return {
            "search_term": search_term,
            "found_by": "player_name",
            "results": results
        }
    
    # If no players found, try searching by team
    team = await teams.get_team_by_name(search_term)
    if team:
        all_players = await players.get_players_resource()
        team_players = [
            p for p in all_players 
            if p["team"].lower() == team["name"].lower() or 
               p["team_short"].lower() == team["short_name"].lower()
        ]
        
        # Sort by total points
        team_players.sort(key=lambda p: float(p["points"]), reverse=True)
        
        # Format player data
        results = []
        for player in team_players[:limit]:
            results.append({
                "name": player["name"],
                "position": player["position"],
                "price": f"£{player['price']}m",
                "form": player["form"],
                "points": player["points"],
                "points_per_game": player["points_per_game"],
            })
        
        return {
            "search_term": search_term,
            "found_by": "team_name",
            "team": team["name"],
            "results": results
        }
    
    # No results found
    return {
        "search_term": search_term,
        "found_by": None,
        "results": []
    }

# Register prompts
@mcp.prompt()
def player_analysis_prompt(player_name: str) -> str:
    """Create a prompt for analyzing an FPL player"""
    return f"Please analyze {player_name} as an FPL asset. I want to understand:\n" \
           f"1. Current form and performance\n" \
           f"2. Upcoming fixtures and their difficulty\n" \
           f"3. Value for money compared to similar players\n" \
           f"4. Whether I should consider buying, selling, or holding this player"

@mcp.prompt()
def transfer_advice_prompt(budget: float, position: str) -> str:
    """Create a prompt for getting transfer advice"""
    return f"I need transfer advice for my Fantasy Premier League team. " \
           f"I'm looking for a {position} player with a budget of £{budget}m. " \
           f"Please suggest the best options based on form, fixtures, and value."

# Main function for direct execution and entry point
def main():
    """Run the Fantasy Premier League MCP server."""
    logger.info("Starting Fantasy Premier League MCP Server")
    mcp.run()

# Run the server if executed directly
if __name__ == "__main__":
    main()