# FPL MCP Server Enhancement Implementation Plan

## 1. Project Overview

### Current Limitations
The current FPL MCP server has a fundamental limitation: it restricts access to the full player dataset, making comprehensive analysis difficult. The `find_players` tool is limited to returning only 5 players by default, which prevents Claude from performing meaningful analysis across the entire player pool.

### Enhancement Goals
We need to implement three powerful tools that provide:
1. Full player dataset analysis with filtering capabilities
2. Enhanced fixture analysis for players, teams, and positions
3. Comprehensive player comparison with gameweek history

### Architecture Changes
We'll preserve the existing MCP structure while adding new tools that enable full-dataset access and analysis. We'll utilize caching to optimize performance and minimize API calls.

## 2. Files to Review

Start by reviewing these files to understand the existing codebase:

1. `src/fpl_mcp/__main__.py` - Main entry point with existing tools
2. `src/fpl_mcp/fpl/api.py` - API interface for FPL data
3. `src/fpl_mcp/fpl/cache.py` - Caching implementation
4. `src/fpl_mcp/fpl/resources/players.py` - Player data handling
5. `src/fpl_mcp/fpl/resources/fixtures.py` - Fixture data handling
6. `src/fpl_mcp/fpl/tools/comparisons.py` - Existing comparison tools

## 3. Implementation Steps

### Step 1: Implement Position Normalization Utility

Create a new file: `src/fpl_mcp/fpl/utils/position_utils.py`

```python
"""Utilities for normalizing position terms in FPL context."""

from typing import Optional

# Comprehensive position mapping dictionary
POSITION_MAPPINGS = {
    # Standard FPL codes
    "GKP": "GKP", "DEF": "DEF", "MID": "MID", "FWD": "FWD",
    
    # Common variations - singular
    "goalkeeper": "GKP", "goalie": "GKP", "keeper": "GKP",
    "defender": "DEF", "fullback": "DEF", "center-back": "DEF", "cb": "DEF",
    "midfielder": "MID", "mid": "MID", "winger": "MID",
    "forward": "FWD", "striker": "FWD", "attacker": "FWD", "st": "FWD",
    
    # Common variations - plural
    "goalkeepers": "GKP", "goalies": "GKP", "keepers": "GKP",
    "defenders": "DEF", "fullbacks": "DEF", "center-backs": "DEF",
    "midfielders": "MID", "mids": "MID", "wingers": "MID",
    "forwards": "FWD", "strikers": "FWD", "attackers": "FWD"
}

def normalize_position(position_term: Optional[str]) -> Optional[str]:
    """Convert various position terms to standard FPL position codes.
    
    Args:
        position_term: Position term to normalize (can be None)
        
    Returns:
        Normalized FPL position code or None if input is None
    """
    if not position_term:
        return None
        
    # Convert to lowercase for case-insensitive matching
    normalized = position_term.lower().strip()
    
    # Try direct match in mapping (case insensitive)
    for term, code in POSITION_MAPPINGS.items():
        if normalized == term.lower():
            return code
            
    # Try partial matches
    for term, code in POSITION_MAPPINGS.items():
        if normalized in term.lower() or term.lower() in normalized:
            return code
            
    # No match found, return original
    return position_term
```

### Step 2: Implement Enhanced Caching for Player Dataset

Modify `src/fpl_mcp/fpl/cache.py` to add a new function:

```python
# Add to existing cache.py file

async def get_cached_player_data():
    """Get cached complete player dataset with computed fields.
    
    Returns:
        Complete player dataset with additional computed fields
    """
    return await cache.get_or_fetch(
        "complete_player_dataset",
        fetch_func=fetch_and_prepare_all_players,
        ttl=3600  # Refresh hourly
    )

async def fetch_and_prepare_all_players():
    """Fetch all players and add computed fields.
    
    Returns:
        Enhanced player dataset with computed fields
    """
    # Get raw player data from API
    from .api import api
    from .resources.players import get_players_resource
    
    # Fetch complete player dataset with all fields
    all_players = await get_players_resource()
    
    # Add computed fields for each player
    for player in all_players:
        # Calculate value (points per million)
        try:
            points = float(player["points"]) if "points" in player else 0
            price = float(player["price"]) if "price" in player else 0
            player["value"] = round(points / price, 2) if price > 0 else 0
        except (ValueError, TypeError, ZeroDivisionError):
            player["value"] = 0
            
        # Other useful computed fields can be added here
            
    return all_players
```

### Step 3: Implement Enhanced Player Analysis Tool

Add to `src/fpl_mcp/__main__.py`:

