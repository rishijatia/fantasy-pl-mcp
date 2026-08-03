"""Tests for the new FPL endpoint tools (live scores, dream team,
transfer history, price changes, captain suggestions)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from fpl_mcp.fpl.api import api

BASE = "https://fantasy.premierleague.com/api"

RAW_PLAYERS = [
    {
        "id": 1, "web_name": "Salah", "team": 14, "element_type": 3,
        "now_cost": 130, "cost_change_event": 1, "cost_change_start": 5,
        "selected_by_percent": "55.0", "transfers_in_event": 200000,
        "transfers_out_event": 10000, "form": "9.0", "points_per_game": "8.0",
        "ep_next": "8.5", "status": "a", "news": "",
        "chance_of_playing_next_round": None,
    },
    {
        "id": 2, "web_name": "Haaland", "team": 13, "element_type": 4,
        "now_cost": 150, "cost_change_event": 0, "cost_change_start": 2,
        "selected_by_percent": "80.0", "transfers_in_event": 50000,
        "transfers_out_event": 60000, "form": "7.0", "points_per_game": "7.5",
        "ep_next": "7.0", "status": "d", "news": "Knock",
        "chance_of_playing_next_round": 75,
    },
    {
        "id": 3, "web_name": "Raya", "team": 1, "element_type": 1,
        "now_cost": 55, "cost_change_event": -1, "cost_change_start": -2,
        "selected_by_percent": "20.0", "transfers_in_event": 1000,
        "transfers_out_event": 90000, "form": "4.0", "points_per_game": "4.0",
        "ep_next": "4.5", "status": "a", "news": "",
        "chance_of_playing_next_round": None,
    },
]

TEAMS = [
    {"id": 1, "name": "Arsenal", "short_name": "ARS"},
    {"id": 13, "name": "Man City", "short_name": "MCI"},
    {"id": 14, "name": "Liverpool", "short_name": "LIV"},
]

LIVE_DATA = {
    "elements": [
        {"id": 1, "stats": {"total_points": 13, "minutes": 90, "goals_scored": 2,
                            "assists": 0, "bonus": 3, "bps": 60, "in_dreamteam": True}},
        {"id": 2, "stats": {"total_points": 2, "minutes": 90, "goals_scored": 0,
                            "assists": 0, "bonus": 0, "bps": 12, "in_dreamteam": False}},
        {"id": 3, "stats": {"total_points": 0, "minutes": 0, "goals_scored": 0,
                            "assists": 0, "bonus": 0, "bps": 0, "in_dreamteam": False}},
    ]
}


def patch_static():
    """Patch bootstrap-derived data so tools don't hit the network for it."""
    return patch.multiple(
        "fpl_mcp.fpl.api.FPLAPI",
        get_players=AsyncMock(return_value=RAW_PLAYERS),
        get_teams=AsyncMock(return_value=TEAMS),
    )


async def test_live_event_api_method():
    with respx.mock:
        route = respx.get(f"{BASE}/event/7/live/").mock(
            return_value=httpx.Response(200, json=LIVE_DATA)
        )
        data = await api.get_live_event_data(7)
        assert data == LIVE_DATA
        assert route.call_count == 1

        # Second call comes from cache
        await api.get_live_event_data(7)
        assert route.call_count == 1
    await api.close()


async def test_entry_transfers_api_method():
    transfers = [
        {"element_in": 1, "element_in_cost": 128, "element_out": 3,
         "element_out_cost": 55, "event": 7, "time": "2026-07-01T10:00:00Z"},
    ]
    with respx.mock:
        respx.get(f"{BASE}/entry/12345/transfers/").mock(
            return_value=httpx.Response(200, json=transfers)
        )
        data = await api.get_entry_transfers(12345)
        assert data == transfers
    await api.close()


async def test_dream_team_api_method():
    payload = {"top_player": {"id": 1, "points": 13},
               "team": [{"element": 1, "points": 13, "position": 1}]}
    with respx.mock:
        respx.get(f"{BASE}/dream-team/7/").mock(
            return_value=httpx.Response(200, json=payload)
        )
        data = await api.get_dream_team(7)
        assert data["top_player"]["id"] == 1
    await api.close()


