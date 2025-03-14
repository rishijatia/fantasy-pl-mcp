# Implementation Plan for FPL MCP Fixture Support

Here's a detailed step-by-step implementation plan to add fixture support to your Fantasy Premier League MCP server, with verification steps using the MCP Inspector. This implementation will include support for blank and double gameweeks.

> **Note for Junior Developers**: This guide follows the existing architecture patterns used throughout the codebase. Pay special attention to type hints, docstrings, error handling approaches, and the separation of API logic from endpoint definitions.

## Pre-Implementation Steps

1. **Backup your project**
   ```bash
   cp -r /Users/rj/Projects/fantasy-pl-mcp /Users/rj/Projects/fantasy-pl-mcp-backup
   ```

2. **Check MCP Inspector installation**
   ```bash
   npx @modelcontextprotocol/inspector --version
   ```
   If not installed, it will be automatically installed when you run it.

## Implementation Steps

### Step 1: Create the Fixtures Module

1. **Open the fixtures.py file**
   The file already exists at `/Users/rj/Projects/fantasy-pl-mcp/src/fpl_mcp/fpl/resources/fixtures.py` but is empty. We'll implement the fixture functionality in this file.
   ```bash
   code /Users/rj/Projects/fantasy-pl-mcp/src/fpl_mcp/fpl/resources/fixtures.py
   ```
   
   > **Note**: Ensure you're using the correct path on your system. The path may be different depending on where you cloned the repository.

2. **Implement the fixtures module**
   Start by adding these imports and setting up the module. This follows the same pattern as other resource modules in the project:

   ```python
   #!/usr/bin/env python3

   import logging
   from typing import List, Dict, Any, Optional, Union

   from ..api import api

   # Set up logging following project conventions
   logger = logging.getLogger("fpl-mcp-server.fixtures")
   ```

3. **Add the core fixtures functionality**
   Implement the main fixtures functions following the existing code style:

   ```python
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
   ```

4. **Add support for blank and double gameweeks**
   Now add these additional functions to support blank and double gameweeks:

   ```python
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
   ```

### Step 2: Update Main File

1. **Update your __main__.py file**
   ```bash
   code /Users/rj/Projects/fantasy-pl-mcp/src/fpl_mcp/__main__.py
   ```

2. **Add the imports at the top of file**
   Look for the section where other resources are imported and add fixtures:
   ```python
   # Import modules that use the mcp variable
   from .fpl.api import api  
   from .fpl.resources import players, teams, gameweeks, fixtures
   from .fpl.tools import comparisons
   ```

3. **Add these resource endpoints**
   Add these resource endpoints after the existing resource registrations:
   ```python
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
   ```