```python
from .fpl.utils.position_utils import normalize_position
from collections import Counter

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
    
    # Get cached complete player dataset
    from .fpl.cache import get_cached_player_data
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
            from .fpl.resources.fixtures import get_player_gameweek_history
            
            # Get history for top players (limit)
            player_ids = [p.get("id") for p in filtered_players[:limit]]
            gameweek_data = await get_player_gameweek_history(player_ids, num_gameweeks)
            result["gameweek_data"] = gameweek_data
        except Exception as e:
            logger.error(f"Error fetching gameweek data: {e}")
            result["gameweek_data_error"] = str(e)
    
    return result
```

### Step 4: Implement Player Gameweek History Function

Create or modify `src/fpl_mcp/fpl/resources/fixtures.py` to add:

```python
async def get_player_gameweek_history(player_ids: List[int], num_gameweeks: int = 5) -> Dict[str, Any]:
    """Get recent gameweek history for multiple players.
    
    Args:
        player_ids: List of player IDs to fetch history for
        num_gameweeks: Number of recent gameweeks to include
        
    Returns:
        Dictionary mapping player IDs to their gameweek histories
    """
    # Get current gameweek to determine range
    gameweeks = await api.get_gameweeks()
    current_gameweek = None
    
    for gw in gameweeks:
        if gw.get("is_current"):
            current_gameweek = gw.get("id")
            break
            
    if current_gameweek is None:
        # If no current gameweek found, try to find next gameweek
        for gw in gameweeks:
            if gw.get("is_next"):
                current_gameweek = gw.get("id") - 1
                break
    
    if current_gameweek is None:
        return {"error": "Could not determine current gameweek"}
    
    # Calculate gameweek range
    start_gameweek = max(1, current_gameweek - num_gameweeks + 1)
    gameweek_range = list(range(start_gameweek, current_gameweek + 1))
    
    # Fetch history for each player
    result = {}
    
    for player_id in player_ids:
        try:
            # Get player summary which includes history
            player_summary = await api.get_player_summary(player_id)
            
            if not player_summary or "history" not in player_summary:
                continue
                
            # Filter to requested gameweeks and format
            player_history = []
            
            for entry in player_summary["history"]:
                round_num = entry.get("round")
                if round_num in gameweek_range:
                    player_history.append({
                        "gameweek": round_num,
                        "minutes": entry.get("minutes", 0),
                        "points": entry.get("total_points", 0),
                        "goals": entry.get("goals_scored", 0),
                        "assists": entry.get("assists", 0),
                        "clean_sheets": entry.get("clean_sheets", 0),
                        "bonus": entry.get("bonus", 0),
                        "opponent": await get_team_name_by_id(entry.get("opponent_team")),
                        "was_home": entry.get("was_home", False)
                    })
            
            # Sort by gameweek
            player_history.sort(key=lambda x: x["gameweek"])
            result[player_id] = player_history
            
        except Exception as e:
            logger.error(f"Error fetching history for player {player_id}: {e}")
    
    return {
        "players": result,
        "gameweeks": gameweek_range
    }

async def get_team_name_by_id(team_id: int) -> str:
    """Get team name from team ID.
    
    Args:
        team_id: Team ID
        
    Returns:
        Team name or "Unknown team" if not found
    """
    teams_data = await api.get_teams()
    
    for team in teams_data:
        if team.get("id") == team_id:
            return team.get("name", "Unknown team")
            
    return "Unknown team"
```

### Step 5: Implement Fixture Analysis Tool

Add to `src/fpl_mcp/__main__.py`:

```python
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
    
    # Normalize entity type
    entity_type = entity_type.lower()
    if entity_type not in ["player", "team", "position"]:
        return {"error": f"Invalid entity type: {entity_type}. Must be 'player', 'team', or 'position'"}
    
    # Get current gameweek
    gameweeks = await api.get_gameweeks()
    current_gameweek = None
    
    for gw in gameweeks:
        if gw.get("is_current"):
            current_gameweek = gw.get("id")
            break
            
    if current_gameweek is None:
        # If no current gameweek found, try to find next gameweek
        for gw in gameweeks:
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
            
        player = player_matches[0]
        result["player"] = {
            "id": player["id"],
            "name": player["name"],
            "team": player["team"],
            "position": player["position"]
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
```

### Step 6: Implement Enhanced Player Comparison Tool

Add to `src/fpl_mcp/__main__.py`:

```python
@mcp.tool()
async def compare_players(
    player_names: List[str],
    metrics: List[str] = ["total_points", "form", "goals_scored", "assists", "bonus"],
    include_gameweeks: bool = False,
    num_gameweeks: int = 5
) -> Dict[str, Any]:
    """Compare multiple players across various metrics
    
    Args:
        player_names: List of player names to compare (2-5 players recommended)
        metrics: List of metrics to compare
        include_gameweeks: Whether to include gameweek-by-gameweek comparison
        num_gameweeks: Number of recent gameweeks to include in comparison
        
    Returns:
        Detailed comparison of players across the specified metrics
    """
    logger.info(f"Tool called: compare_players({player_names}, ...)")
    
    if not player_names or len(player_names) < 2:
        return {"error": "Please provide at least two player names to compare"}
    
    # Find all players by name
    players_data = {}
    for name in player_names:
        matches = await players.find_players_by_name(name, limit=1)
        if not matches:
            return {"error": f"No player found matching '{name}'"}
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
                "price": player["price"]
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
            
            # Get gameweek data for each player
            for name, player in players_data.items():
                player_history = await fixtures.get_player_gameweek_history([player["id"]], num_gameweeks)
                if "players" in player_history and player["id"] in player_history["players"]:
                    gameweek_comparison[name] = player_history["players"][player["id"]]
            
            # Only add to result if we have data
            if gameweek_comparison:
                comparison["gameweek_comparison"] = gameweek_comparison
                
                # Add gameweek range for reference
                if "gameweeks" in player_history:
                    comparison["gameweek_range"] = player_history["gameweeks"]
        except Exception as e:
            logger.error(f"Error fetching gameweek comparison: {e}")
            comparison["gameweek_comparison_error"] = str(e)
    
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
    
    comparison["summary"] = {
        "metrics_won": player_wins,
        "overall_best": max(player_wins.items(), key=lambda x: x[1])[0] if player_wins else None
    }
    
    return comparison
```

## 4. Verification Steps

After implementing the changes, perform the following tests:

### Test 1: Enhanced Player Analysis Tool

1. Test with basic filtering:
   ```
   /analyze_players position="midfielders" min_price=8.0 limit=10
   ```
   
2. Test with multiple filters:
   ```
   /analyze_players position="defenders" max_price=5.0 min_points=50 sort_by="value" sort_order="desc"
   ```
   
3. Test with gameweek history:
   ```
   /analyze_players team="Liverpool" include_gameweeks=true num_gameweeks=3
   ```

Verify:
- Position normalization works correctly
- Proper filtering is applied
- Results are sorted as specified
- Summary statistics are accurate
- Gameweek history is included when requested

### Test 2: Fixture Analysis Tool

1. Test player fixture analysis:
   ```
   /analyze_fixtures entity_type="player" entity_name="Salah" num_gameweeks=5
   ```
   
2. Test team fixture analysis:
   ```
   /analyze_fixtures entity_type="team" entity_name="Arsenal" num_gameweeks=5
   ```
   
3. Test position fixture analysis:
   ```
   /analyze_fixtures entity_type="position" entity_name="forwards" num_gameweeks=5
   ```

Verify:
- Correct fixtures are returned
- Difficulty assessment is reasonable
- Blank and double gameweeks are identified
- Position-based analysis provides useful team recommendations

### Test 3: Player Comparison Tool

1. Test comparing two players:
   ```
   /compare_players player_names=["Salah", "De Bruyne"]
   ```
   
2. Test comparing multiple players with gameweek history:
   ```
   /compare_players player_names=["Haaland", "Kane", "Vardy"] include_gameweeks=true
   ```
   
3. Test with custom metrics:
   ```
   /compare_players player_names=["Robertson", "Alexander-Arnold"] metrics=["assists", "clean_sheets", "bonus", "price"]
   ```

Verify:
- Players are found correctly
- Metrics comparison is accurate
- Gameweek history is included when requested
- Best performers are identified correctly

## 5. Logging and Error Handling

1. Log function entry points with parameters
2. Log errors in detail
3. Return clear error messages to Claude
4. Handle edge cases gracefully (player not found, invalid filters, etc.)

## 6. Final Implementation Notes

1. **Environment Setup**:
   - Make sure all imports are correct
   - Ensure dependencies are installed

2. **Important Considerations**:
   - Position normalization is critical for natural language interaction
   - Caching is essential for performance - hourly refresh is reasonable
   - Always return useful summaries alongside detailed data
   - Structure data for easy visualization by Claude

3. **Documentation**:
   - Update docstrings to clearly explain parameters and return values
   - Log any changes to the existing API

This implementation plan provides a clear, step-by-step approach to enhancing the FPL MCP server's capabilities while preserving the existing architecture. The junior engineer should be able to follow these instructions to implement the three main tools and the supporting functions needed for them to work efficiently.