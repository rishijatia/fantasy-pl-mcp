# Fantasy Premier League MCP Server

[![PyPI version](https://badge.fury.io/py/fpl-mcp.svg)](https://badge.fury.io/py/fpl-mcp)
[![Package Check](https://github.com/rishijatia/fantasy-pl-mcp/actions/workflows/package-check.yml/badge.svg)](https://github.com/rishijatia/fantasy-pl-mcp/actions/workflows/package-check.yml)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/fpl-mcp)](https://pypi.org/project/fpl-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/fpl-mcp)](https://pepy.tech/project/fpl-mcp)

A Model Context Protocol (MCP) server that provides access to Fantasy Premier League (FPL) data and tools. This server allows you to interact with FPL data in Claude for Desktop and other MCP-compatible clients.

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

### Option 4: Automated Setup for Claude Desktop

The easiest way to set up with Claude Desktop:

```bash
# After cloning the repository
python install_mcp.py
```

This automatically installs the package and configures Claude Desktop.

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
   - "Compare Mohamed Salah and Erling Haaland"
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

## Available Tools

- `compare_players` - Compare detailed statistics between any two players
- `find_players` - Search for players by name or team

## Prompt Templates

- `player_analysis_prompt` - Create a prompt for analyzing an FPL player
- `transfer_advice_prompt` - Get advice on player transfers based on budget and position

## Project Structure

```
fantasy-pl-mcp/
├── src/
│   └── fpl_mcp/                    # Package directory
│       ├── __init__.py             # Package version and imports
│       ├── __main__.py             # Main entry point
│       ├── config.py               # Configuration handling
│       ├── fpl/                    # FPL API implementation
│       │   ├── __init__.py
│       │   ├── api.py              # FPL API client
│       │   ├── cache.py            # Caching logic
│       │   ├── rate_limiter.py     # Rate limiting for API calls
│       │   ├── resources/          # MCP resources
│       │   └── tools/              # MCP tools
│       └── schemas/                # JSON schemas
├── pyproject.toml                  # Modern Python packaging
├── install_mcp.py                  # Claude Desktop installer
└── scripts/                        # Utility scripts
```

## Development

### Adding Features

To add new features:

1. Add resource handlers in the appropriate file within `fpl_mcp/fpl/resources/`
2. Add tool handlers in the appropriate file within `fpl_mcp/fpl/tools/`
3. Update the `__main__.py` file to register new resources and tools
4. Test using the MCP Inspector before deploying to Claude for Desktop

## Limitations

- The FPL API is not officially documented and may change without notice
- Only read operations are currently supported
- Authentication for private leagues is not yet implemented

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
