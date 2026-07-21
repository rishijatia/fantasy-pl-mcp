"""Regression test: get_simplified_league_decision_analysis previously raised
NameError because `limit` was documented but missing from the signature."""

from unittest.mock import AsyncMock, patch

from fpl_mcp.fpl.tools.simplified_decision import (
    get_simplified_league_decision_analysis,
)

LEAGUE_DATA = {
    "league_info": {"id": 1, "name": "Test League"},
    "standings": [
        {"team_id": 101, "team_name": "Team A", "manager_name": "Alice"},
        {"team_id": 102, "team_name": "Team B", "manager_name": "Bob"},
    ],
}

HISTORICAL_DATA = {
    "teams_data": {
        101: {"current": [{"event": 1, "points_on_bench": 4}]},
        102: {"current": [{"event": 1, "points_on_bench": 7}]},
    }
}


async def test_decisions_analysis_does_not_crash():
    get_standings = AsyncMock(return_value=LEAGUE_DATA)
    get_history = AsyncMock(return_value=HISTORICAL_DATA)

    with patch(
        "fpl_mcp.fpl.tools.simplified_decision.api.get_players",
        new=AsyncMock(return_value=[]),
    ):
        result = await get_simplified_league_decision_analysis(
            league_id=1,
            start_gw=1,
            end_gw=1,
            get_league_standings_func=get_standings,
            get_teams_historical_data_func=get_history,
            league_data=LEAGUE_DATA,
        )

    assert "error" not in result
    assert result["teams_analyzed"] == 2
    rankings = result["bench_analysis"]["rankings"]
    assert len(rankings) == 2
    # Sorted by total bench points, descending
    assert rankings[0]["manager_name"] == "Bob"
    assert rankings[0]["total_bench_points"] == 7


async def test_limit_caps_teams_analyzed():
    many_teams = {
        "league_info": {"id": 1, "name": "Test League"},
        "standings": [
            {"team_id": i, "team_name": f"T{i}", "manager_name": f"M{i}"}
            for i in range(20)
        ],
    }
    get_history = AsyncMock(return_value={"teams_data": {}})

    with patch(
        "fpl_mcp.fpl.tools.simplified_decision.api.get_players",
        new=AsyncMock(return_value=[]),
    ):
        result = await get_simplified_league_decision_analysis(
            league_id=1,
            start_gw=1,
            end_gw=2,
            get_league_standings_func=AsyncMock(return_value=many_teams),
            get_teams_historical_data_func=get_history,
            league_data=many_teams,
            limit=3,
        )

    assert result["teams_analyzed"] == 3