class ToolCollector:
    """Minimal FastMCP stand-in that records registered tool functions."""

    def __init__(self):
        self.tools = {}

    def tool(self, *args, **kwargs):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def collect(register_tools):
    mcp = ToolCollector()
    register_tools(mcp)
    return mcp.tools


async def test_get_gameweek_live_scores_tool():
    from fpl_mcp.fpl.tools.live import register_tools

    tools = collect(register_tools)
    with patch_static(), \
         patch("fpl_mcp.fpl.api.FPLAPI.get_live_event_data", new=AsyncMock(return_value=LIVE_DATA)), \
         patch("fpl_mcp.fpl.api.FPLAPI.get_event_status", new=AsyncMock(return_value={
             "status": [{"event": 7, "bonus_added": False}]})):
        result = await tools["get_gameweek_live_scores"](gameweek_id=7)

    assert result["gameweek"] == 7
    assert result["bonus_added"] is False
    # Only players with minutes, sorted by points
    assert [p["name"] for p in result["players"]] == ["Salah", "Haaland"]
    assert result["players"][0]["points"] == 13
    assert result["players"][0]["team"] == "Liverpool"


async def test_get_gameweek_live_scores_filters_by_player_ids():
    from fpl_mcp.fpl.tools.live import register_tools

    tools = collect(register_tools)
    with patch_static(), \
         patch("fpl_mcp.fpl.api.FPLAPI.get_live_event_data", new=AsyncMock(return_value=LIVE_DATA)), \
         patch("fpl_mcp.fpl.api.FPLAPI.get_event_status", new=AsyncMock(return_value={"status": []})):
        result = await tools["get_gameweek_live_scores"](gameweek_id=7, player_ids=[2, 3])

    # Requested players are kept even with 0 minutes
    assert {p["id"] for p in result["players"]} == {2, 3}


async def test_get_dream_team_tool():
    from fpl_mcp.fpl.tools.live import register_tools

    tools = collect(register_tools)
    payload = {"top_player": {"id": 1, "points": 13},
               "team": [{"element": 1, "points": 13}, {"element": 2, "points": 2}]}
    with patch_static(), \
         patch("fpl_mcp.fpl.api.FPLAPI.get_dream_team", new=AsyncMock(return_value=payload)):
        result = await tools["get_dream_team"](gameweek_id=7)

    assert result["top_player"]["name"] == "Salah"
    assert result["total_points"] == 15
    assert result["team"][0]["position"] == "MID"


async def test_get_manager_transfer_history_tool():
    from fpl_mcp.fpl.tools.managers import register_tools

    tools = collect(register_tools)
    transfers = [
        {"element_in": 1, "element_in_cost": 128, "element_out": 3,
         "element_out_cost": 55, "event": 7, "time": "2026-07-01T10:00:00Z"},
        {"element_in": 2, "element_in_cost": 150, "element_out": 1,
         "element_out_cost": 130, "event": 6, "time": "2026-06-24T10:00:00Z"},
    ]
    with patch_static(), \
         patch("fpl_mcp.fpl.api.FPLAPI.get_entry_transfers", new=AsyncMock(return_value=transfers)):
        result = await tools["get_manager_transfer_history"](team_id=12345)

    assert result["total_transfers"] == 2
    assert result["transfers_returned"] == 2
    assert result["transfers"][0]["player_in"] == "Salah"
    assert result["transfers"][0]["player_out"] == "Raya"
    assert result["transfers"][0]["player_in_cost"] == 12.8
    assert set(result["transfers_by_gameweek"].keys()) == {"7", "6"}

    # With a limit, total_transfers still reports the full API count
    with patch_static(), \
         patch("fpl_mcp.fpl.api.FPLAPI.get_entry_transfers", new=AsyncMock(return_value=transfers)):
        limited = await tools["get_manager_transfer_history"](team_id=12345, limit=1)

    assert limited["total_transfers"] == 2
    assert limited["transfers_returned"] == 1


