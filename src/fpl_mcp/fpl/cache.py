import time
import os
import pathlib
from typing import Any, Callable, Dict, Optional, TypeVar
from diskcache import Cache
import asyncio
from functools import wraps
import json

from ..config import CACHE_DIR, CACHE_TTL

T = TypeVar('T')

class FPLCache:
    """
    A disk-based caching system with TTL (Time To Live) for FPL API data.
    Uses diskcache for persistent storage between runs.
    """
    def __init__(self, cache_dir=CACHE_DIR, default_ttl=CACHE_TTL):
        """
        Initialize the cache.
        
        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default cache TTL in seconds (1 hour by default)
        """
        # Ensure the cache directory exists
        os.makedirs(cache_dir, exist_ok=True)
        self.cache = Cache(str(cache_dir))
        self.default_ttl = default_ttl
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get a lock for a specific cache key to prevent concurrent fetches."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
    
    async def get_or_fetch(self, key: str, fetch_func: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        Get from cache or fetch and cache the data.
        Uses locks to prevent concurrent fetches for the same key.
        
        Args:
            key: Cache key
            fetch_func: Async function to call if cache miss
            ttl: Optional TTL override
            
        Returns:
            Cached or freshly fetched data
        """
        # Use lock to prevent multiple concurrent fetches for same key
        async with self._get_lock(key):
            current_time = time.time()
            
            # Check if key exists and is not expired
            if key in self.cache:
                cached_time, cached_data = self.cache[key]
                if current_time - cached_time < (ttl or self.default_ttl):
                    return cached_data
            
            # Cache miss or expired, fetch new data
            data = await fetch_func()
            self.cache[key] = (current_time, data)
            return data
    
    def clear(self, key: Optional[str] = None) -> None:
        """
        Clear cache entries.
        
        Args:
            key: Specific key to clear, or all cache if None
        """
        if key is None:
            self.cache.clear()
        elif key in self.cache:
            del self.cache[key]
            
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "directory": str(self.cache.directory),
            "entries": list(self.cache.iterkeys())
        }


# Create a singleton instance
cache = FPLCache()


def cached(key_prefix: str, ttl: Optional[int] = None):
    """
    Decorator for caching async function results.
    
    Args:
        key_prefix: Prefix for cache key
        ttl: Optional TTL override
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create a cache key from function name, args, and kwargs
            key_parts = [key_prefix, func.__name__]
            
            # Add stringified args and kwargs to key
            if args:
                key_parts.append(str(args))
            if kwargs:
                # Sort kwargs by key for consistent cache keys
                sorted_kwargs = sorted(kwargs.items())
                key_parts.append(str(sorted_kwargs))
                
            cache_key = "_".join(key_parts)
            
            # Define fetch function
            async def fetch_func():
                return await func(*args, **kwargs)
                
            return await cache.get_or_fetch(cache_key, fetch_func, ttl)
            
        return wrapper
    return decorator