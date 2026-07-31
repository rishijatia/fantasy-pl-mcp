"""Tests for the bounded-concurrency helper and player index."""

import asyncio

import pytest

from fpl_mcp.fpl.utils.concurrency import gather_limited


async def test_results_preserve_order():
    async def double(x):
        await asyncio.sleep(0.01 * (5 - x))  # later inputs finish sooner
        return x * 2

    results = await gather_limited((double(i) for i in range(5)), limit=2)
    assert results == [0, 2, 4, 6, 8]


async def test_concurrency_is_bounded():
    running = 0
    peak = 0

    async def tracked():
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1

    await gather_limited((tracked() for _ in range(10)), limit=3)
    assert peak <= 3


async def test_exceptions_returned_when_requested():
    async def ok():
        return "ok"

    async def boom():
        raise RuntimeError("boom")

    results = await gather_limited([ok(), boom(), ok()], return_exceptions=True)
    assert results[0] == "ok"
    assert isinstance(results[1], RuntimeError)
    assert results[2] == "ok"


async def test_exceptions_propagate_by_default():
    async def boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await gather_limited([boom()])


async def test_player_map_indexes_by_id():
    from unittest.mock import AsyncMock, patch

    from fpl_mcp.fpl.cache import get_player_map

    players = [
        {"id": 1, "web_name": "Salah", "team": 14},
        {"id": 2, "web_name": "Haaland", "team": 13},
    ]
    with patch("fpl_mcp.fpl.api.api.get_players", new=AsyncMock(return_value=players)):
        player_map = await get_player_map()

    assert player_map[1]["web_name"] == "Salah"
    assert player_map[2]["team"] == 13
    assert len(player_map) == 2
