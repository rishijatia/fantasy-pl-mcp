# Fantasy Premier League MCP Server - Distribution and Open Source Improvements

## Overview of Required Changes

After analyzing your Fantasy Premier League MCP server, I've identified specific changes to improve its distribution and open source hygiene. Here's a detailed plan of the improvements needed:

## 1. Project Structure Reorganization

The current structure has some inconsistencies that should be addressed:

```
fantasy-pl-mcp/
├── server/                          # Should be renamed to 'fpl_mcp'
│   ├── server.py                    # Should be moved to fpl_mcp/__main__.py
│   ├── config.py                    # Move to fpl_mcp/config.py
│   ├── fpl/                         # Move to fpl_mcp/fpl/
│   ├── schemas/                     # Move to fpl_mcp/schemas/
│   └── requirements.txt             # Should be removed (use setup.py instead)
├── README.md
├── LICENSE
├── setup.py                         # Needs updating
├── CONTRIBUTING.md
├── install.sh, install.bat          # Can be simplified or removed
└── scripts/                         # Keep as is
```

Recommended new structure:

```
fantasy-pl-mcp/
├── src/
│   └── fpl_mcp/                     # Package directory
│       ├── __init__.py              # Package version and imports
│       ├── __main__.py              # Main entry point (current server.py)
│       ├── config.py                # Configuration handling
│       ├── fpl/                     # FPL API implementation
│       │   ├── __init__.py
│       │   ├── api.py
│       │   ├── cache.py
│       │   ├── rate_limiter.py
│       │   ├── resources/
│       │   └── tools/
│       └── schemas/                 # JSON schemas
├── README.md                        # Updated installation instructions
├── LICENSE                          # MIT License
├── CONTRIBUTING.md                  # Contribution guidelines
├── pyproject.toml                   # Modern Python packaging (replace setup.py)
└── scripts/                         # Utility scripts
```

## 2. Packaging Improvements

### Replace setup.py with pyproject.toml

Create a `pyproject.toml` file:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "fpl-mcp"
version = "0.1.0"
description = "An MCP server for Fantasy Premier League data"
readme = "README.md"
authors = [
    {name = "Your Name", email = "your.email@example.com"},
]
license = {text = "MIT"}
classifiers = [
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
]
requires-python = ">=3.8"
dependencies = [
    "mcp>=1.2.0",
    "httpx>=0.24.0",
    "python-dotenv",
    "diskcache",
    "jsonschema",
]

[project.scripts]
fpl-mcp = "fpl_mcp.__main__:main"

[project.urls]
Homepage = "https://github.com/yourusername/fantasy-pl-mcp"
Issues = "https://github.com/yourusername/fantasy-pl-mcp/issues"
```

## 3. Code Changes

### 1. Create a proper `__init__.py` in the `fpl_mcp` package:

```python
"""Fantasy Premier League Model Context Protocol (MCP) Server."""

__version__ = "0.1.0"

# Import main components for easy access
from fpl_mcp.__main__ import main
```

### 2. Move and update server.py to __main__.py:

Modify imports to use relative imports within the package:

```python
# Change from:
from fpl.api import api
# To:
from .fpl.api import api
```

Add proper entry point for both direct execution and pip installation:

```python
def main():
    """Run the Fantasy Premier League MCP server."""
    logger.info("Starting Fantasy Premier League MCP Server")
    mcp.run()

if __name__ == "__main__":
    main()
```

### 3. Update config.py for better path handling:

```python
import os
import pathlib
from importlib import resources
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Base paths - handle both development and installed package
try:
    # When installed as package
    with resources.path(__package__, "__init__.py") as p:
        BASE_DIR = p.parent
except (ImportError, ModuleNotFoundError):
    # During development
    BASE_DIR = pathlib.Path(__file__).parent.absolute()

SCHEMAS_DIR = BASE_DIR / "schemas"
# Use user cache dir for persistent cache
CACHE_DIR = pathlib.Path(os.getenv("FPL_CACHE_DIR", 
                                 str(pathlib.Path.home() / ".cache" / "fpl-mcp")))
```

### 4. Fix import paths in all modules:

Update all import statements to use package-relative imports:

```python
# Change from:
from fpl.cache import cache
# To:
from .cache import cache

