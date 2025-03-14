# Fantasy Premier League MCP

## Installation

### Installing from PyPI

```bash
pip install fpl-mcp
```

### Installing with extras

```bash
pip install "fpl-mcp[dev]"  # Installs development dependencies
```

## Usage

### Using the Command Line Interface

After installation, you can run the FPL MCP server directly from your command line:

```bash
# Run with default settings
fpl-mcp

# Run with specific port
fpl-mcp --port 8080

# Enable debug mode
fpl-mcp --debug
```

### Python API

You can also use Fantasy PL MCP programmatically in your Python code:

```python
from fpl_mcp import FplMcp

# Create a new server instance
server = FplMcp()

# Start the server
server.start()

# Access FPL data directly
players = server.get_all_players()
teams = server.get_all_teams()

# Stop the server
server.stop()
```

### Claude Desktop Integration

To use with Claude Desktop:

1. Install the package
2. Edit your Claude Desktop configuration file (claude_desktop_config.json)

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

## API Documentation

Detailed API documentation is available at the [project GitHub page](https://github.com/rishijatia/fantasy-pl-mcp).

## License

This project is licensed under the MIT License.
