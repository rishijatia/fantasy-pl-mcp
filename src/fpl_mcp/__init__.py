"""Fantasy Premier League Model Context Protocol (MCP) Server."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fpl-mcp")
except PackageNotFoundError:
    # Running from a source tree without installation
    __version__ = "0.0.0"

# Import main components for easy access
from fpl_mcp.__main__ import main