async def test_get_price_changes_tool():
    from fpl_mcp.fpl.tools.players import register_tools

    tools = collect(register_tools)
    with patch_static():
        result = await tools["get_price_changes"]()

    assert result["summary"] == {"total_risers": 1, "total_fallers": 1}
    assert result["risers"][0]["name"] == "Salah"
    assert result["risers"][0]["change_this_gameweek"] == 0.1
    assert result["fallers"][0]["name"] == "Raya"

    with patch_static():
        only_risers = await tools["get_price_changes"](direction="risers")
    assert "fallers" not in only_risers


async def test_suggest_captain_tool():
    from fpl_mcp.fpl.tools.advice import register_tools

    tools = collect(register_tools)
    picks = {"picks": [
        {"element": 1, "is_captain": False},
        {"element": 2, "is_captain": True},
        {"element": 3, "is_captain": False},
    ]}
    fixtures = [{"gameweek": 8, "difficulty": 2, "location": "home", "opponent": "X"}]

    mock_auth = AsyncMock()
    mock_auth.team_id = "999"
    mock_auth.get_team_for_gameweek = AsyncMock(return_value=picks)

    with patch_static(), \
         patch("fpl_mcp.fpl.tools.advice.get_auth_manager", return_value=mock_auth), \
         patch("fpl_mcp.fpl.tools.advice.get_player_fixtures", new=AsyncMock(return_value=fixtures)):
        result = await tools["suggest_captain"](gameweek_id=7)

    assert result["team_id"] == 999
    assert len(result["candidates"]) == 3
    # Salah has the best blend of ep_next/form/ppg and full availability
    assert result["recommendation"]["name"] == "Salah"
    # Doubtful Haaland (75% chance) is availability-scaled
    haaland = next(c for c in result["candidates"] if c["name"] == "Haaland")
    assert haaland["components"]["availability"] == 0.75
    assert haaland["status"] == "doubtful/unavailable"


async def test_suggest_captain_requires_team():
    from fpl_mcp.fpl.tools.advice import register_tools

    tools = collect(register_tools)
    mock_auth = AsyncMock()
    mock_auth.team_id = None

    with patch("fpl_mcp.fpl.tools.advice.get_auth_manager", return_value=mock_auth):
        result = await tools["suggest_captain"]()

    assert "error" in result


async def test_live_scores_reports_gameweek_not_started():
    """Pre-season the FPL API 404s on event/N/live; that is not an error."""
    from fpl_mcp.fpl.tools.live import register_tools

    tools = collect(register_tools)
    with respx.mock:
        respx.get(f"{BASE}/event/91/live/").mock(return_value=httpx.Response(404))
        with patch_static():
            result = await tools["get_gameweek_live_scores"](gameweek_id=91)

    assert "error" not in result
    assert result["gameweek"] == 91
    assert result["players"] == []
    assert "not started yet" in result["note"]
    await api.close()


async def test_dream_team_reports_gameweek_not_played():
    """Pre-season the FPL API 404s on dream-team/N; that is not an error."""
    from fpl_mcp.fpl.tools.live import register_tools

    tools = collect(register_tools)
    with respx.mock:
        respx.get(f"{BASE}/dream-team/92/").mock(return_value=httpx.Response(404))
        with patch_static():
            result = await tools["get_dream_team"](gameweek_id=92)

    assert "error" not in result
    assert result["gameweek"] == 92
    assert result["team"] == []
    assert "not been played yet" in result["note"]
    await api.close()


async def test_dream_team_still_reports_real_failures():
    """A 500 is a genuine failure and must not be masked as 'not played'."""
    from fpl_mcp.fpl.tools.live import register_tools

    tools = collect(register_tools)
    with respx.mock:
        respx.get(f"{BASE}/dream-team/93/").mock(return_value=httpx.Response(500))
        with patch_static():
            result = await tools["get_dream_team"](gameweek_id=93)

    assert "error" in result
    await api.close()
