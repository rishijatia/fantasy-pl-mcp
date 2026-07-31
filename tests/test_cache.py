"""Tests for the disk cache: native expiry and concurrent fetch behavior."""

import asyncio
import tempfile

from fpl_mcp.fpl.cache import FPLCache


def make_cache(default_ttl=3600):
    return FPLCache(cache_dir=tempfile.mkdtemp(prefix="fpl-cache-test-"), default_ttl=default_ttl)


async def test_get_or_fetch_caches_result():
    cache = make_cache()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return {"n": calls}

    first = await cache.get_or_fetch("key", fetch)
    second = await cache.get_or_fetch("key", fetch)

    assert first == second == {"n": 1}
    assert calls == 1


async def test_entries_expire():
    cache = make_cache()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return calls

    # Sub-second TTL: diskcache supports float expiry
    assert await cache.get_or_fetch("key", fetch, ttl=0.2) == 1
    await asyncio.sleep(0.3)
    assert await cache.get_or_fetch("key", fetch, ttl=0.2) == 2


async def test_concurrent_fetches_deduplicate():
    """Concurrent requests for the same key trigger exactly one fetch."""
    cache = make_cache()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return "value"

    results = await asyncio.gather(
        *(cache.get_or_fetch("key", fetch) for _ in range(8))
    )

    assert all(r == "value" for r in results)
    assert calls == 1


async def test_clear_specific_key():
    cache = make_cache()

    async def fetch():
        return "v"

    await cache.get_or_fetch("key", fetch)
    cache.clear("key")

    calls = 0

    async def fetch2():
        nonlocal calls
        calls += 1
        return "v2"

    assert await cache.get_or_fetch("key", fetch2) == "v2"
    assert calls == 1


async def test_falsy_values_are_cached():
    """Empty dicts/lists must be cached, not refetched."""
    cache = make_cache()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return []

    assert await cache.get_or_fetch("key", fetch) == []
    assert await cache.get_or_fetch("key", fetch) == []
    assert calls == 1