4. **Add these tool endpoints**
   Add these tool endpoints after the existing tool registrations:
   ```python
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
       
       # Find the player
       player_matches = await players.find_players_by_name(player_name)
       if not player_matches:
           return {"error": f"No player found matching '{player_name}'"}
       
       player = player_matches[0]
       analysis = await fixtures.analyze_player_fixtures(player["id"], num_fixtures)
       
       return analysis

   @mcp.tool()
   async def compare_player_fixtures(player1_name: str, player2_name: str, num_fixtures: int = 5) -> Dict[str, Any]:
       """Compare upcoming fixtures for two players and suggest which has better fixtures
       
       Args:
           player1_name: First player's name to search for
           player2_name: Second player's name to search for
           num_fixtures: Number of upcoming fixtures to analyze (default: 5)
       
       Returns:
           Comparative analysis of both players' upcoming fixtures
       """
       logger.info(f"Tool called: compare_player_fixtures({player1_name}, {player2_name}, {num_fixtures})")
       
       # Find both players
       player1_matches = await players.find_players_by_name(player1_name)
       if not player1_matches:
           return {"error": f"No player found matching '{player1_name}'"}
       
       player2_matches = await players.find_players_by_name(player2_name)
       if not player2_matches:
           return {"error": f"No player found matching '{player2_name}'"}
       
       player1 = player1_matches[0]
       player2 = player2_matches[0]
       
       # Get fixture analysis for both players
       player1_analysis = await fixtures.analyze_player_fixtures(player1["id"], num_fixtures)
       player2_analysis = await fixtures.analyze_player_fixtures(player2["id"], num_fixtures)
       
       # Build comparison result
       comparison = {
           "players": {
               player1["name"]: {
                   "team": player1["team"],
                   "position": player1["position"],
                   "price": f"£{player1['price']}m",
                   "fixtures_score": player1_analysis["fixture_analysis"]["difficulty_score"],
                   "fixture_analysis": player1_analysis["fixture_analysis"]["analysis"],
               },
               player2["name"]: {
                   "team": player2["team"],
                   "position": player2["position"],
                   "price": f"£{player2['price']}m",
                   "fixtures_score": player2_analysis["fixture_analysis"]["difficulty_score"],
                   "fixture_analysis": player2_analysis["fixture_analysis"]["analysis"],
               }
           },
           "next_fixtures": {
               player1["name"]: [
                   f"{f['opponent']} ({f['location'][0].upper()}) - Difficulty: {f['difficulty']}"
                   for f in player1_analysis["fixture_analysis"]["fixtures_analyzed"]
               ],
               player2["name"]: [
                   f"{f['opponent']} ({f['location'][0].upper()}) - Difficulty: {f['difficulty']}"
                   for f in player2_analysis["fixture_analysis"]["fixtures_analyzed"]
               ]
           }
       }
       
       # Add recommendation
       score1 = player1_analysis["fixture_analysis"]["difficulty_score"]
       score2 = player2_analysis["fixture_analysis"]["difficulty_score"]
       
       if abs(score1 - score2) < 0.5:
           comparison["recommendation"] = f"Both players have similar fixture difficulty"
       elif score1 > score2:
           comparison["recommendation"] = f"{player1['name']} has better upcoming fixtures"
       else:
           comparison["recommendation"] = f"{player2['name']} has better upcoming fixtures"
       
       return comparison

   @mcp.tool()
   async def get_blank_gameweeks(num_gameweeks: int = 5) -> Dict[str, Any]:
       """Get information about upcoming blank gameweeks where teams don't have fixtures
       
       Args:
           num_gameweeks: Number of upcoming gameweeks to check (default: 5)
       
       Returns:
           Information about blank gameweeks and affected teams
       """
       logger.info(f"Tool called: get_blank_gameweeks({num_gameweeks})")
       blank_gameweeks = await fixtures.get_blank_gameweeks(num_gameweeks)
       
       if not blank_gameweeks:
           return {
               "blank_gameweeks": [],
               "summary": "No blank gameweeks found in the next {num_gameweeks} gameweeks"
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
   ```

### Step 3: Verify Code Consistency

1. **Check code formatting**
   Ensure your code follows the same formatting style as the rest of the project:
   
   - 4-space indentation (not tabs)
   - Descriptive variable names
   - Type hints for all functions
   - Docstrings for all functions
   - Consistent error handling with informative log messages
   - Appropriate use of async/await

2. **Verify error handling**
   Make sure your code properly handles potential errors such as:
   
   - API connection failures
   - Missing or invalid data
   - Empty results
   - Type mismatches

3. **Check imports**
   Ensure all necessary imports are included and unnecessary ones are removed.

### Step 4: Build the Package

1. **Create a distributable package**
   ```bash
   cd /Users/rj/Projects/fantasy-pl-mcp
   uv build
   ```

## Verification Steps Using MCP Inspector

### Step 1: Run the MCP Inspector

1. **Launch the MCP Inspector with your server**
   ```bash
   cd /Users/rj/Projects/fantasy-pl-mcp
   npx @modelcontextprotocol/inspector uv run src/fpl_mcp/__main__.py
   ```
   
   > **Note**: The Inspector should launch in your default web browser. If it doesn't, you can manually open http://localhost:3000/ in your browser.

2. **Wait for the server to initialize**
   - MCP Inspector should open in your browser
   - Wait until you see "Server connected" in the Inspector

