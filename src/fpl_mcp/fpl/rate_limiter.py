import time
import asyncio
from typing import List

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
    
    async def acquire(self) -> bool:
        """
        Acquire permission to make a request.
        Blocks until a request can be made if the rate limit is reached.
        
        Returns:
            True when request permission is granted
        """
        now = time.time()
        
        # Remove expired request timestamps
        self.request_times = [t for t in self.request_times if now - t < self.time_window]
        
        # If we've reached the limit, wait until we can make another request
        if len(self.request_times) >= self.max_requests:
            # Calculate how long to wait (time until oldest request expires)
            wait_time = self.time_window - (now - self.request_times[0])
            await asyncio.sleep(max(0, wait_time))
            # Recursively try again after waiting
            return await self.acquire()
        
        # Add current time to request times and allow the request
        self.request_times.append(time.time())
        return True