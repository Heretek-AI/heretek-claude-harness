"""
Configuration Cache Module

Provides in-memory caching for configuration data with TTL support.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from heretek_swarm.config.models import ConfigCacheEntry

import structlog
logger = structlog.get_logger(__name__)


class ConfigCache:
    """
    In-memory cache for configuration data with TTL support.

    Features:
    - Configurable TTL for cache entries
    - Cache warming on initialization
    - Automatic expiration
    - Access tracking for optimization
    """

    def __init__(self, ttl_minutes: int = 5):
        """
        Initialize the configuration cache.

        Args:
            ttl_minutes: Time-to-live for cache entries in minutes.
        """
        self._cache: dict[str, ConfigCacheEntry] = {}
        self._cache_ttl = timedelta(minutes=ttl_minutes)
        self._lock = threading.RLock()

    @property
    def ttl(self) -> timedelta:
        """Get the cache TTL."""
        return self._cache_ttl

    @ttl.setter
    def ttl(self, value: timedelta) -> None:
        """Set the cache TTL."""
        self._cache_ttl = value

    def _get_cache_key(self, entity_type: str, key: str) -> str:
        """Generate a cache key for an entity."""
        return f"{entity_type}:{key}"

    def invalidate(self, entity_type: str, key: str) -> None:
        """
        Invalidate a cache entry.

        Args:
            entity_type: Type of entity (e.g., 'config', 'provider')
            key: The entity key
        """
        cache_key = self._get_cache_key(entity_type, key)
        with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.debug("cache_invalidated", cache_key=cache_key)

    def set(
        self,
        entity_type: str,
        key: str,
        value: Any,
        ttl: timedelta | None = None,
    ) -> None:
        """
        Set a cache entry.

        Args:
            entity_type: Type of entity
            key: The entity key
            value: The value to cache
            ttl: Optional custom TTL
        """
        cache_key = self._get_cache_key(entity_type, key)
        with self._lock:
            self._cache[cache_key] = ConfigCacheEntry(
                cache_key=cache_key,
                cache_value={"value": value},
                expires_at=datetime.now(UTC) + (ttl or self._cache_ttl),
            )
        logger.debug("cache_set", cache_key=cache_key)

    def get(self, entity_type: str, key: str) -> Any | None:
        """
        Get a cached value if available and not expired.

        Args:
            entity_type: Type of entity
            key: The entity key

        Returns:
            Cached value or None if not found or expired
        """
        cache_key = self._get_cache_key(entity_type, key)
        with self._lock:
            entry = self._cache.get(cache_key)

            if entry is None:
                logger.debug("cache_miss", cache_key=cache_key)
                return None

            if entry.expires_at and datetime.now(UTC) > entry.expires_at:
                del self._cache[cache_key]
                logger.debug("cache_expired", cache_key=cache_key)
                return None

            entry.access_count += 1
            entry.last_accessed_at = datetime.now(UTC)
            logger.debug("cache_hit", cache_key=cache_key)
            return entry.cache_value.get("value")

    async def warm(
        self,
        session_factory,
        entity_class,
        categories: list[str] | None = None,
    ) -> None:
        """
        Warm up the cache with frequently accessed configurations.

        Args:
            session_factory: SQLAlchemy session factory
            entity_class: The entity class to load
            categories: Optional list of categories to load
        """
        try:
            async with session_factory() as session:
                if categories:
                    from sqlalchemy import select
                    stmt = select(entity_class).where(
                        entity_class.category.in_(categories)
                    )
                else:
                    from sqlalchemy import select
                    stmt = select(entity_class)

                result = await session.execute(stmt)
                entities = result.scalars().all()

                with self._lock:
                    for entity in entities:
                        # Extract key and value based on entity type
                        if hasattr(entity, "config_key"):
                            cache_key = f"config:{entity.config_key}"
                            cache_value = {
                                "value": entity.config_value,
                                "type": entity.config_type.value,
                            }
                        elif hasattr(entity, "provider_id"):
                            cache_key = f"provider:{entity.provider_id}"
                            cache_value = {"value": entity.model_dump()}
                        else:
                            continue

                        self._cache[cache_key] = ConfigCacheEntry(
                            cache_key=cache_key,
                            cache_value=cache_value,
                            expires_at=datetime.now(UTC) + self._cache_ttl,
                        )

                logger.info("cache_warmed", count=len(entities))
        except Exception as e:
            logger.warning("cache_warmup_skipped", reason=str(e))

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
        logger.info("cache_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(
                1 for e in self._cache.values()
                if e.expires_at and datetime.now(UTC) > e.expires_at
            )

            return {
                "total_entries": total_entries,
                "active_entries": total_entries - expired_entries,
                "expired_entries": expired_entries,
                "ttl_minutes": self._cache_ttl.total_seconds() / 60,
                "total_accesses": sum(e.access_count for e in self._cache.values()),
            }
