"""FPL tools exposed through MCP."""

from .analysis import register_tools as register_analysis_tools
from .fixtures import register_tools as register_fixture_tools
from .gameweeks import register_tools as register_gameweek_tools
from .leagues import register_tools as register_league_tools
from .managers import register_tools as register_manager_tools
from .players import register_tools as register_player_tools
from .team import register_tools as register_team_tools

__all__ = [
    "register_analysis_tools",
    "register_fixture_tools",
    "register_gameweek_tools",
    "register_league_tools",
    "register_manager_tools",
    "register_player_tools",
    "register_team_tools",
]
