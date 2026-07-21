import time
import asyncio
from typing import List

from ..config import RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_PERIOD_SECONDS

class RateLimiter:
    """
    A simple rate limiter to prevent excessive requests to the FPL API.
    Tracks request times and enforces a maximum number of requests per time window.
    """
    def __init__(self, max_requests: int = 20, per_seconds: int = 60):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window
            per_seconds: Time window in seconds
        """
        self.request_times: List[float] = []
        self.max_requests = max_requests
        self.time_window = per_seconds
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        Acquire permission to make a request.
        Blocks until a request can be made if the rate limit is reached.

        Returns:
            True when request permission is granted
        """
        while True:
            async with self._lock:
                now = time.time()

                # Remove expired request timestamps
                self.request_times = [t for t in self.request_times if now - t < self.time_window]

                if len(self.request_times) < self.max_requests:
                    self.request_times.append(now)
                    return True

                # Time until the oldest request leaves the window
                wait_time = self.time_window - (now - self.request_times[0])

            # Sleep outside the lock so other acquirers aren't blocked
            await asyncio.sleep(max(0.01, wait_time))


# Shared limiter so authenticated and public API calls draw from one budget
rate_limiter = RateLimiter(
    max_requests=RATE_LIMIT_MAX_REQUESTS,
    per_seconds=RATE_LIMIT_PERIOD_SECONDS,
)
