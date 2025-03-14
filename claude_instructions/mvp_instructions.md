# Fantasy Premier League MCP Server Implementation Plan (Revised)

## Project Overview

This implementation plan outlines the development of a Model Context Protocol (MCP) server for Fantasy Premier League (FPL) data. The MVP will focus on exposing key resources from the bootstrap-static endpoint with an emphasis on comprehensive player statistics.

## Project Structure

```
fantasy-pl-mcp/
├── server.py                  # Main MCP server implementation
├── fpl/
│   ├── __init__.py
│   ├── api.py                 # FPL API client
│   ├── cache.py               # Caching logic
│   ├── resources/             # MCP resources
│   │   ├── __init__.py
│   │   ├── players.py
│   │   ├── teams.py
│   │   └── gameweeks.py
│   └── tools/                 # MCP tools
│       ├── __init__.py
│       └── comparisons.py
├── config.py                  # Configuration settings
├── schemas/
│   └── static_schema.json     # JSON schema for bootstrap-static
├── fpl_cache/                 # Cache directory
└── requirements.txt           # Dependencies
```

## Core Dependencies

```
mcp>=1.2.0         # MCP Python SDK
httpx>=0.24.0      # Async HTTP client
python-dotenv      # Environment variable management
diskcache          # Disk-based cache
jsonschema         # JSON schema validation
```

## Key Architectural Decisions

### 1. Caching Strategy

Implement a disk-based caching system with TTL (Time To Live) to:
- Reduce load on the FPL API
- Improve response times
- Handle temporary FPL API outages

```python
# Pseudocode for caching approach
class FPLCache:
    def __init__(self, cache_dir="fpl_cache", default_ttl=3600):
        self.cache = diskcache.Cache(cache_dir)
        self.default_ttl = default_ttl
    
    async def get_or_fetch(self, key, fetch_func, ttl=None):
        if key in self.cache and not self._is_expired(key):
            return self.cache[key]
        
        data = await fetch_func()
        self.cache.set(key, data, expire=ttl or self.default_ttl)
        return data
```

### 2. Schema Validation

Use the provided JSON schema to validate API responses and ensure correct data parsing:

```python
# Pseudocode for schema validation
import json
import jsonschema

class SchemaValidator:
    def __init__(self, schema_path):
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)
    
    def validate(self, data):
        """Validate data against schema"""
        try:
            jsonschema.validate(instance=data, schema=self.schema['schema'])
            return True, None
        except jsonschema.exceptions.ValidationError as e:
            return False, str(e)
```

### 3. Rate Limiting

Implement a simple rate limiter to prevent excessive requests to the FPL API:

```python
# Pseudocode for rate limiting
class RateLimiter:
    def __init__(self, max_requests=20, per_seconds=60):
        self.request_times = []
        self.max_requests = max_requests
        self.time_window = per_seconds
    
    async def acquire(self):
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < self.time_window]
        
        if len(self.request_times) >= self.max_requests:
            wait_time = self.time_window - (now - self.request_times[0])
            await asyncio.sleep(max(0, wait_time))
            return await self.acquire()
        
        self.request_times.append(time.time())
        return True
```

### 4. Error Handling

Implement robust error handling to account for:
- FPL API downtime
- Unexpected data format changes
- MCP protocol errors

## Implementation Plan

### Phase 1: Core Infrastructure (2 days)

1. Set up project structure and dependencies
2. Implement FPL API client with caching and rate limiting
3. Create basic MCP server structure
4. Set up schema validation using `schemas/static_schema.json`

### Phase 2: Resource Implementation (3 days)

1. Implement `fpl://static/players` resource
   - Use schema to ensure all player fields are correctly parsed
   - Include all available player stats from bootstrap-static
   - Format data for readability
   - Add filtering capabilities

2. Implement `fpl://static/teams` resource
   - Include team details and strength ratings
   - Format for readability

3. Implement `fpl://gameweeks/current` resource
   - Show deadline, status, and key stats
   - Add references to most captained/transferred players

