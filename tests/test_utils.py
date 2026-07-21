"""Tests for the shared helper utilities."""

from unittest.mock import AsyncMock, patch

from fpl_mcp.fpl.utils.difficulty import assess_fixtures, fixture_score, score_from_average
from fpl_mcp.fpl.utils.gameweek import get_current_gameweek_id
from fpl_mcp.fpl.utils.params import unwrap


# --- difficulty ---

def test_fixture_score_formula():
    # avg difficulty 2 -> (6-2)*2 = 8
    fixtures = [{"difficulty": 2}, {"difficulty": 2}]
    assert fixture_score(fixtures) == 8.0


def test_fixture_score_empty():
    assert fixture_score([]) == 0.0


def test_fixture_score_custom_key():
    assert fixture_score([{"fdr": 4}], key="fdr") == 4.0


def test_score_from_average():
    assert score_from_average(3) == 6.0
    assert score_from_average(5) == 2.0
    assert score_from_average(1) == 10.0


def test_assessment_ladder():
    assert assess_fixtures(9) == "Excellent fixtures"
    assert assess_fixtures(8) == "Excellent fixtures"
    assert assess_fixtures(7) == "Good fixtures"
    assert assess_fixtures(5) == "Average fixtures"
    assert assess_fixtures(3.9) == "Difficult fixtures"


# --- params.unwrap ---

def test_unwrap_passthrough():
    assert unwrap("Salah", "player_name") == "Salah"
    assert unwrap(5, "num_fixtures", default=3) == 5
    assert unwrap(None, "x", default="d") is None  # non-dict passes through


def test_unwrap_dict_first_key_wins():
    assert unwrap({"player_name": "Salah", "query": "x"}, "player_name", "query") == "Salah"
    assert unwrap({"query": "Kane"}, "player_name", "query") == "Kane"


def test_unwrap_dict_no_match_uses_default():
    assert unwrap({"other": 1}, "num_fixtures", default=5) == 5


def test_unwrap_dict_no_match_no_default_stringifies():
    # Historical fallback for name-like params: str(dict)
    assert unwrap({"other": 1}, "player_name") == str({"other": 1})


# --- gameweek ---

GWS_WITH_CURRENT = [
    {"id": 11, "is_current": False, "is_next": False},
    {"id": 12, "is_current": True, "is_next": False},
    {"id": 13, "is_current": False, "is_next": True},
]

GWS_BETWEEN = [
    {"id": 12, "is_current": False, "is_next": False},
    {"id": 13, "is_current": False, "is_next": True},
]

GWS_NONE = [
    {"id": 1, "is_current": False, "is_next": False},
]


async def test_current_gameweek_id():
    with patch("fpl_mcp.fpl.utils.gameweek.api.get_gameweeks", new=AsyncMock(return_value=GWS_WITH_CURRENT)):
        assert await get_current_gameweek_id() == 12


async def test_current_gameweek_falls_back_to_next_minus_one():
    with patch("fpl_mcp.fpl.utils.gameweek.api.get_gameweeks", new=AsyncMock(return_value=GWS_BETWEEN)):
        assert await get_current_gameweek_id() == 12


async def test_current_gameweek_none_when_undeterminable():
    with patch("fpl_mcp.fpl.utils.gameweek.api.get_gameweeks", new=AsyncMock(return_value=GWS_NONE)):
        assert await get_current_gameweek_id() is None
