# Implementation Plan for FPL MCP Fixture Support

Here's a detailed step-by-step implementation plan to add fixture support to your Fantasy Premier League MCP server, with verification steps using the MCP Inspector. This implementation will include support for blank and double gameweeks.

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

1. **Create the fixtures.py file**
   ```bash
   mkdir -p /Users/rj/Projects/fantasy-pl-mcp/src/fpl_mcp/fpl/resources
   touch /Users/rj/Projects/fantasy-pl-mcp/src/fpl_mcp/fpl/resources/fixtures.py
   ```

2. **Add the fixtures implementation code**
   Open the file in your editor and add the code from the "Fixtures Implementation for FPL MCP" artifact.

3. **Update the fixtures.py to support blank and double gameweeks**
   Add these additional functions to fixtures.py:

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
   ```python
   from .fpl.resources import fixtures
   ```

3. **Add these resource endpoints**
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

### Step 3: Build the Package

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

6. **Test blank gameweeks resource**
   - Click on `fpl://gameweeks/blank`
   - Verify that you see information about blank gameweeks (if any)

7. **Test double gameweeks resource**
   - Click on `fpl://gameweeks/double`
   - Verify that you see information about double gameweeks (if any)

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
     - Player details
     - Fixture difficulty score
     - List of upcoming fixtures with difficulty ratings

3. **Test compare_player_fixtures tool**
   - Click on `compare_player_fixtures`
   - Enter parameters:
     - player1_name: "Haaland"
     - player2_name: "Salah"
     - num_fixtures: 5
   - Execute the tool and verify the response includes:
     - Both players' details
     - Fixture scores for both players
     - Comparative analysis
     - Recommendation on which player has better fixtures

4. **Test get_blank_gameweeks tool**
   - Click on `get_blank_gameweeks`
   - Enter parameter:
     - num_gameweeks: 5
   - Execute the tool and verify the response shows blank gameweeks

5. **Test get_double_gameweeks tool**
   - Click on `get_double_gameweeks`
   - Enter parameter:
     - num_gameweeks: 5
   - Execute the tool and verify the response shows double gameweeks

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

- **API Connection Issues**: Check that your FPL API connection is working by verifying the response from basic API calls
- **Incorrect Parsing**: If fixture data doesn't look right, check the JSON structure of the API response
- **MCP Inspector Connection**: If MCP Inspector can't connect, check that your server is running properly
- **Claude Desktop Integration**: If Claude can't use your tools, check Claude's logs at `~/Library/Logs/Claude/mcp*.log`

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

With this implementation, you'll have comprehensive fixture support in your FPL MCP server, including analysis of blank and double gameweeks, which is essential for FPL strategy and planning.