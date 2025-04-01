# Fantasy Premier League MCP Server

[![PyPI version](https://badge.fury.io/py/fpl-mcp.svg)](https://badge.fury.io/py/fpl-mcp)
[![Package Check](https://github.com/rishijatia/fantasy-pl-mcp/actions/workflows/package-check.yml/badge.svg)](https://github.com/rishijatia/fantasy-pl-mcp/actions/workflows/package-check.yml)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/fpl-mcp)](https://pypi.org/project/fpl-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/fpl-mcp)](https://pepy.tech/project/fpl-mcp)
<a href="https://glama.ai/mcp/servers/2zxsxuxuj9">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/2zxsxuxuj9/badge" />

A Model Context Protocol (MCP) server that provides access to Fantasy Premier League (FPL) data and tools. This server allows you to interact with FPL data in Claude for Desktop and other MCP-compatible clients.

*Demo of the Fantasy Premier League MCP Server in action*

[![Fantasy Premier League MCP Demo](https://img.youtube.com/vi/QfOOOQ_jeMA/0.jpg)](https://youtu.be/QfOOOQ_jeMA)


## Supported Platforms

- Claude Desktop
- Cursor
- Windsurf
- Other MCP Compatible Desktop LLMs

Mobile is currently not supported.

## Features

- **Rich Player Data**: Access comprehensive player statistics from the FPL API
- **Team Information**: Get details about Premier League teams
- **Gameweek Data**: View current and past gameweek information
- **Player Search**: Find players by name or team
- **Player Comparison**: Compare detailed statistics between any two players

## Requirements

- Python 3.10 or higher
- Claude Desktop (for AI integration)

## Installation

### Option 1: Install from PyPI (Recommended)

```bash
pip install fpl-mcp
```

### Option 1b: Install with Development Dependencies

```bash
pip install "fpl-mcp[dev]"
```

### Option 2: Install from GitHub

```bash
pip install git+https://github.com/rishijatia/fantasy-pl-mcp.git
```

### Option 3: Clone and Install Locally

```bash
git clone https://github.com/rishijatia/fantasy-pl-mcp.git
cd fantasy-pl-mcp
pip install -e .
```

## Running the Server

After installation, you have several options to run the server:

### 1. Using the CLI command

```bash
fpl-mcp
```

### 2. Using the Python module

```bash
python -m fpl_mcp
```

### 3. Using with Claude Desktop

Configure Claude Desktop to use the installed package by editing your `claude_desktop_config.json` file:

**Method 1: Using the Python module directly (most reliable)**

```json
{
  "mcpServers": {
    "fantasy-pl": {
      "command": "python",
      "args": ["-m", "fpl_mcp"]
    }
  }
}
```

**Method 2: Using the installed command with full path (if installed with pip)**

```json
{
  "mcpServers": {
    "fantasy-pl": {
      "command": "/full/path/to/your/venv/bin/fpl-mcp"
    }
  }
}
```

Replace `/full/path/to/your/venv/bin/fpl-mcp` with the actual path to the executable. You can find this by running `which fpl-mcp` in your terminal after activating your virtual environment.

> **Note:** Using just `"command": "fpl-mcp"` may result in a `spawn fpl-mcp ENOENT` error since Claude Desktop might not have access to your virtual environment's PATH. Using the full path or the Python module approach helps avoid this issue.

## Usage

### In Claude for Desktop

1. Start Claude for Desktop
2. You should see FPL tools available via the hammer icon
3. Example queries:
   - "Compare Mohamed Salah and Erling Haaland over the last 5 gameweeks"
   - "Find all Arsenal midfielders"
   - "What's the current gameweek status?"
   - "Show me the top 5 forwards by points"

#### Fantasy-PL MCP Usage Instructions

#### Basic Commands:
- Compare players: "Compare [Player1] and [Player2]"
- Find players: "Find players from [Team]" or "Search for [Player Name]"
- Fixture difficulty: "Show upcoming fixtures for [Team]"
- Captain advice: "Who should I captain between [Player1] and [Player2]?"

#### Advanced Features:
- Statistical analysis: "Compare underlying stats for [Player1] and [Player2]"
- Form check: "Show me players in form right now"
- Differential picks: "Suggest differentials under 10% ownership"
- Team optimization: "Rate my team and suggest transfers"

#### Tips:
- Be specific with player names for accurate results
- Include positions when searching (FWD, MID, DEF, GK)
- For best captain advice, ask about form, fixtures, and underlying stats
- Request comparison of specific metrics (xG, shots in box, etc.   

### MCP Inspector for Development

For development and testing:

```bash
# If you have mcp[cli] installed
mcp dev -m fpl_mcp

# Or use npx
npx @modelcontextprotocol/inspector python -m fpl_mcp
```

## Available Resources
- `fpl://static/players` - All player data with comprehensive statistics
- `fpl://static/players/{name}` - Player data by name search
- `fpl://static/teams` - All Premier League teams
- `fpl://static/teams/{name}` - Team data by name search
- `fpl://gameweeks/current` - Current gameweek data
- `fpl://gameweeks/all` - All gameweeks data
- `fpl://fixtures` - All fixtures for the current season
- `fpl://fixtures/gameweek/{gameweek_id}` - Fixtures for a specific gameweek
- `fpl://fixtures/team/{team_name}` - Fixtures for a specific team
- `fpl://players/{player_name}/fixtures` - Upcoming fixtures for a specific player
- `fpl://gameweeks/blank` - Information about upcoming blank gameweeks
- `fpl://gameweeks/double` - Information about upcoming double gameweeks

## Available Tools
- `get_gameweek_status` - Get precise information about current, previous, and next gameweeks
- `analyze_player_fixtures` - Analyze upcoming fixtures for a player with difficulty ratings
- `get_blank_gameweeks` - Get information about upcoming blank gameweeks
- `get_double_gameweeks` - Get information about upcoming double gameweeks
- `analyze_players` - Filter and analyze FPL players based on multiple criteria
- `analyze_fixtures` - Analyze upcoming fixtures for players, teams, or positions
- `compare_players` - Compare multiple players across various metrics
- `check_fpl_authentication` - Check if FPL authentication is working correctly
- `get_my_team` - View your authenticated team (requires authentication)
- `get_team` - View any team with a specific ID (requires authentication)
- `get_manager_info` - Get manager details (requires authentication)

## Prompt Templates
- `player_analysis_prompt` - Create a prompt for analyzing an FPL player in depth
- `transfer_advice_prompt` - Get advice on player transfers based on budget and position
- `team_rating_prompt` - Create a prompt for rating and analyzing an FPL team
- `differential_players_prompt` - Create a prompt for finding differential players with low ownership
- `chip_strategy_prompt` - Create a prompt for chip strategy advice

## Development

### Adding Features

To add new features:

1. Add resource handlers in the appropriate file within `fpl_mcp/fpl/resources/`
2. Add tool handlers in the appropriate file within `fpl_mcp/fpl/tools/`
3. Update the `__main__.py` file to register new resources and tools
4. Test using the MCP Inspector before deploying to Claude for Desktop

## Authentication

To use features requiring authentication (like accessing your team or private leagues), you need to set up your FPL credentials:

```bash
# Run the credential setup tool
fpl-mcp-config setup
```

This interactive tool will:
1. Prompt for your FPL email, password, and team ID
2. Let you choose between storing in config.json or .env file
3. Save credentials securely to ~/.fpl-mcp/

You can test your authentication with:
```bash
fpl-mcp-config test
```

Alternatively, you can manually configure authentication:
1. Create `~/.fpl-mcp/.env` file with:
   ```
   FPL_EMAIL=your_email@example.com
   FPL_PASSWORD=your_password
   FPL_TEAM_ID=your_team_id
   ```
   
2. Or create `~/.fpl-mcp/config.json`:
   ```json
   {
     "email": "your_email@example.com",
     "password": "your_password",
     "team_id": "your_team_id"
   }
   ```

3. Or set environment variables:
   ```bash
   export FPL_EMAIL=your_email@example.com
   export FPL_PASSWORD=your_password
   export FPL_TEAM_ID=your_team_id
   ```

## Limitations

- The FPL API is not officially documented and may change without notice
- Only read operations are currently supported

## Troubleshooting

### Common Issues

#### 1. "spawn fpl-mcp ENOENT" error in Claude Desktop

This occurs because Claude Desktop cannot find the `fpl-mcp` executable in its PATH.

**Solution:** Use one of these approaches:

- Use the full path to the executable in your config file
  ```json
  {
    "mcpServers": {
      "fantasy-pl": {
        "command": "/full/path/to/your/venv/bin/fpl-mcp"
      }
    }
  }
  ```

- Use Python to run the module directly (preferred method)
  ```json
  {
    "mcpServers": {
      "fantasy-pl": {
        "command": "python",
        "args": ["-m", "fpl_mcp"]
      }
    }
  }
  ```

#### 2. Server disconnects immediately

If the server starts but immediately disconnects:

- Check logs at `~/Library/Logs/Claude/mcp*.log` (macOS) or `%APPDATA%\Claude\logs\mcp*.log` (Windows)
- Ensure all dependencies are installed
- Try running the server manually with `python -m fpl_mcp` to see any errors

#### 3. Server not showing in Claude Desktop

If the hammer icon doesn't appear:

- Restart Claude Desktop completely
- Verify your `claude_desktop_config.json` has correct JSON syntax
- Ensure the path to Python or the executable is absolute, not relative

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

For more details, please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file.

## Acknowledgments

- [Fantasy Premier League API](https://fantasy.premierleague.com/api/) for providing the data
- [Model Context Protocol](https://modelcontextprotocol.io/) for the connectivity standard
- [Claude](https://claude.ai/) for the AI assistant capabilities

## Citation

If you use this package in your research or project, please consider citing it:

```bibtex
@software{fpl_mcp,
  author = {Jatia, Rishi and Fantasy PL MCP Contributors},
  title = {Fantasy Premier League MCP Server},
  url = {https://github.com/rishijatia/fantasy-pl-mcp},
  version = {0.1.0},
  year = {2025},
}
```