### Step 2: Verify Resources

1. **Check fixture resources**
   - Click on the "Resources" tab in the Inspector
   - You should see:
     - `fpl://fixtures`
     - `fpl://fixtures/gameweek/{gameweek_id}`
     - `fpl://fixtures/team/{team_name}`
     - `fpl://players/{player_name}/fixtures`
     - `fpl://gameweeks/blank`
     - `fpl://gameweeks/double`

2. **Test all fixtures resource**
   - Click on `fpl://fixtures`
   - Check that it returns a list of fixtures with proper formatting

3. **Test gameweek fixtures resource**
   - Click on `fpl://fixtures/gameweek/{gameweek_id}`
   - Enter a valid gameweek ID (e.g., the current gameweek)
   - Verify fixtures for that gameweek are shown

4. **Test team fixtures resource**
   - Click on `fpl://fixtures/team/{team_name}`
   - Enter "Arsenal" or another team name
   - Verify that you see fixtures for that team

5. **Test player fixtures resource**
   - Click on `fpl://players/{player_name}/fixtures`
   - Enter "Haaland" or another player name
   - Verify that you see fixtures for that player
   - Check that the output includes player information and a list of upcoming fixtures

6. **Test blank gameweeks resource**
   - Click on `fpl://gameweeks/blank`
   - Verify that you see information about blank gameweeks (if any)
   - Check that the structure includes gameweek information and affected teams

7. **Test double gameweeks resource**
   - Click on `fpl://gameweeks/double`
   - Verify that you see information about double gameweeks (if any)
   - Check that the structure includes gameweek information and affected teams

### Step 3: Verify Tools

1. **Check fixture tools**
   - Click on the "Tools" tab in the Inspector
   - You should see:
     - `analyze_player_fixtures`
     - `compare_player_fixtures`
     - `get_blank_gameweeks`
     - `get_double_gameweeks`

2. **Test analyze_player_fixtures tool**
   - Click on `analyze_player_fixtures`
   - Enter parameters:
     - player_name: "Haaland" (or another player)
     - num_fixtures: 5
   - Execute the tool and verify the response includes:
     - Player details (name, team, position)
     - Fixture difficulty score (1-10 scale)
     - Written analysis of fixture difficulty
     - List of upcoming fixtures with difficulty ratings
     - Home/away percentage
   - Verify the difficulty ratings match what you'd expect based on opponent strength

3. **Test compare_player_fixtures tool**
   - Click on `compare_player_fixtures`
   - Enter parameters:
     - player1_name: "Haaland"
     - player2_name: "Salah"
     - num_fixtures: 5
   - Execute the tool and verify the response includes:
     - Both players' details (name, team, position, price)
     - Fixture scores for both players (1-10 scale)
     - Comparative analysis of their fixtures
     - A clear recommendation on which player has better fixtures
     - Upcoming fixture details for both players

4. **Test get_blank_gameweeks tool**
   - Click on `get_blank_gameweeks`
   - Enter parameter:
     - num_gameweeks: 5
   - Execute the tool and verify the response shows blank gameweeks
   - Check that the response includes:
     - A list of blank gameweeks with gameweek numbers/names
     - Teams affected by each blank gameweek
     - A summary of findings
   - If no blank gameweeks are found, verify the response indicates this clearly

5. **Test get_double_gameweeks tool**
   - Click on `get_double_gameweeks`
   - Enter parameter:
     - num_gameweeks: 5
   - Execute the tool and verify the response shows double gameweeks
   - Check that the response includes:
     - A list of double gameweeks with gameweek numbers/names
     - Teams with multiple fixtures in each double gameweek
     - Number of fixtures per team
     - A summary of findings
   - If no double gameweeks are found, verify the response indicates this clearly

## Integration with Claude Desktop

### Step 1: Update Configuration

