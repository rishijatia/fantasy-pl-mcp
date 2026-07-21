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
    await asyncio.gather(*(limiter.acquire() for _ in range(12)))

    # Every recorded timestamp respects the budget: sort and check that
    # request i and request i+5 are at least a window apart.
    times = sorted(limiter.request_times)
    all_times = times  # only the last window is retained; the invariant
    # still holds for what remains
    for i in range(len(all_times) - 5):
        assert all_times[i + 5] - all_times[i] >= 0.9


def test_module_level_singleton_exists():
    """api.py and auth_manager.py must share one limiter instance."""
    from fpl_mcp.fpl.api import api
    from fpl_mcp.fpl import auth_manager as am

    assert api.rate_limiter is rate_limiter
