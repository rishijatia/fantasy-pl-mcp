"""FPL tools exposed through MCP."""

from .team import register_tools as register_team_tools
from .managers import register_tools as register_manager_tools
from .leagues import register_tools as register_league_tools
from .players import register_tools as register_player_tools

__all__ = ["register_team_tools", "register_manager_tools", "register_league_tools", "register_player_tools"]