1. **Update Claude Desktop configuration**
   ```bash
   code ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

2. **Add or update your server configuration**
   ```json
   {
     "mcpServers": {
       "fpl": {
         "command": "uv",
         "args": [
           "--directory",
           "/Users/rj/Projects/fantasy-pl-mcp",
           "run",
           "src/fpl_mcp/__main__.py"
         ]
       }
     }
   }
   ```

### Step 2: Test with Claude

1. **Restart Claude Desktop**

2. **Test fixture queries like:**
   - "What are Arsenal's next 5 fixtures?"
   - "Does Haaland have good fixtures coming up?"
   - "Compare Salah and Son's upcoming fixtures"
   - "Are there any blank gameweeks coming up?"
   - "Which teams have double gameweeks in the next 5 gameweeks?"
   - "Which midfielders have the best fixtures in the next 3 gameweeks?"

## Troubleshooting

### Common Issues and Solutions

#### API-Related Issues
- **API Connection Issues**: 
  - Check that your FPL API connection is working by verifying the response from basic API calls
  - Look for error messages in the logs
  - Test API endpoints directly using httpx in a Python script to isolate the issue
  - Verify rate limiting isn't causing problems

#### Data-Related Issues
- **Incorrect Parsing**: 
  - If fixture data doesn't look right, check the JSON structure of the API response
  - Use print statements or logging to debug the structure
  - Verify team and player mappings are working correctly
  - Check for unexpected null values in the API response

#### Integration Issues
- **MCP Inspector Connection**: 
  - If MCP Inspector can't connect, check that your server is running properly
  - Verify the correct ports are being used
  - Check for any error messages in the terminal where you ran the server
  - Restart the Inspector and server if needed

#### Claude Desktop Issues
- **Claude Desktop Integration**: 
  - If Claude can't use your tools, check Claude's logs at `~/Library/Logs/Claude/mcp*.log`
  - Verify the path in `claude_desktop_config.json` is correct
  - Ensure permissions are set correctly
  - Try reinstalling the server with a fresh configuration

### Debugging Tips

1. **Use logging extensively**: Add debug log statements to track the flow of execution
2. **Check API responses**: Print raw API responses to understand their structure
3. **Test incrementally**: Test each function in isolation before testing the whole system
4. **Verify data types**: Ensure you're handling expected data types correctly

## Blank and Double Gameweek Support

The implementation specifically supports blank and double gameweeks through:

1. **Detection**: The `get_blank_gameweeks` and `get_double_gameweeks` functions analyze the fixture schedule to identify:
   - Gameweeks where teams don't have fixtures (blank)
   - Gameweeks where teams play multiple times (double)

2. **Resources**: Dedicated resources for accessing this information:
   - `fpl://gameweeks/blank` 
   - `fpl://gameweeks/double`

3. **Tools**: Specialized tools for querying blank and double gameweeks:
   - `get_blank_gameweeks` tool
   - `get_double_gameweeks` tool

This allows Claude to answer questions like:
- "Are there any blank gameweeks coming up?"
- "Which teams have double gameweeks in the next 5 gameweeks?"
- "Should I use my Bench Boost chip in the upcoming double gameweek?"
- "Which Arsenal players might be affected by blank gameweek 29?"
- "Does Haaland have difficult fixtures coming up?"
- "Compare Kane and Salah's upcoming fixtures - who has the easier run?"
- "Which midfielders have the best fixtures in the next 3 gameweeks?"
- "Is gameweek 26 likely to be a good time to use my Free Hit chip?"

## Final Code Quality Checklist

Before submitting your implementation, review these points:

- [ ] All function signatures include proper type hints
- [ ] All functions have descriptive docstrings explaining parameters and return values
- [ ] Error handling is consistent with the rest of the codebase
- [ ] Logging follows project conventions (using the logger, appropriate log levels)
- [ ] Variable naming is clear and consistent
- [ ] Code is properly formatted with 4-space indentation
- [ ] No unnecessary imports or commented out code
- [ ] All tools and resources follow the FPL MCP naming conventions
- [ ] API interactions properly handle potential errors
- [ ] All functions and endpoints have been tested with the MCP Inspector

With this implementation, you'll have comprehensive fixture support in your FPL MCP server, including analysis of blank and double gameweeks, which is essential for FPL strategy and planning.