import asyncio
from typing import Any, Awaitable, Iterable, List


async def gather_limited(
    coros: Iterable[Awaitable[Any]],
    limit: int = 5,
    return_exceptions: bool = False,
) -> List[Any]:
    """Run awaitables concurrently, at most `limit` at a time.

    A bounded alternative to asyncio.gather so that fan-out over many
    FPL API calls (e.g. one per league manager) doesn't burst past the
    rate limiter or open too many connections at once.

    Args:
        coros: Awaitables to run
        limit: Maximum number running concurrently
        return_exceptions: As in asyncio.gather

    Returns:
        Results in the same order as the input awaitables
    """
    semaphore = asyncio.Semaphore(limit)

    async def _run(coro: Awaitable[Any]) -> Any:
        async with semaphore:
            return await coro

    return await asyncio.gather(
        *(_run(c) for c in coros), return_exceptions=return_exceptions
    )
