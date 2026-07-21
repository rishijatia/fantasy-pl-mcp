"""Tests for analyze_players/compare_players defaults against the formatted
player shape produced by fpl/resources/players.py."""

from unittest.mock import AsyncMock, patch

from fpl_mcp.fpl.tools import analysis


class _CaptureMCP:
    """Minimal stand-in for FastMCP that records registered tool functions."""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def _make_player(pid, points):
    return {
        "id": pid,
        "name": f"Player {pid}",
        "team": "Arsenal",
        "team_short": "ARS",
        "position": "MID",
        "price": 8.0,
        "form": "5.0",
        "points": points,
        "selected_by_percent": "10.0",
        "status": "a",
    }


def _get_tools():
    capture = _CaptureMCP()
    analysis.register_tools(capture)
    return capture.tools


async def test_analyze_players_default_sort_is_descending_points():
    tools = _get_tools()
    fake_players = [_make_player(pid, points) for pid, points in ((1, 50), (2, 120), (3, 80))]

    with patch(
        "fpl_mcp.fpl.tools.analysis.get_cached_player_data",
        new_callable=AsyncMock,
        return_value=fake_players,
    ):
        result = await tools["analyze_players"]()

    returned_points = [p["points"] for p in result["players"]]
    assert returned_points == [120, 80, 50]


async def test_analyze_players_accepts_bootstrap_alias_for_sort_by():
    tools = _get_tools()
    fake_players = [_make_player(pid, points) for pid, points in ((1, 10), (2, 30), (3, 20))]

    with patch(
        "fpl_mcp.fpl.tools.analysis.get_cached_player_data",
        new_callable=AsyncMock,
        return_value=fake_players,
    ):
        result = await tools["analyze_players"](sort_by="total_points")

    returned_points = [p["points"] for p in result["players"]]
    assert returned_points == [30, 20, 10]


async def test_compare_players_default_metrics_exist_on_formatted_players():
    tools = _get_tools()
    alice = dict(_make_player(1, 100), name="Alice", goals=12, assists=5, bonus=8, news="")
    bob = dict(_make_player(2, 90), name="Bob", goals=9, assists=11, bonus=6, news="")

    async def fake_find(name, limit=3):
        return [alice] if name == "Alice" else [bob]

    with patch(
        "fpl_mcp.fpl.tools.analysis.players.find_players_by_name",
        side_effect=fake_find,
    ):
        result = await tools["compare_players"](
            player_names=["Alice", "Bob"], include_fixture_analysis=False
        )

    # Every default metric must resolve to a real key on formatted players
    assert set(result["metrics_comparison"]) == {
        "points",
        "form",
        "goals",
        "assists",
        "bonus",
    }
    assert result["metrics_comparison"]["points"] == {"Alice": 100.0, "Bob": 90.0}
