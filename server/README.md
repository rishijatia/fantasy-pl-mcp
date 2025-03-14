# Fantasy Premier League MCP Server

An MCP (Model Context Protocol) server that provides access to Fantasy Premier League data and tools, allowing LLMs like Claude to analyze FPL assets, compare players, and provide valuable fantasy football insights.

## Features

### Resources

- **`fpl://static/players`** - Get comprehensive data on all FPL players
- **`fpl://static/players/{name}`** - Get data for a specific player by name
- **`fpl://static/teams`** - Get data on all Premier League teams
- **`fpl://static/teams/{name}`** - Get data for a specific team by name
- **`fpl://gameweeks/current`** - Get information about the current gameweek
- **`fpl://gameweeks/all`** - Get information about all gameweeks

### Tools

- **`compare_players`** - Compare two players with detailed statistical analysis
- **`find_players`** - Search for players by name or team

### Prompts

- **`player_analysis_prompt`** - Analyze a player as an FPL asset
- **`transfer_advice_prompt`** - Get transfer recommendations based on budget and position

## Installation

### Prerequisites

- Python 3.8+
- Virtual environment

### Setup

1. Create and activate a virtual environment:

```bash
# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Running the server directly

```bash
./server.py
```

### Testing with MCP Inspector

Install the MCP Inspector and test the server:

```bash
npx @modelcontextprotocol/inspector .venv/bin/python server.py
```

### Using with Claude Desktop

1. Install the server in Claude Desktop:

```bash
mcp install server.py
```

2. For a custom name:

```bash
mcp install server.py --name "Fantasy PL Data"
```

## Development

### Virtual Environment

Use the virtual environment for development:

```bash
# Activate
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Deactivate when done
deactivate
```

### Project Structure

- `server.py` - Main MCP server implementation
- `fpl/` - FPL API client and data processing modules
  - `api.py` - FPL API client with caching
  - `cache.py` - Caching implementation
  - `rate_limiter.py` - Rate limiting for API calls
  - `resources/` - MCP resources implementation
  - `tools/` - MCP tools implementation
- `schemas/` - JSON schemas for FPL API
- `fpl_cache/` - Cache directory for FPL data

## Features in Detail

### Player Comparison Tool

The player comparison tool allows:

- Searching for players by partial name
- Detailed statistical comparison
- Value for money analysis
- Overall recommendations based on statistical performance

### Resource Access with Schema Validation

All data is validated against a JSON schema (generated from the FPL API) to ensure:
- Type safety
- Field validation 
- Change detection
- Comprehensive data access

## Next Steps

Future improvements could include:
- User team management (requires authentication)
- Fixture difficulty analysis
- Price change predictions
- Captain recommendations
- Team optimization tools