### Phase 3: Tool Implementation (2 days)

1. Implement player comparison tool
   - Support comparing two players by name or ID
   - Include detailed stat comparison
   - Calculate difference metrics
   - Support fuzzy name matching

### Phase 4: Prompt Implementation (1 day)

1. Implement player analysis prompt template
   - Create structured format for player analysis
   - Include form, fixtures, and value considerations

### Phase 5: Testing and Documentation (2 days)

1. Test with MCP Inspector
2. Create documentation
3. Deploy and test with Claude Desktop

## Implementation Details

### FPL API Client with Schema Validation

```python
# api.py
import httpx
import asyncio
import json
import jsonschema
from .cache import FPLCache
from .rate_limiter import RateLimiter

class FPLAPI:
    BASE_URL = "https://fantasy.premierleague.com/api"
    
    def __init__(self, schema_path="schemas/static_schema.json"):
        self.cache = FPLCache()
        self.rate_limiter = RateLimiter()
        self.headers = {
            "User-Agent": "Fantasy-PL-MCP/0.1.0"
        }
        
        # Load schema for bootstrap-static
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)
    
    async def get_bootstrap_static(self):
        """Get main FPL static data"""
        await self.rate_limiter.acquire()
        
        async def fetch():
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/bootstrap-static/",
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                
                # Validate against schema
                try:
                    jsonschema.validate(instance=data, schema=self.schema['schema'])
                except jsonschema.exceptions.ValidationError as e:
                    print(f"Warning: Schema validation failed: {e}")
                    # Continue despite validation error, but log it
                
                return data
        
        return await self.cache.get_or_fetch("bootstrap_static", fetch, ttl=3600)  # 1 hour TTL
```

### Players Resource with Schema-Aware Parsing

```python
# resources/players.py
async def get_players_resource():
    """Format player data for the MCP resource"""
    data = await fpl_api.get_bootstrap_static()
    
    # Create team and position lookup maps
    team_map = {t["id"]: t for t in data["teams"]}
    position_map = {p["id"]: p for p in data["element_types"]}
    
    # Format player data
    players = []
    for player in data["elements"]:
        # Extract team and position info
        team = team_map.get(player["team"], {})
        position = position_map.get(player["element_type"], {})
        
        # Build comprehensive player object with all available stats
        # Schema ensures we know exactly what fields are available
        player_data = {
            "id": player["id"],
            "name": f"{player['first_name']} {player['second_name']}",
            "web_name": player["web_name"],
            "team": team.get("name", "Unknown"),
            "team_short": team.get("short_name", "UNK"),
            "position": position.get("singular_name_short", "UNK"),
            "price": player["now_cost"] / 10.0,
            "form": player["form"],
            "points": player["total_points"],
            "points_per_game": player["points_per_game"],
            
            # Playing time
            "minutes": player["minutes"],
            "starts": player["starts"],
            "starts_per_90": player["starts_per_90"],
            
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
            
            # Expected stats
            "expected_goals": player["expected_goals"],
            "expected_assists": player["expected_assists"],
            "expected_goal_involvements": player["expected_goal_involvements"],
            "expected_goals_conceded": player["expected_goals_conceded"],
            "expected_goals_per_90": player["expected_goals_per_90"],
            "expected_assists_per_90": player["expected_assists_per_90"],
            
            # Ownership & transfers
            "selected_by_percent": player["selected_by_percent"],
            "transfers_in": player["transfers_in"],
            "transfers_in_event": player["transfers_in_event"],
            "transfers_out": player["transfers_out"],
            "transfers_out_event": player["transfers_out_event"],
            
            # Price changes
            "cost_change_event": player["cost_change_event"] / 10.0,
            "cost_change_start": player["cost_change_start"] / 10.0,
            
            # Status info
            "status": player["status"],
            "news": player["news"],
            "chance_of_playing_next_round": player["chance_of_playing_next_round"],
            "chance_of_playing_this_round": player["chance_of_playing_this_round"],
            
            # Ranks (for comparison)
            "form_rank": player["form_rank"],
            "form_rank_type": player["form_rank_type"],
            "points_per_game_rank": player["points_per_game_rank"],
            "points_per_game_rank_type": player["points_per_game_rank_type"],
            "selected_rank": player["selected_rank"],
            "selected_rank_type": player["selected_rank_type"]
        }
        
        players.append(player_data)
    
    return players
```

