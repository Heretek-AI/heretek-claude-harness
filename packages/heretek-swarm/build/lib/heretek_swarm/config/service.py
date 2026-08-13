"""
Configuration Service

Provides CRUD operations for configurations with caching and validation.
Supports migration from .env to database-backed configuration.
Features API key encryption using Fernet symmetric encryption.

Architecture:
    - ConfigurationService: Main service class (infrastructure)
    - ConfigurationServiceCrud: CRUD operations mixin (split into crud.py)
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .crud import ConfigurationServiceCrud
from .db_models import (
    AgentConfig as AgentConfigORM,
)
from .db_models import (
    EmbeddingProvider as EmbeddingProviderORM,
)
from .db_models import (
    InfrastructureConfig as InfrastructureConfigORM,
)
from .db_models import (
    LLMProvider as LLMProviderORM,
)
from .db_models import (
    UserConfiguration as UserConfigurationORM,
)
from .encryption import ApiKeyEncryptor
from .models import (
    AgentConfig,
    ConfigCacheEntry,
    ConfigType,
    EmbeddingProvider,
    EmbeddingProviderCreate,
    EmbeddingProviderType,
    InfrastructureConfig,
    InfrastructureService,
    LLMProvider,
    LLMProviderCreate,
    LLMProviderType,
    UserConfiguration,
    UserConfigurationCreate,
)

logger = structlog.get_logger("config.service")


class SeedResult(TypedDict):
    """Return type for ConfigurationService.seed_from_env()."""

    providers_created: int
    embedding_providers_created: int
    configs_created: int
    skipped_reasons: list[str]


class ConfigurationService(ConfigurationServiceCrud):
    """
    Service for managing configurations in the database.

    Features:
    - CRUD operations for all configuration types
    - In-memory caching for frequently accessed configs
    - Validation of configuration values
    - Audit logging for changes
    - Import/export functionality
    - Migration from .env files

    CRUD operations are provided by ConfigurationServiceCrud mixin.
    """

    def __init__(self, database_url: str | None = None):
        """
        Initialize the configuration service.

        Args:
            database_url: PostgreSQL database URL. Defaults to DATABASE_URL env var.

        Raises:
            ValueError: If DATABASE_URL environment variable is not set
        """
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        self._engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_pre_ping=True,
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Lazy-attach DB timing listener — zero cost until ConfigurationService is instantiated
        from heretek_swarm.observability.db_timing import attach_db_timing
        from heretek_swarm.observability.prometheus_metrics import (
            heretek_swarm_db_query_duration_seconds,
        )

        attach_db_timing(
            self._engine,
            histogram=heretek_swarm_db_query_duration_seconds,
            histogram_labels={"db_name": "config"},
        )

        # In-memory cache for frequently accessed configurations
        self._cache: dict[str, ConfigCacheEntry] = {}
        self._cache_ttl = timedelta(minutes=5)

        # Encryption for API keys using ApiKeyEncryptor (file-based key persistence)
        self._encryptor: ApiKeyEncryptor = ApiKeyEncryptor()

        logger.info("ConfigurationService initialized", database_url=self.database_url)

    def encrypt_api_key(self, api_key: str) -> str:
        """
        Encrypt an API key using Fernet symmetric encryption.

        Args:
            api_key: The plain text API key to encrypt

        Returns:
            Encrypted API key (base64 encoded)

        Raises:
            ValueError: If encryption is not configured
        """
        return self._encryptor.encrypt(api_key)

    def decrypt_api_key(self, encrypted_key: str) -> str:
        """
        Decrypt an API key using Fernet symmetric encryption.

        Args:
            encrypted_key: The encrypted API key to decrypt

        Returns:
            Decrypted plain text API key

        Raises:
            ValueError: If decryption fails or encryption not configured
        """
        return self._encryptor.decrypt(encrypted_key)

    async def initialize(self) -> None:
        """Initialize the service and warm up the cache."""
        await self._warm_cache()
        logger.info("ConfigurationService initialized with cache")

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        await self._engine.dispose()
        logger.info("ConfigurationService shutdown complete")

    # ====================================================================
    # Cache Management
    # ====================================================================

    async def _warm_cache(self) -> None:
        """Warm up the cache with frequently accessed configurations."""
        try:
            async with self._session_factory() as session:
                from sqlalchemy import select

                # Cache system configurations
                result = await session.execute(
                    select(UserConfigurationORM).where(
                        UserConfigurationORM.category.in_(["system", "rate_limiting"])
                    )
                )
                configs = result.scalars().all()

                for config in configs:
                    cache_key = f"config:{config.config_key}"
                    self._cache[cache_key] = ConfigCacheEntry(
                        cache_key=cache_key,
                        cache_value={"value": config.config_value, "type": config.config_type},
                        expires_at=datetime.now(UTC) + self._cache_ttl,
                    )
        except Exception as e:
            logger.warning("cache_warmup_skipped", reason=str(e))

    def _get_cache_key(self, entity_type: str, key: str) -> str:
        """Generate a cache key for an entity."""
        return f"{entity_type}:{key}"

    def _invalidate_cache(self, entity_type: str, key: str) -> None:
        """Invalidate a cache entry."""
        cache_key = self._get_cache_key(entity_type, key)
        if cache_key in self._cache:
            del self._cache[cache_key]

    def _set_cache(
        self,
        entity_type: str,
        key: str,
        value: Any,
        ttl: timedelta | None = None,
    ) -> None:
        """Set a cache entry."""
        cache_key = self._get_cache_key(entity_type, key)
        self._cache[cache_key] = ConfigCacheEntry(
            cache_key=cache_key,
            cache_value={"value": value},
            expires_at=datetime.now(UTC) + (ttl or self._cache_ttl),
        )

    def _get_cache(self, entity_type: str, key: str) -> dict[str, Any] | None:
        """Get a cached value if available and not expired."""
        cache_key = self._get_cache_key(entity_type, key)
        entry = self._cache.get(cache_key)

        if entry is None:
            return None

        if entry.expires_at and datetime.now(UTC) > entry.expires_at:
            del self._cache[cache_key]
            return None

        entry.access_count += 1
        entry.last_accessed_at = datetime.now(UTC)
        return entry.cache_value

    def _orm_to_pydantic(self, orm_obj: Any) -> Any:
        """Convert SQLAlchemy ORM object to Pydantic model for public API."""
        if orm_obj is None:
            return None

        # Map ORM class to Pydantic class
        if isinstance(orm_obj, UserConfigurationORM):
            return UserConfiguration(
                id=orm_obj.id,
                config_key=orm_obj.config_key,
                config_value=orm_obj.config_value,
                config_type=orm_obj.config_type,
                description=orm_obj.description,
                category=orm_obj.category,
                is_sensitive=orm_obj.is_sensitive,
                is_editable=orm_obj.is_editable,
                validation_schema=orm_obj.validation_schema,
                created_at=orm_obj.created_at,
                updated_at=orm_obj.updated_at,
                updated_by=orm_obj.updated_by,
            )
        if isinstance(orm_obj, LLMProviderORM):
            return LLMProvider(
                id=orm_obj.id,
                provider_name=orm_obj.provider_name,
                provider_type=orm_obj.provider_type,
                base_url=orm_obj.base_url,
                api_key=orm_obj.api_key_encrypted,  # May need decryption
                api_key_hint=orm_obj.api_key_hint,
                default_model=orm_obj.default_model,
                available_models=orm_obj.available_models or [],
                model_aliases=orm_obj.model_aliases or {},
                supports_streaming=orm_obj.supports_streaming,
                supports_function_calling=orm_obj.supports_function_calling,
                supports_vision=orm_obj.supports_vision,
                max_tokens=orm_obj.max_tokens,
                max_context_length=orm_obj.max_context_length,
                rate_limit_requests_per_minute=orm_obj.rate_limit_requests_per_minute,
                rate_limit_tokens_per_minute=orm_obj.rate_limit_tokens_per_minute,
                is_enabled=orm_obj.is_enabled,
                is_default=orm_obj.is_default,
                priority=orm_obj.priority,
                extra_config=orm_obj.extra_config or {},
            )
        if isinstance(orm_obj, EmbeddingProviderORM):
            return EmbeddingProvider(
                id=orm_obj.id,
                provider_name=orm_obj.provider_name,
                provider_type=orm_obj.provider_type,
                base_url=orm_obj.base_url,
                api_key=orm_obj.api_key_encrypted,  # May need decryption
                api_key_hint=orm_obj.api_key_hint,
                model_name=orm_obj.default_model,
                dimensions=orm_obj.embedding_dimensions,
                available_models=orm_obj.available_models or [],
                is_enabled=orm_obj.is_enabled,
                is_default=orm_obj.is_default,
                priority=orm_obj.priority,
                extra_config=orm_obj.extra_config or {},
            )
        if isinstance(orm_obj, AgentConfigORM):
            return AgentConfig(
                id=orm_obj.id,
                agent_type=orm_obj.agent_type,
                agent_id=orm_obj.agent_id,
                config_name=orm_obj.config_name,
                config_data=orm_obj.config_data or {},
                llm_provider_id=orm_obj.llm_provider_id,
                embedding_provider_id=orm_obj.embedding_provider_id,
                is_active=orm_obj.is_active,
                is_default_for_type=orm_obj.is_default_for_type,
                description=orm_obj.description,
                tags=orm_obj.tags or [],
                created_at=orm_obj.created_at,
                updated_at=orm_obj.updated_at,
                created_by=orm_obj.created_by,
                updated_by=orm_obj.updated_by,
            )
        if isinstance(orm_obj, InfrastructureConfigORM):
            return InfrastructureConfig(
                id=orm_obj.id,
                service=InfrastructureService(orm_obj.service),
                host=orm_obj.host,
                port=orm_obj.port,
                connection_url=orm_obj.connection_url,
                is_enabled=orm_obj.is_enabled,
                health_status=orm_obj.health_status,
                last_health_check=orm_obj.last_health_check,
                health_check_latency_ms=orm_obj.health_check_latency_ms,
                health_check_error=orm_obj.health_check_error,
                extra_config=orm_obj.extra_config or {},
                created_at=orm_obj.created_at,
                updated_at=orm_obj.updated_at,
            )
        # For unknown types, try to return as-is or convert via dict
        if hasattr(orm_obj, "__dict__"):
            return orm_obj.__dict__
        return orm_obj

    # ====================================================================
    # .env Seeding
    # ====================================================================

    async def seed_from_env(self) -> SeedResult:
        """
        Seed LLM providers, embedding providers, and system configs from
        docker-compose environment variables. Idempotent — skips existing.
        Never raises — all exceptions are caught and logged as warnings.
        """
        result: SeedResult = {
            "providers_created": 0,
            "embedding_providers_created": 0,
            "configs_created": 0,
            "skipped_reasons": [],
        }

        try:
            await self._seed_llm_provider(result)
            await self._seed_embedding_provider(result)
            await self._seed_system_configs(result)
        except Exception as e:
            result["skipped_reasons"].append(f"seed_from_env failed: {e}")
            logger.warning("env_seeding_failed", reason=str(e))

        logger.info(
            "env_seeding_complete",
            providers_created=result["providers_created"],
            embedding_providers_created=result["embedding_providers_created"],
            configs_created=result["configs_created"],
            skipped_count=len(result["skipped_reasons"]),
        )
        return result

    async def _seed_llm_provider(self, result: SeedResult) -> None:
        """Seed the OpenAI LLM provider from env vars."""
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
            return

        llm_existing = await self.get_llm_provider_by_name("openai")
        if llm_existing:
            result["skipped_reasons"].append("LLM provider 'openai' already exists")
            return

        llm_model = os.environ.get("LLM_MODEL")
        api_key_hint = f"...{openai_key[-4:]}" if len(openai_key) >= 4 else openai_key
        extra_config = {"llm_model": llm_model} if llm_model else {}

        await self.create_llm_provider(
            LLMProviderCreate(
                provider_name="openai",
                provider_type=LLMProviderType.OPENAI,
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                api_key=openai_key,
                api_key_hint=api_key_hint,
                default_model=llm_model,
                is_default=True,
                extra_config=extra_config or None,
            ),
            user="env_seed",
        )
        result["providers_created"] += 1

    async def _seed_embedding_provider(self, result: SeedResult) -> None:
        """Seed the embedding provider from env vars."""
        emb_provider = os.environ.get("EMBEDDING_PROVIDER", "openai")
        emb_key = os.environ.get("EMBEDDING_API_KEY")
        if not emb_key:
            return

        emb_existing = await self.get_embedding_provider_by_name(emb_provider)
        if emb_existing:
            result["skipped_reasons"].append(
                f"Embedding provider '{emb_provider}' already exists"
            )
            return

        embedder_model = os.environ.get("EMBEDDER_MODEL")
        api_key_hint = f"...{emb_key[-4:]}" if len(emb_key) >= 4 else emb_key
        extra_config = {"embedder_model": embedder_model} if embedder_model else {}

        await self.create_embedding_provider(
            EmbeddingProviderCreate(
                provider_name=emb_provider,
                provider_type=EmbeddingProviderType.OPENAI_COMPATIBLE,
                base_url=os.environ.get("EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
                api_key=emb_key,
                api_key_hint=api_key_hint,
                default_model=embedder_model,
                is_default=True,
                extra_config=extra_config or None,
            ),
            user="env_seed",
        )
        result["embedding_providers_created"] += 1

    async def _seed_system_configs(self, result: SeedResult) -> None:
        """Seed system UserConfigurations from env vars."""
        system_configs = [
            ("environment", "ENVIRONMENT"),
            ("cors_origins", "CORS_ORIGINS"),
            ("rate_limit_enabled", "RATE_LIMIT_ENABLED"),
        ]
        for config_key, env_var in system_configs:
            raw = os.environ.get(env_var)
            if raw is None:
                continue
            try:
                config_existing = await self.get_config(config_key)
                if config_existing:
                    result["skipped_reasons"].append(
                        f"Config '{config_key}' already exists"
                    )
                else:
                    is_rate_limit = env_var == "RATE_LIMIT_ENABLED"
                    config_type = ConfigType.BOOLEAN if is_rate_limit else ConfigType.STRING
                    config_value: bool | str = (
                        raw.lower() in ("true", "1", "yes") if is_rate_limit else raw
                    )
                    await self.create_config(
                        UserConfigurationCreate(
                            config_key=config_key,
                            config_value=config_value,
                            config_type=config_type,
                            description=f"Seeded from {env_var} env var",
                            category="system",
                            is_sensitive=False,
                            is_editable=True,
                        ),
                        user="env_seed",
                    )
                    result["configs_created"] += 1
            except Exception as e:
                result["skipped_reasons"].append(
                    f"Failed to seed config '{config_key}': {e}"
                )


# =============================================================================
# Module-level convenience functions
# =============================================================================

_config_service: ConfigurationService | None = None


def get_config_service() -> ConfigurationService:
    """
    Get or create the global configuration service instance.

    Returns:
        The global ConfigurationService instance
    """
    global _config_service
    if _config_service is None:
        _config_service = ConfigurationService()
    return _config_service


async def initialize_config_service() -> None:
    """Initialize the global configuration service."""
    service = get_config_service()
    await service.initialize()


async def shutdown_config_service() -> None:
    """Shutdown the global configuration service."""
    global _config_service
    if _config_service is not None:
        await _config_service.shutdown()
        _config_service = None
