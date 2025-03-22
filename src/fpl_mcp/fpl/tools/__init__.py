"""FPL tools exposed through MCP."""

from .team import register_tools as register_team_tools
from .managers import register_tools as register_manager_tools

__all__ = ["register_team_tools", "register_manager_tools"]