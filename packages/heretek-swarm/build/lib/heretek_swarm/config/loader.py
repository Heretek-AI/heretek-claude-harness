"""
Configuration Loader

Provides a clean API for runtime code to access configuration from the database.
Includes caching to avoid database hits on every request and maintains backward
compatibility with environment variables as fallback.

Usage:
    # Async usage in FastAPI endpoints
    from heretek_swarm.config.loader import get_config

    config_value = await get_config("rate_limit.enabled", default=True)

    # In runtime code with ConfigLoader instance
    from heretek_swarm.config.loader import ConfigLoader

    loader = ConfigLoader()
    await loader.initialize()
    value = loader.get("memory.max_size", default=1000)
    value_with_source = loader.get_with_source("memory.max_size")
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from .service import ConfigurationService, get_config_service

logger = structlog.get_logger("config.loader")


@dataclass
class CacheEntry:
    """Cache entry for configuration values."""
    value: Any
    source: str  # "database" or "environment"
    expires_at: datetime
    access_count: int = 0
    last_accessed_at: datetime | None = None


class ConfigLoader:
    """
    Configuration loader with caching and environment fallback.

    Features:
    - In-memory caching with TTL
    - Automatic fallback to environment variables
    - Source tracking (database vs environment)
    - Thread-safe access
    - Bulk loading capabilities
    """

    def __init__(
        self,
        service: ConfigurationService | None = None,
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize the configuration loader.

        Args:
            service: ConfigurationService instance. Uses global if not provided.
            cache_ttl_seconds: Cache time-to-live in seconds (default: 5 minutes)
        """
        self._service = service
        self._cache: dict[str, CacheEntry] = {}
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._initialized = False
        self._config_keys: dict[str, str] = self._build_config_key_mapping()

    def _build_config_key_mapping(self) -> dict[str, str]:
        """
        Build mapping from config keys to environment variable names.

        This defines the relationship between database config keys and
        their corresponding environment variable fallbacks.
        """
        return {
            # Rate limiting
            "rate_limit.enabled": "RATE_LIMIT_ENABLED",
            "rate_limit.requests_per_minute": "RATE_LIMIT_REQUESTS_PER_MINUTE",

            # Memory
            "memory.max_size": "MEMORY_MAX_SIZE",
            "memory.default_ttl": "MEMORY_DEFAULT_TTL",
            "memory.retention_days": "MEMORY_RETENTION_DAYS",

            # Consciousness
            "consciousness.phi_threshold": "CONSCIOUSNESS_PHI_THRESHOLD",
            "consciousness.enabled": "CONSCIOUSNESS_ENABLED",

            # Consensus
            "consensus.min_votes": "CONSENSUS_MIN_VOTES",
            "consensus.confidence_threshold": "CONSENSUS_CONFIDENCE_THRESHOLD",

            # Runtime
            "runtime.monitoring_enabled": "MONITORING_ENABLED",
            "runtime.auto_restart_enabled": "AUTO_RESTART_ENABLED",
            "runtime.health_check_interval": "HEALTH_CHECK_INTERVAL",
            "runtime.metrics_collection_interval": "METRICS_COLLECTION_INTERVAL",

            # RAG
            "rag.enabled": "RAG_ENABLED",

            # Bot integrations
            "integrations.discord_enabled": "DISCORD_BOT_ENABLED",
            "integrations.telegram_enabled": "TELEGRAM_BOT_ENABLED",
            "integrations.slack_enabled": "SLACK_BOT_ENABLED",

            # API
            "api.host": "API_HOST",
            "api.port": "API_PORT",
            "api.workers": "API_WORKERS",
            "api.environment": "ENVIRONMENT",
            "api.cors_origins": "CORS_ORIGINS",

            # Database
            "database.url": "DATABASE_URL",
            "redis.url": "REDIS_URL",
            "qdrant.url": "QDRANT_URL",

            # Logging
            "logging.level": "LOG_LEVEL",
            "logging.format": "LOG_FORMAT",

            # Security
            "security.auth_enabled": "AUTH_ENABLED",
            "security.rate_limit_enabled": "RATE_LIMIT_ENABLED",

            # LLM
            "llm.provider": "LLM_PROVIDER",
            "llm.model": "MINIMAX_MODEL",
            "llm.api_key": "MINIMAX_API_KEY",
            "llm.base_url": "MINIMAX_BASE_URL",
            "llm.group_id": "MINIMAX_GROUP_ID",

            # Embeddings
            "embeddings.provider": "EMBEDDING_PROVIDER",
            "embeddings.model": "EMBEDDER_MODEL",
            "embeddings.base_url": "EMBEDDING_BASE_URL",
            "embeddings.api_key": "EMBEDDING_API_KEY",
        }

    async def initialize(self) -> None:
        """
        Initialize the configuration loader.

        This loads the ConfigurationService and warms up the cache
        with frequently accessed configurations.
        """
        if self._initialized:
            return

        if self._service is None:
            self._service = get_config_service()

        # Initialize the service if not already done
        await self._service.initialize()

        # Warm up cache with common configurations
        await self._warm_cache()

        self._initialized = True
        logger.info("ConfigLoader initialized")

    async def _warm_cache(self) -> None:
        """Warm up the cache with frequently accessed configurations."""
        common_keys = [
            "rate_limit.enabled",
            "memory.max_size",
            "consciousness.enabled",
            "rag.enabled",
            "api.environment",
            "logging.level",
        ]

        for key in common_keys:
            try:
                await self._load_config(key)
            except Exception as e:
                logger.debug(f"Failed to warm cache for {key}: {e}")

    async def _load_config(self, config_key: str) -> tuple[Any, str]:
        """
        Load a configuration value from database or environment.

        Args:
            config_key: The configuration key (e.g., "rate_limit.enabled")

        Returns:
            Tuple of (value, source) where source is "database" or "environment"
        """
        # Try database first
        try:
            config = await self._service.get_config(config_key)
            if config is not None:
                value = config.config_value
                # Convert type if needed
                if config.config_type:
                    value = self._convert_value(value, config.config_type.value)

                self._cache[config_key] = CacheEntry(
                    value=value,
                    source="database",
                    expires_at=datetime.now(UTC) + self._cache_ttl,
                )
                logger.debug(f"Loaded config from database: {config_key}")
                return value, "database"
        except Exception as e:
            logger.debug(f"Database config lookup failed for {config_key}: {e}")

        # Fallback to environment variable
        env_var = self._config_keys.get(config_key)
        if env_var:
            env_value = os.environ.get(env_var)
            if env_value is not None:
                # Convert to appropriate type
                converted_value = self._convert_env_value(env_value)
                self._cache[config_key] = CacheEntry(
                    value=converted_value,
                    source="environment",
                    expires_at=datetime.now(UTC) + self._cache_ttl,
                )
                logger.debug(f"Loaded config from environment: {config_key} ({env_var})")
                return converted_value, "environment"

        # Not found anywhere
        return None, "not_found"

    def _convert_value(self, value: Any, config_type: str) -> Any:
        """Convert a value to the specified type."""
        if value is None:
            return None

        type_map = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": lambda x: str(x).lower() in ("true", "1", "yes"),
            "json": lambda x: x,  # Already parsed from JSON
        }

        converter = type_map.get(config_type, str)
        try:
            return converter(value)
        except (ValueError, TypeError):
            return value

    def _convert_env_value(self, value: str) -> Any:
        """
        Convert an environment variable value to appropriate type.

        Tries to intelligently detect the type based on the value format.
        """
        # Boolean
        if value.lower() in ("true", "1", "yes"):
            return True
        if value.lower() in ("false", "0", "no"):
            return False

        # Integer
        try:
            return int(value)
        except ValueError:
            logger.debug(f"Config value '{value}' is not an int, trying next type")

        # Float
        try:
            return float(value)
        except ValueError:
            logger.debug(f"Config value '{value}' is not a float, trying next type")

        # JSON array/object
        if value.startswith(("[", "{")):
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.debug("Config value is not valid JSON, defaulting to string")

        # Default to string
        return value

    def _get_cache(self, config_key: str) -> CacheEntry | None:
        """Get a cached value if available and not expired."""
        entry = self._cache.get(config_key)

        if entry is None:
            return None

        if datetime.now(UTC) > entry.expires_at:
            del self._cache[config_key]
            return None

        entry.access_count += 1
        entry.last_accessed_at = datetime.now(UTC)
        return entry

    def get(self, config_key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Uses cached value if available and not expired.
        Returns default if not found.

        Args:
            config_key: Configuration key (e.g., "rate_limit.enabled")
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        # Check cache first
        entry = self._get_cache(config_key)
        if entry is not None:
            return entry.value

        # Not in cache - return default
        # (async loading should be done via get_async)
        return default

    async def get_async(self, config_key: str, default: Any = None) -> Any:
        """
        Get a configuration value asynchronously.

        Loads from database or environment if not cached.

        Args:
            config_key: Configuration key (e.g., "rate_limit.enabled")
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        # Check cache first
        entry = self._get_cache(config_key)
        if entry is not None:
            return entry.value

        # Load from database or environment
        if self._initialized:
            value, _ = await self._load_config(config_key)
            if value is not None:
                return value

        return default

    def get_with_source(self, config_key: str, default: Any = None) -> tuple[Any, str]:
        """
        Get a configuration value with its source.

        Args:
            config_key: Configuration key
            default: Default value if not found

        Returns:
            Tuple of (value, source) where source is "database", "environment", or "default"
        """
        entry = self._get_cache(config_key)
        if entry is not None:
            return entry.value, entry.source

        return default, "default"

    async def get_async_with_source(
        self,
        config_key: str,
        default: Any = None,
    ) -> tuple[Any, str]:
        """
        Get a configuration value with its source asynchronously.

        Args:
            config_key: Configuration key
            default: Default value if not found

        Returns:
            Tuple of (value, source)
        """
        entry = self._get_cache(config_key)
        if entry is not None:
            return entry.value, entry.source

        if self._initialized:
            value, source = await self._load_config(config_key)
            if value is not None:
                return value, source

        return default, "default"

    async def get_many(self, config_keys: list[str]) -> dict[str, Any]:
        """
        Get multiple configuration values at once.

        Args:
            config_keys: List of configuration keys

        Returns:
            Dictionary mapping keys to values
        """
        results = {}
        for key in config_keys:
            results[key] = await self.get_async(key)
        return results

    def invalidate(self, config_key: str) -> None:
        """
        Invalidate a cached configuration.

        Args:
            config_key: Configuration key to invalidate
        """
        if config_key in self._cache:
            del self._cache[config_key]
            logger.debug(f"Invalidated cache for: {config_key}")

    def invalidate_all(self) -> None:
        """Invalidate all cached configurations."""
        self._cache.clear()
        logger.info("Invalidated all configuration cache")

    async def reload(self) -> dict[str, Any]:
        """
        Reload all configurations from database.

        Returns:
            Summary of reload operation
        """
        self._cache.clear()
        await self._warm_cache()

        return {
            "status": "reloaded",
            "cached_keys": list(self._cache.keys()),
            "cache_count": len(self._cache),
        }

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if not self._cache:
            return {
                "total_entries": 0,
                "total_accesses": 0,
                "oldest_entry": None,
                "newest_entry": None,
            }

        datetime.now(UTC)
        total_accesses = sum(e.access_count for e in self._cache.values())
        expires_at_list = [e.expires_at for e in self._cache.values()]

        return {
            "total_entries": len(self._cache),
            "total_accesses": total_accesses,
            "oldest_entry": min(expires_at_list).isoformat() if expires_at_list else None,
            "newest_entry": max(expires_at_list).isoformat() if expires_at_list else None,
            "hit_rate": total_accesses / len(self._cache) if self._cache else 0,
        }


# Global ConfigLoader instance
_config_loader: ConfigLoader | None = None


def get_config_loader() -> ConfigLoader:
    """Get or create the global ConfigLoader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


async def initialize_config_loader() -> None:
    """Initialize the global ConfigLoader."""
    loader = get_config_loader()
    await loader.initialize()


async def get_config(config_key: str, default: Any = None) -> Any:
    """
    Convenience function to get a configuration value.

    Uses the global ConfigLoader instance.

    Args:
        config_key: Configuration key (e.g., "rate_limit.enabled")
        default: Default value if not found

    Returns:
        Configuration value or default
    """
    loader = get_config_loader()
    if not loader._initialized:
        await loader.initialize()
    return await loader.get_async(config_key, default)


async def get_config_with_source(
    config_key: str,
    default: Any = None,
) -> tuple[Any, str]:
    """
    Convenience function to get a configuration value with source.

    Args:
        config_key: Configuration key
        default: Default value if not found

    Returns:
        Tuple of (value, source)
    """
    loader = get_config_loader()
    if not loader._initialized:
        await loader.initialize()
    return await loader.get_async_with_source(config_key, default)


async def reload_config() -> dict[str, Any]:
    """
    Convenience function to reload all configurations.

    Returns:
        Reload summary
    """
    loader = get_config_loader()
    if not loader._initialized:
        await loader.initialize()
    return await loader.reload()
