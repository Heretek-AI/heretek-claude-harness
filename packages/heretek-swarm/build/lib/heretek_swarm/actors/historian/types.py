"""Historian types — LRU Cache implementation."""

from collections import OrderedDict
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class LRUCache:
    """
    LRU Cache implementation with configurable max size.

    Provides automatic eviction of least-recently-used items when capacity is exceeded.
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of items to cache (default: 100)
        """
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get item from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        if key not in self._cache:
            self.misses += 1
            return default

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self.hits += 1
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """
        Set item in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = value
        else:
            if len(self._cache) >= self.max_size:
                # Evict least recently used
                self._cache.popitem(last=False)
            self._cache[key] = value

    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was found and removed, False otherwise
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a pattern.

        Args:
            pattern: Glob-style pattern (* matches any string)

        Returns:
            Number of entries invalidated
        """
        import fnmatch

        keys_to_remove = [key for key in self._cache if fnmatch.fnmatch(key, pattern)]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""
        return key in self._cache

    def __len__(self) -> int:
        """Return number of cached items."""
        return len(self._cache)

    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "invalidations": getattr(self, "_invalidation_count", 0),
        }
