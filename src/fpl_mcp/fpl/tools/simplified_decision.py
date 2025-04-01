import logging
import asyncio
from typing import Dict, Any, List, Optional

from ..auth_manager import get_auth_manager
from ..api import api
from ..cache import cache, cached

logger = logging.getLogger(__name__)

# Simplified decision analysis function to avoid timeouts
async def get_simplified_league_decision_analysis(
    league_id: int,
    start_gw: int,
    end_gw: int,
    get_league_standings_func,
    get_teams_historical_data_func,
    league_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get simplified decision analysis for a league (optimized for performance)
    
    Args:
        league_id: ID of the league to analyze
        start_gw: Starting gameweek
        end_gw: Ending gameweek
        limit: Maximum number of teams to include
        get_league_standings_func: Function to get league standings
        get_teams_historical_data_func: Function to get historical data
        league_data: Optional pre-fetched league data
        
    Returns:
        Basic decision analysis data structured for visualization
    """
    logger.info(f"Starting simplified decision analysis for league {league_id}")
    
    # Get league standings if not provided
    if league_data is None:
        try:
            league_data = await get_league_standings_func(league_id)
            
            if "error" in league_data:
                return league_data
        except Exception as e:
            logger.error(f"Error getting league standings: {e}")
            return {"error": f"Failed to get league standings: {str(e)}"}
    
    # Extract team IDs (limited to first 5 to avoid timeouts)
    top_teams = league_data["standings"][:min(5, limit)]
    team_ids = [team["team_id"] for team in top_teams]
    logger.info(f"Analyzing {len(team_ids)} teams for decision analysis")
    
    # Get player data (we'll need this for captain analysis)
    try:
        all_players = await api.get_players()
        players_map = {p["id"]: p for p in all_players}
        logger.info(f"Loaded data for {len(players_map)} players")
    except Exception as e:
        logger.error(f"Error loading player data: {e}")
        players_map = {}
    
    # Process results
    gameweeks = list(range(start_gw, end_gw + 1))
    
    # Create a mapping of team info for easier lookup
    team_info = {t["team_id"]: {"name": t["team_name"], "manager": t["manager_name"]} for t in top_teams}
    
    # Get historical data for these teams only (simplified)
    try:
        historical_data = await get_teams_historical_data_func(team_ids, start_gw, end_gw)
        
        if "error" not in historical_data:
            teams_history = historical_data.get("teams_data", {})
            
            # Process bench points from historical data
            bench_points = {}
            for team_id in team_ids:
                bench_points[team_id] = {}
                
                if team_id in teams_history:
                    team_history = teams_history[team_id].get("current", [])
                    
                    for gw in gameweeks:
                        gw_history = next((g for g in team_history if g.get("event") == gw), None)
                        
                        if gw_history:
                            bench_points[team_id][gw] = gw_history.get("points_on_bench", 0)
                        else:
                            bench_points[team_id][gw] = 0
            
            # Calculate bench metrics
            bench_metrics = {}
            for team_id, gw_data in bench_points.items():
                if team_id not in team_info:
                    continue
                    
                total_bench = sum(gw_data.values())
                valid_gws = len(gw_data)
                
                bench_metrics[team_id] = {
                    "team_name": team_info[team_id]["name"],
                    "manager_name": team_info[team_id]["manager"],
                    "total_bench_points": total_bench,
                    "avg_bench_points": round(total_bench / valid_gws, 1) if valid_gws > 0 else 0,
                }
            
            sorted_bench_metrics = sorted(
                bench_metrics.values(),
                key=lambda x: x["total_bench_points"],
                reverse=True
            )
        else:
            logger.error(f"Error in historical data: {historical_data.get('error')}")
            sorted_bench_metrics = []
            
    except Exception as e:
        logger.error(f"Error processing historical data: {e}")
        sorted_bench_metrics = []
    
    # Return simplified decision analysis
    logger.info("Returning simplified decision analysis")
    return {
        "league_info": league_data["league_info"],
        "gameweek_range": {"start": start_gw, "end": end_gw},
        "gameweeks": gameweeks,
        "teams_analyzed": len(team_ids),
        "bench_analysis": {
            "rankings": sorted_bench_metrics
        },
        "status": "simplified",
        "message": "Limited analysis due to performance constraints. Try reducing the number of teams or gameweeks."
    }