### MCP Server Implementation

```python
# server.py
from mcp.server.fastmcp import FastMCP
from fpl.api import FPLAPI
from fpl.resources import players, teams, gameweeks
from fpl.tools import comparisons

# Initialize API client with schema
fpl_api = FPLAPI(schema_path="schemas/static_schema.json")

# Create MCP server
mcp = FastMCP("FPL Data Server")

# Register resources
@mcp.resource("fpl://static/players")
async def get_all_players() -> str:
    """Get a formatted list of all players with comprehensive statistics"""
    players_data = await players.get_players_resource()
    return json.dumps(players_data, indent=2)

@mcp.resource("fpl://static/teams")
async def get_all_teams() -> str:
    """Get a formatted list of all Premier League teams with strength ratings"""
    teams_data = await teams.get_teams_resource()
    return json.dumps(teams_data, indent=2)

@mcp.resource("fpl://gameweeks/current")
async def get_current_gameweek() -> str:
    """Get information about the current gameweek"""
    gameweek_data = await gameweeks.get_current_gameweek_resource()
    return json.dumps(gameweek_data, indent=2)

# Register tools
@mcp.tool()
async def compare_players(player1_name: str, player2_name: str) -> str:
    """Compare two players by searching their names and showing detailed statistical comparison
    
    Args:
        player1_name: First player's name or partial name to search
        player2_name: Second player's name or partial name to search
    """
    comparison = await comparisons.compare_players_by_name(player1_name, player2_name)
    return json.dumps(comparison, indent=2)

# Register prompts
@mcp.prompt()
def player_analysis_prompt(player_name: str) -> list:
    """Create a prompt for analyzing an FPL player"""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"Please analyze {player_name} as an FPL asset. I want to understand:\n"
                        f"1. Current form and performance\n"
                        f"2. Upcoming fixtures and their difficulty\n"
                        f"3. Value for money compared to similar players\n"
                        f"4. Whether I should consider buying, selling, or holding this player"
            }
        }
    ]

# Run the server
if __name__ == "__main__":
    mcp.run(transport='stdio')
```

## Benefits of Using Schema Validation

Using `schemas/static_schema.json` for parsing offers several advantages:

1. **Type Safety**: Ensures data matches expected types (strings, integers, etc.)
2. **Field Validation**: Confirms all required fields are present
3. **Change Detection**: Identifies when the API structure changes
4. **Self-Documentation**: Provides reference for available fields and their types
5. **Error Prevention**: Catches parsing errors early in the process

The schema allows us to handle the extensive player data with confidence that we're extracting all available fields correctly, which is particularly important for the detailed player comparison tool.

## Testing Plan

1. **Unit Testing**:
   - Test schema validation
   - Test cache implementation
   - Test rate limiter logic
   - Test API client error handling

2. **Integration Testing**:
   - Test with MCP Inspector
   - Verify resource/tool functionality

3. **Manual Testing**:
   - Connect to Claude Desktop
   - Test resource access
   - Test player comparison functionality
   - Test prompt templates

## Next Steps After MVP

1. Add fixtures resource for upcoming matches
2. Implement team analysis tool
3. Add transfer suggestion capability
4. Implement captain recommendation
5. Add mini-league analysis (requires authentication)

This implementation plan provides a clear roadmap for building the FPL MCP server with a focus on the most valuable resources while maintaining comprehensive player statistics for detailed comparisons, all with proper schema validation for reliable data handling.