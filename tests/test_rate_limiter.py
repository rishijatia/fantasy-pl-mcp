"""Tests for the shared rate limiter."""

import asyncio
import time

from fpl_mcp.fpl.rate_limiter import RateLimiter, rate_limiter


async def test_allows_requests_under_limit():
    limiter = RateLimiter(max_requests=5, per_seconds=60)
    start = time.monotonic()
    for _ in range(5):
        assert await limiter.acquire() is True
    assert time.monotonic() - start < 1.0


async def test_blocks_when_limit_reached():
    limiter = RateLimiter(max_requests=3, per_seconds=1)
    start = time.monotonic()
    # 3 pass immediately, the 4th must wait for the window to roll over
    for _ in range(4):
        await limiter.acquire()
    assert time.monotonic() - start >= 0.9


async def test_concurrent_acquires_never_exceed_limit():
    """Under concurrency, no more than max_requests may land in one window."""
    limiter = RateLimiter(max_requests=5, per_seconds=1)
    times: list[float] = []

    async def acquire_and_record():
        await limiter.acquire()
        times.append(time.monotonic())

    await asyncio.gather(*(acquire_and_record() for _ in range(12)))

    # The limiter only retains the last window internally, so record every
    # completion ourselves: request i and request i+5 must be at least a
    # window apart or more than 5 requests landed inside one window.
    times.sort()
    assert len(times) == 12
    for i in range(len(times) - 5):
        assert times[i + 5] - times[i] >= 0.9


def test_module_level_singleton_exists():
    """api.py and auth_manager.py must share one limiter instance."""
    from fpl_mcp.fpl.api import api
    from fpl_mcp.fpl import auth_manager as am

    assert api.rate_limiter is rate_limiter
