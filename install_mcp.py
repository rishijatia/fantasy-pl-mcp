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