# Change from:
from config import FPL_API_BASE_URL
# To:
from ..config import FPL_API_BASE_URL
```

## 4. Documentation Improvements

### Update README.md

The README should have more straightforward installation instructions:

```markdown
## Installation

### Option 1: Install from PyPI (Recommended)

```bash
pip install fpl-mcp
```

### Option 2: Install from GitHub

```bash
pip install git+https://github.com/yourusername/fantasy-pl-mcp.git
```

### Option 3: Clone and Install Locally

```bash
git clone https://github.com/yourusername/fantasy-pl-mcp.git
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

Configure Claude Desktop to use the installed package:

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

Or if you installed it with pip:

```json
{
  "mcpServers": {
    "fantasy-pl": {
      "command": "fpl-mcp"
    }
  }
}
```
```

### Create a CHANGELOG.md

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - YYYY-MM-DD

### Added
- Initial release
- FPL data access through MCP resources
- Player comparison tools
- Team and player search functionality
```

## 5. GitHub-Specific Files

### Create a simple GitHub CI workflow

Create `.github/workflows/python-test.yml`:

```yaml
name: Python Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10']

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest
        pip install -e .
    - name: Test with pytest
      run: |
        pytest
```

### Update .gitignore

Ensure `.gitignore` includes Python-specific entries:

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# Cache
fpl_cache/
.cache/

# Environment variables
.env

# IDE specific files
.idea/
.vscode/
*.swp
*.swo
```

## 6. Specific Changes for Easy Claude Desktop Integration

Create a new user-friendly installer script that simplifies Claude Desktop integration:

```python
#!/usr/bin/env python3
"""
FPL MCP Server Installer for Claude Desktop
"""

import os
import json
import sys
import subprocess
from pathlib import Path

def main():
    print("Fantasy Premier League MCP Server - Claude Desktop Installer")
    print("===================================================")
    
    # Install the package if not already installed
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "."])
        print("✅ Package installed successfully")
    except subprocess.CalledProcessError:
        print("❌ Failed to install package")
        return
    
    # Find the Claude Desktop config location
    if sys.platform == "darwin":  # macOS
        config_dir = Path.home() / "Library" / "Application Support" / "Claude"
    elif sys.platform == "win32":  # Windows
        config_dir = Path(os.getenv("APPDATA")) / "Claude"
    else:
        print("❌ Unsupported platform. Please configure Claude Desktop manually.")
        return
    
    config_file = config_dir / "claude_desktop_config.json"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Load existing config or create new one
    if config_file.exists():
        with open(config_file, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}
    else:
        config = {}
    
    # Ensure mcpServers key exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Add our server
    config["mcpServers"]["fantasy-pl"] = {
        "command": "python",
        "args": ["-m", "fpl_mcp"]
    }
    
    # Save the config
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    
    print("✅ Claude Desktop configuration updated")
    print("\nSetup Complete! 🎉")
    print("To use the FPL MCP server:")
    print("1. Start Claude Desktop")
    print("2. Look for the FPL tools in the tool list (hammer icon)")
    print("\nExample queries:")
    print("- Compare Mohamed Salah and Erling Haaland")
    print("- Find all Arsenal midfielders")

if __name__ == "__main__":
    main()
```

## Implementation Steps Summary

Here's a summary of the steps you need to take to implement these changes:

1. Reorganize your project structure to follow the standard package layout
2. Convert `setup.py` to `pyproject.toml` for modern packaging
3. Update import statements to use package-relative imports throughout
4. Create a proper package `__init__.py` with version information
5. Move `server.py` to `__main__.py` and ensure it has a clean entry point
6. Update `config.py` to handle paths correctly in both development and installed modes
7. Create or update GitHub workflow files for CI
8. Improve documentation with clearer installation and usage instructions
9. Create a simple installer script for Claude Desktop integration

These changes will make your Fantasy Premier League MCP server more distributable, easier to maintain, and simpler for users to install and use.

## Claude Desktop Configuration

After implementing these changes, users can easily configure Claude Desktop with the following entry in `claude_desktop_config.json`:

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

This configuration assumes the package is installed via pip. If the user installed via the installer script, this configuration will be automatically created.