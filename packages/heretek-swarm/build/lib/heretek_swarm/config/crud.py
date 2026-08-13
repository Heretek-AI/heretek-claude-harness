"""
Configuration CRUD Operations

Contains CRUD operation mixins for ConfigurationService.
Each section handles a specific configuration domain.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from sqlalchemy import select

from .db_models import (
    AgentConfig as AgentConfigORM,
)
from .db_models import (
    EmbeddingProvider as EmbeddingProviderORM,
)
from .db_models import (
    LLMProvider as LLMProviderORM,
)
from .db_models import (
    UserConfiguration as UserConfigurationORM,
)
from .models import (
    AgentConfig,
    AgentConfigCreate,
    AgentConfigUpdate,
    ConfigAuditLog,
    ConfigType,
    EmbeddingProvider,
    EmbeddingProviderCreate,
    EmbeddingProviderUpdate,
    InfrastructureConfig,
    InfrastructureConfigCreate,
    InfrastructureConfigUpdate,
    LLMProvider,
    LLMProviderCreate,
    LLMProviderUpdate,
    UserConfiguration,
    UserConfigurationCreate,
    UserConfigurationUpdate,
    ConfigurationExport,
    ImportOptions,
    ImportResult,
)

if TYPE_CHECKING:
    from uuid import UUID

    from .service import ConfigurationService

# Import ORM models at module level
from .db_models import (
    InfrastructureConfig as InfrastructureConfigORM,
)

logger = structlog.get_logger("config.crud")


class ConfigurationServiceCrud:
    """
    Mixin class providing CRUD operations for ConfigurationService.

    This mixin provides all the database CRUD operations organized by domain:
    - User Configuration CRUD
    - LLM Provider CRUD
    - Embedding Provider CRUD
    - Agent Configuration CRUD
    - Audit Logging
    - Import/Export
    - Validation
    - Migration from .env
    """

    # These will be set by ConfigurationService.__init__
    _engine: Any
    _session_factory: Any
    _cache: dict[str, Any]
    _cache_ttl: Any
    _encryptor: Any
    _fernet: Any

    def _log_change(
        self: ConfigurationService,
        action: str,
        entity_type: str,
        entity_id: str | None,
        changes: dict[str, Any] | None,
        user: str | None,
    ) -> None:
        """Log a configuration change for audit purposes."""
        logger.info(
            "config_change",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            changes=changes,
            user=user,
        )

    # =====================================================================
    # User Configuration CRUD
    # =====================================================================

    async def get_config(
        self: ConfigurationService,
        config_key: str,
    ) -> UserConfiguration | None:
        """
        Get a user configuration by key.

        Args:
            config_key: The configuration key to retrieve

        Returns:
            UserConfiguration if found, None otherwise
        """
        # Check cache first
        cached = self._get_cache("config", config_key)
        if cached:
            return cached.get("value")

        async with self._session_factory() as session:
            result = await session.execute(
                select(UserConfigurationORM).where(UserConfigurationORM.config_key == config_key)
            )
            config = result.scalar_one_or_none()

            if config:
                pydantic = self._orm_to_pydantic(config)
                self._set_cache("config", config_key, pydantic)
                return pydantic
            return None

    async def get_config_value(
        self: ConfigurationService,
        config_key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a configuration value by key with a default.

        Args:
            config_key: The configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        config = await self.get_config(config_key)
        if config:
            return config.config_value
        return default

    async def list_configs(
        self: ConfigurationService,
        category: str | None = None,
        include_sensitive: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UserConfiguration]:
        """
        List configurations, optionally filtered by category.

        Args:
            category: Optional category filter
            include_sensitive: Whether to include sensitive configs
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of UserConfiguration objects
        """
        async with self._session_factory() as session:
            query = select(UserConfigurationORM)
            if category:
                query = query.where(UserConfigurationORM.category == category)
            if not include_sensitive:
                query = query.where(UserConfigurationORM.is_sensitive == False)  # noqa: E712

            result = await session.execute(
                query.order_by(UserConfigurationORM.category).limit(limit).offset(offset)
            )
            configs = result.scalars().all()
            return [self._orm_to_pydantic(c) for c in configs]

    async def create_config(
        self: ConfigurationService,
        config: UserConfigurationCreate,
        user: str | None = None,
    ) -> UserConfiguration:
        """
        Create a new user configuration.

        Args:
            config: Configuration data
            user: User creating the config

        Returns:
            Created UserConfiguration
        """
        async with self._session_factory() as session:
            orm_obj = UserConfigurationORM(
                config_key=config.config_key,
                config_value=config.config_value,
                config_type=config.config_type,
                description=config.description,
                category=config.category,
                is_sensitive=config.is_sensitive,
                is_editable=config.is_editable,
                validation_schema=config.validation_schema,
                created_by=user,
                updated_by=user,
            )
            session.add(orm_obj)
            await session.commit()
            await session.refresh(orm_obj)

            self._log_change("create", "user_configuration", str(orm_obj.id), None, user)
            return self._orm_to_pydantic(orm_obj)

    async def update_config(
        self: ConfigurationService,
        config_key: str,
        updates: UserConfigurationUpdate,
        user: str | None = None,
    ) -> UserConfiguration | None:
        """
        Update an existing user configuration.

        Args:
            config_key: Key of config to update
            updates: Update data
            user: User making the update

        Returns:
            Updated UserConfiguration or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserConfigurationORM).where(UserConfigurationORM.config_key == config_key)
            )
            config = result.scalar_one_or_none()

            if not config:
                return None

            if not config.is_editable:
                raise ValueError(f"Configuration '{config_key}' is not editable")

            changes = {}
            update_data = updates.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if getattr(config, key) != value:
                    changes[key] = {"old": getattr(config, key), "new": value}
                    setattr(config, key, value)

            config.updated_by = user
            await session.commit()
            await session.refresh(config)

            self._invalidate_cache("config", config_key)
            self._log_change("update", "user_configuration", str(config.id), changes, user)
            return self._orm_to_pydantic(config)

    async def delete_config(
        self: ConfigurationService,
        config_key: str,
        user: str | None = None,
    ) -> bool:
        """
        Delete a user configuration.

        Args:
            config_key: Key of config to delete
            user: User making the deletion

        Returns:
            True if deleted, False if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserConfigurationORM).where(UserConfigurationORM.config_key == config_key)
            )
            config = result.scalar_one_or_none()

            if not config:
                return False

            if not config.is_editable:
                raise ValueError(f"Configuration '{config_key}' is not editable")

            await session.delete(config)
            await session.commit()

            self._invalidate_cache("config", config_key)
            self._log_change("delete", "user_configuration", str(config.id), None, user)
            return True

    # =====================================================================
    # LLM Provider CRUD
    # =====================================================================

    async def get_llm_provider(
        self: ConfigurationService,
        provider_id: UUID,
    ) -> LLMProvider | None:
        """
        Get an LLM provider by ID.

        Args:
            provider_id: Provider UUID

        Returns:
            LLMProvider if found, None otherwise
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(LLMProviderORM).where(LLMProviderORM.id == provider_id)
            )
            provider = result.scalar_one_or_none()
            return self._orm_to_pydantic(provider) if provider else None

    async def get_llm_provider_by_name(
        self: ConfigurationService,
        provider_name: str,
    ) -> LLMProvider | None:
        """
        Get an LLM provider by name.

        Args:
            provider_name: Provider name

        Returns:
            LLMProvider if found, None otherwise
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(LLMProviderORM).where(LLMProviderORM.provider_name == provider_name)
            )
            provider = result.scalar_one_or_none()
            return self._orm_to_pydantic(provider) if provider else None

    async def list_llm_providers(
        self: ConfigurationService,
        include_disabled: bool = False,
    ) -> list[LLMProvider]:
        """
        List all LLM providers.

        Args:
            include_disabled: Whether to include disabled providers

        Returns:
            List of LLMProvider objects
        """
        async with self._session_factory() as session:
            query = select(LLMProviderORM)
            if not include_disabled:
                query = query.where(LLMProviderORM.is_enabled == True)  # noqa: E712
            result = await session.execute(query.order_by(LLMProviderORM.priority))
            providers = result.scalars().all()
            return [self._orm_to_pydantic(p) for p in providers]

    async def get_default_llm_provider(self: ConfigurationService) -> LLMProvider | None:
        """
        Get the default LLM provider.

        Returns:
            Default LLMProvider or None if none set
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(LLMProviderORM).where(LLMProviderORM.is_default == True)  # noqa: E712
            )
            provider = result.scalar_one_or_none()
            return self._orm_to_pydantic(provider) if provider else None

    def _encrypt_extra_config(
        self: ConfigurationService,
        extra_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Encrypt sensitive values in extra config."""
        if not extra_config:
            return {}
        encrypted = {}
        for key, value in extra_config.items():
            if isinstance(value, str) and key.lower() in ("api_key", "secret", "token"):
                encrypted[key] = self._encryptor.encrypt(value)
            else:
                encrypted[key] = value
        return encrypted

    def _decrypt_extra_config(
        self: ConfigurationService,
        extra_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Decrypt sensitive values in extra config."""
        if not extra_config:
            return {}
        decrypted = {}
        for key, value in extra_config.items():
            if isinstance(value, str) and key.lower() in ("api_key", "secret", "token"):
                try:
                    decrypted[key] = self._encryptor.decrypt(value)
                except Exception:
                    decrypted[key] = value
            else:
                decrypted[key] = value
        return decrypted

    async def create_llm_provider(
        self: ConfigurationService,
        provider: LLMProviderCreate,
        user: str | None = None,
    ) -> LLMProvider:
        """
        Create a new LLM provider.

        Args:
            provider: Provider data
            user: User creating the provider

        Returns:
            Created LLMProvider
        """
        async with self._session_factory() as session:
            # Encrypt API key if provided
            api_key_encrypted = None
            if provider.api_key:
                api_key_encrypted = self._encryptor.encrypt(provider.api_key)

            # Encrypt sensitive extra config values
            extra_config = self._encrypt_extra_config(provider.extra_config or {})

            orm_obj = LLMProviderORM(
                provider_name=provider.provider_name,
                provider_type=provider.provider_type,
                base_url=provider.base_url,
                api_key_encrypted=api_key_encrypted,
                api_key_hint=provider.api_key_hint,
                default_model=provider.default_model,
                available_models=provider.available_models,
                model_aliases=provider.model_aliases,
                supports_streaming=provider.supports_streaming,
                supports_function_calling=provider.supports_function_calling,
                supports_vision=provider.supports_vision,
                max_tokens=provider.max_tokens,
                max_context_length=provider.max_context_length,
                rate_limit_requests_per_minute=provider.rate_limit_requests_per_minute,
                rate_limit_tokens_per_minute=provider.rate_limit_tokens_per_minute,
                is_enabled=provider.is_enabled,
                is_default=provider.is_default,
                priority=provider.priority,
                extra_config=extra_config,
            )
            session.add(orm_obj)
            await session.commit()
            await session.refresh(orm_obj)

            self._log_change("create", "llm_provider", str(orm_obj.id), None, user)
            return self._orm_to_pydantic(orm_obj)

    async def update_llm_provider(
        self: ConfigurationService,
        provider_id: UUID,
        updates: LLMProviderUpdate,
        user: str | None = None,
    ) -> LLMProvider | None:
        """
        Update an existing LLM provider.

        Args:
            provider_id: ID of provider to update
            updates: Update data
            user: User making the update

        Returns:
            Updated LLMProvider or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(LLMProviderORM).where(LLMProviderORM.id == provider_id)
            )
            provider = result.scalar_one_or_none()

            if not provider:
                return None

            changes = {}
            update_data = updates.model_dump(exclude_unset=True)

            # Handle API key separately (encrypt new key)
            if update_data.get("api_key"):
                update_data["api_key_encrypted"] = self._encryptor.encrypt(
                    update_data.pop("api_key")
                )

            # Handle extra_config encryption
            if "extra_config" in update_data:
                update_data["extra_config"] = self._encrypt_extra_config(
                    update_data["extra_config"]
                )

            for key, value in update_data.items():
                if key == "api_key":
                    continue  # Already handled above
                if getattr(provider, key, None) != value:
                    changes[key] = {"old": getattr(provider, key), "new": value}
                    setattr(provider, key, value)

            await session.commit()
            await session.refresh(provider)

            self._log_change("update", "llm_provider", str(provider.id), changes, user)
            return self._orm_to_pydantic(provider)

    async def delete_llm_provider(
        self: ConfigurationService,
        provider_id: UUID,
        user: str | None = None,
    ) -> bool:
        """
        Delete an LLM provider.

        Args:
            provider_id: ID of provider to delete
            user: User making the deletion

        Returns:
            True if deleted, False if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(LLMProviderORM).where(LLMProviderORM.id == provider_id)
            )
            provider = result.scalar_one_or_none()

            if not provider:
                return False

            await session.delete(provider)
            await session.commit()

            self._log_change("delete", "llm_provider", str(provider.id), None, user)
            return True

    def get_llm_provider_api_key(
        self: ConfigurationService,
        provider: LLMProvider,
    ) -> str | None:
        """
        Decrypt and return the API key for an LLM provider.

        Args:
            provider: LLMProvider object

        Returns:
            Decrypted API key or None
        """
        if not provider.api_key:
            return None
        try:
            return self._encryptor.decrypt(provider.api_key)
        except Exception:
            return None

    # =====================================================================
    # Embedding Provider CRUD
    # =====================================================================

    async def get_embedding_provider(
        self: ConfigurationService,
        provider_id: UUID,
    ) -> EmbeddingProvider | None:
        """
        Get an embedding provider by ID.

        Args:
            provider_id: Provider UUID

        Returns:
            EmbeddingProvider if found, None otherwise
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmbeddingProviderORM).where(EmbeddingProviderORM.id == provider_id)
            )
            provider = result.scalar_one_or_none()
            return self._orm_to_pydantic(provider) if provider else None

    async def get_embedding_provider_by_name(
        self: ConfigurationService,
        provider_name: str,
    ) -> EmbeddingProvider | None:
        """
        Get an embedding provider by name.

        Args:
            provider_name: Provider name

        Returns:
            EmbeddingProvider if found, None otherwise
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmbeddingProviderORM).where(
                    EmbeddingProviderORM.provider_name == provider_name
                )
            )
            provider = result.scalar_one_or_none()
            return self._orm_to_pydantic(provider) if provider else None

    async def list_embedding_providers(
        self: ConfigurationService,
        include_disabled: bool = False,
    ) -> list[EmbeddingProvider]:
        """
        List all embedding providers.

        Args:
            include_disabled: Whether to include disabled providers

        Returns:
            List of EmbeddingProvider objects
        """
        async with self._session_factory() as session:
            query = select(EmbeddingProviderORM)
            if not include_disabled:
                query = query.where(EmbeddingProviderORM.is_enabled == True)  # noqa: E712
            result = await session.execute(query.order_by(EmbeddingProviderORM.priority))
            providers = result.scalars().all()
            return [self._orm_to_pydantic(p) for p in providers]

    async def get_default_embedding_provider(
        self: ConfigurationService,
    ) -> EmbeddingProvider | None:
        """
        Get the default embedding provider.

        Returns:
            Default EmbeddingProvider or None if none set
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmbeddingProviderORM).where(
                    EmbeddingProviderORM.is_default == True  # noqa: E712
                )
            )
            provider = result.scalar_one_or_none()
            return self._orm_to_pydantic(provider) if provider else None

    async def create_embedding_provider(
        self: ConfigurationService,
        provider: EmbeddingProviderCreate,
        user: str | None = None,
    ) -> EmbeddingProvider:
        """
        Create a new embedding provider.

        Args:
            provider: Provider data
            user: User creating the provider

        Returns:
            Created EmbeddingProvider
        """
        async with self._session_factory() as session:
            # Encrypt API key if provided
            api_key_encrypted = None
            if provider.api_key:
                api_key_encrypted = self._encryptor.encrypt(provider.api_key)

            orm_obj = EmbeddingProviderORM(
                provider_name=provider.provider_name,
                provider_type=provider.provider_type,
                base_url=provider.base_url,
                api_key_encrypted=api_key_encrypted,
                api_key_hint=provider.api_key_hint,
                default_model=provider.default_model,
                embedding_dimensions=provider.embedding_dimensions,
                available_models=provider.available_models,
                is_enabled=provider.is_enabled,
                is_default=provider.is_default,
                priority=provider.priority,
                extra_config=self._encrypt_extra_config(provider.extra_config or {}),
            )
            session.add(orm_obj)
            await session.commit()
            await session.refresh(orm_obj)

            self._log_change("create", "embedding_provider", str(orm_obj.id), None, user)
            return self._orm_to_pydantic(orm_obj)

    async def update_embedding_provider(
        self: ConfigurationService,
        provider_id: UUID,
        updates: EmbeddingProviderUpdate,
        user: str | None = None,
    ) -> EmbeddingProvider | None:
        """
        Update an existing embedding provider.

        Args:
            provider_id: ID of provider to update
            updates: Update data
            user: User making the update

        Returns:
            Updated EmbeddingProvider or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmbeddingProviderORM).where(EmbeddingProviderORM.id == provider_id)
            )
            provider = result.scalar_one_or_none()

            if not provider:
                return None

            changes = {}
            update_data = updates.model_dump(exclude_unset=True)

            # Handle API key separately (encrypt new key)
            if update_data.get("api_key"):
                update_data["api_key_encrypted"] = self._encryptor.encrypt(
                    update_data.pop("api_key")
                )

            for key, value in update_data.items():
                if key == "api_key":
                    continue
                if getattr(provider, key, None) != value:
                    changes[key] = {"old": getattr(provider, key), "new": value}
                    setattr(provider, key, value)

            await session.commit()
            await session.refresh(provider)

            self._log_change("update", "embedding_provider", str(provider.id), changes, user)
            return self._orm_to_pydantic(provider)

    async def delete_embedding_provider(
        self: ConfigurationService,
        provider_id: UUID,
        user: str | None = None,
    ) -> bool:
        """
        Delete an embedding provider.

        Args:
            provider_id: ID of provider to delete
            user: User making the deletion

        Returns:
            True if deleted, False if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EmbeddingProviderORM).where(EmbeddingProviderORM.id == provider_id)
            )
            provider = result.scalar_one_or_none()

            if not provider:
                return False

            await session.delete(provider)
            await session.commit()

            self._log_change("delete", "embedding_provider", str(provider.id), None, user)
            return True

    def get_embedding_provider_api_key(
        self: ConfigurationService,
        provider: EmbeddingProvider,
    ) -> str | None:
        """
        Decrypt and return the API key for an embedding provider.

        Args:
            provider: EmbeddingProvider object

        Returns:
            Decrypted API key or None
        """
        if not provider.api_key:
            return None
        try:
            return self._encryptor.decrypt(provider.api_key)
        except Exception:
            return None

    # =====================================================================
    # Agent Configuration CRUD
    # =====================================================================

    async def get_agent_config(
        self: ConfigurationService,
        config_id: UUID,
    ) -> AgentConfig | None:
        """
        Get an agent configuration by ID.

        Args:
            config_id: Configuration UUID

        Returns:
            AgentConfig if found, None otherwise
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentConfigORM).where(AgentConfigORM.id == config_id)
            )
            config = result.scalar_one_or_none()
            return self._orm_to_pydantic(config) if config else None

    async def get_agent_config_by_type(
        self: ConfigurationService,
        agent_type: str,
        agent_id: str | None = None,
    ) -> AgentConfig | None:
        """
        Get an agent configuration by type.

        Args:
            agent_type: Type of agent
            agent_id: Optional specific agent ID

        Returns:
            AgentConfig if found, None otherwise
        """
        async with self._session_factory() as session:
            query = select(AgentConfigORM).where(AgentConfigORM.agent_type == agent_type)
            if agent_id:
                query = query.where(AgentConfigORM.agent_id == agent_id)
            result = await session.execute(query)
            config = result.scalar_one_or_none()
            return self._orm_to_pydantic(config) if config else None

    async def list_agent_configs(
        self: ConfigurationService,
        agent_type: str | None = None,
        include_inactive: bool = False,
    ) -> list[AgentConfig]:
        """
        List agent configurations.

        Args:
            agent_type: Optional type filter
            include_inactive: Whether to include inactive configs

        Returns:
            List of AgentConfig objects
        """
        async with self._session_factory() as session:
            query = select(AgentConfigORM)
            if agent_type:
                query = query.where(AgentConfigORM.agent_type == agent_type)
            if not include_inactive:
                query = query.where(AgentConfigORM.is_active == True)  # noqa: E712
            result = await session.execute(query.order_by(AgentConfigORM.agent_type))
            configs = result.scalars().all()
            return [self._orm_to_pydantic(c) for c in configs]

    async def create_agent_config(
        self: ConfigurationService,
        config: AgentConfigCreate,
        user: str | None = None,
    ) -> AgentConfig:
        """
        Create a new agent configuration.

        Args:
            config: Configuration data
            user: User creating the config

        Returns:
            Created AgentConfig
        """
        async with self._session_factory() as session:
            orm_obj = AgentConfigORM(
                agent_type=config.agent_type,
                agent_id=config.agent_id,
                config_name=config.config_name,
                config_data=config.config_data,
                llm_provider_id=config.llm_provider_id,
                embedding_provider_id=config.embedding_provider_id,
                is_active=config.is_active,
                is_default_for_type=config.is_default_for_type,
                description=config.description,
                tags=config.tags,
                created_by=user,
                updated_by=user,
            )
            session.add(orm_obj)
            await session.commit()
            await session.refresh(orm_obj)

            self._log_change("create", "agent_config", str(orm_obj.id), None, user)
            return self._orm_to_pydantic(orm_obj)

    async def update_agent_config(
        self: ConfigurationService,
        config_id: UUID,
        updates: AgentConfigUpdate,
        user: str | None = None,
    ) -> AgentConfig | None:
        """
        Update an existing agent configuration.

        Args:
            config_id: ID of config to update
            updates: Update data
            user: User making the update

        Returns:
            Updated AgentConfig or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentConfigORM).where(AgentConfigORM.id == config_id)
            )
            config = result.scalar_one_or_none()

            if not config:
                return None

            changes = {}
            update_data = updates.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if getattr(config, key, None) != value:
                    changes[key] = {"old": getattr(config, key), "new": value}
                    setattr(config, key, value)

            config.updated_by = user
            await session.commit()
            await session.refresh(config)

            self._log_change("update", "agent_config", str(config.id), changes, user)
            return self._orm_to_pydantic(config)

    async def delete_agent_config(
        self: ConfigurationService,
        config_id: UUID,
        user: str | None = None,
    ) -> bool:
        """
        Delete an agent configuration.

        Args:
            config_id: ID of config to delete
            user: User making the deletion

        Returns:
            True if deleted, False if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentConfigORM).where(AgentConfigORM.id == config_id)
            )
            config = result.scalar_one_or_none()

            if not config:
                return False

            await session.delete(config)
            await session.commit()

            self._log_change("delete", "agent_config", str(config.id), None, user)
            return True

    # =====================================================================
    # Audit Logging
    # =====================================================================

    async def get_audit_log(
        self: ConfigurationService,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
    ) -> list[ConfigAuditLog]:
        """
        Get audit log entries.

        Args:
            entity_type: Optional entity type filter
            entity_id: Optional entity ID filter
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        logger.info(
            "audit_log_requested",
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )
        return []

    # =====================================================================
    # Import/Export
    # =====================================================================

    async def export_configurations(
        self: ConfigurationService,
        config_type: ConfigType | None = None,  # noqa: ARG002
        include_sensitive: bool = False,
        exported_by: str | None = None,
    ) -> ConfigurationExport:
        """
        Export configurations.

        Args:
            config_type: Optional type filter
            include_sensitive: Whether to include sensitive data
            exported_by: User performing the export

        Returns:
            ConfigurationExport bundle
        """
        llm_providers = await self.list_llm_providers(include_disabled=True)
        embedding_providers = await self.list_embedding_providers(include_disabled=True)
        agent_configs = await self.list_agent_configs(include_disabled=True)
        user_configs = await self.list_configs(include_sensitive=include_sensitive)

        if not include_sensitive:
            for provider in llm_providers:
                provider.api_key = None
            for provider in embedding_providers:
                provider.api_key = None

        return ConfigurationExport(
            exported_by=exported_by,
            user_configurations=user_configs,
            llm_providers=llm_providers,
            embedding_providers=embedding_providers,
            agent_configs=agent_configs,
        )

    async def import_configurations(
        self: ConfigurationService,
        import_data: Any,
        options: ImportOptions | None = None,
        user: str | None = None,  # noqa: ARG002
    ) -> ImportResult:
        """
        Import configurations.

        Args:
            import_data: Data to import (ConfigurationImport or dict)
            options: Import options
            user: User performing import

        Returns:
            ImportResult
        """
        _ = user
        opts = options or ImportOptions()
        payload = import_data.model_dump() if hasattr(import_data, "model_dump") else import_data
        imported: dict[str, int] = {
            "user_configurations": 0, "llm_providers": 0,
            "embedding_providers": 0, "agent_configs": 0,
        }
        errors: list[str] = []

        if opts.import_llm_providers and payload.get("llm_providers"):
            await self._import_rows(
                payload["llm_providers"], LLMProviderCreate,
                self.create_llm_provider, imported, "llm_providers", errors, user,
            )

        if opts.import_embedding_providers and payload.get("embedding_providers"):
            await self._import_rows(
                payload["embedding_providers"], EmbeddingProviderCreate,
                self.create_embedding_provider, imported, "embedding_providers", errors, user,
            )

        if opts.import_agent_configs and payload.get("agent_configs"):
            await self._import_rows(
                payload["agent_configs"], AgentConfigCreate,
                self.create_agent_config, imported, "agent_configs", errors, user,
            )

        if opts.import_user_configs and payload.get("user_configurations"):
            await self._import_rows(
                payload["user_configurations"], UserConfigurationCreate,
                self.create_config, imported, "user_configurations", errors, user,
            )

        return ImportResult(
            success=len(errors) == 0,
            imported_count=imported,
            errors=errors,
        )

    async def _import_rows(
        self: ConfigurationService,
        rows: list[dict[str, Any]],
        create_type: type,
        create_fn: callable,
        imported: dict[str, int],
        key: str,
        errors: list[str],
        user: str | None,
    ) -> None:
        """Import a list of rows using the given create function."""
        label = key.rstrip("s")  # "llm_providers" -> "llm_provider"
        for row in rows:
            try:
                await create_fn(create_type(**row), user=user)
                imported[key] += 1
            except Exception as e:
                errors.append(f"{label}: {e}")

        return ImportResult(
            success=len(errors) == 0,
            imported_count=imported,
            errors=errors,
        )

    # =====================================================================
    # Validation
    # =====================================================================

    # Mapping from config_type to (expected_type_or_tuple, error_message)
    _TYPE_CHECKS: ClassVar[dict[str, tuple[type | tuple[type, ...], str]]] = {
        "integer": (int, "Value must be an integer"),
        "float": ((int, float), "Value must be a number"),
        "boolean": (bool, "Value must be a boolean"),
        "json": (dict, "Value must be a JSON object"),
    }

    def _validate_config_value(
        self: ConfigurationService,
        config_type: str,
        value: Any,
        validation_schema: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Validate a configuration value.

        Args:
            config_type: Type of configuration
            value: Value to validate
            validation_schema: Optional validation schema

        Returns:
            Tuple of (is_valid, error_message)
        """
        if validation_schema:
            return True, None

        type_check = self._TYPE_CHECKS.get(config_type)
        if type_check is None:
            return True, None

        expected_type, error_msg = type_check
        if not isinstance(value, expected_type):
            return False, error_msg

        return True, None

    # =====================================================================
    # Migration from .env
    # =====================================================================

    async def _migrate_single_env_var(
        self: ConfigurationService,
        key: str,
        value: str,
        config_key: str,
        category: str,
        user: str | None,
    ) -> None:
        """Migrate a single environment variable to database config."""
        await self.create_config(
            UserConfigurationCreate(
                config_key=config_key,
                config_value=value,
                config_type="string",
                category=category,
                description=f"Migrated from {key}",
                is_sensitive=False,
                is_editable=True,
            ),
            user=user,
        )

    async def migrate_from_env(
        self: ConfigurationService,
        prefix: str = "APP_",
        category: str = "environment",
        user: str | None = None,
    ) -> dict[str, Any]:
        """
        Migrate configuration from environment variables.

        Args:
            prefix: Environment variable prefix to migrate
            category: Category for migrated configs
            user: User performing migration

        Returns:
            Migration result
        """
        migrated_count = 0
        skipped_count = 0
        errors: list[str] = []

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            config_key = key[len(prefix):].lower()
            try:
                await self._migrate_single_env_var(key, value, config_key, category, user)
                migrated_count += 1
            except Exception as e:
                errors.append(f"{key}: {e}")
                skipped_count += 1

        return {
            "migrated": migrated_count,
            "skipped": skipped_count,
            "errors": errors,
        }

    # =====================================================================
    # Infrastructure Configuration CRUD
    # =====================================================================

    async def get_infrastructure_config(
        self: ConfigurationService,
        config_id: UUID,
    ) -> InfrastructureConfig | None:
        """
        Get infrastructure configuration by ID.

        Args:
            config_id: Configuration UUID

        Returns:
            InfrastructureConfig if found, None otherwise
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(InfrastructureConfigORM).where(InfrastructureConfigORM.id == config_id)
            )
            config = result.scalar_one_or_none()
            return self._orm_to_pydantic(config) if config else None

    async def get_infrastructure_config_by_service(
        self: ConfigurationService,
        service: str,
    ) -> InfrastructureConfig | None:
        """
        Get infrastructure configuration by service type.

        Args:
            service: Infrastructure service type (postgres, redis, qdrant, nats, mem0)

        Returns:
            InfrastructureConfig if found, None otherwise
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(InfrastructureConfigORM).where(
                    InfrastructureConfigORM.service == service
                )
            )
            config = result.scalar_one_or_none()
            return self._orm_to_pydantic(config) if config else None

    async def list_infrastructure_configs(
        self: ConfigurationService,
        include_disabled: bool = False,
    ) -> list[InfrastructureConfig]:
        """
        List all infrastructure configurations.

        Args:
            include_disabled: Whether to include disabled configs

        Returns:
            List of InfrastructureConfig objects
        """
        async with self._session_factory() as session:
            query = select(InfrastructureConfigORM)
            if not include_disabled:
                query = query.where(InfrastructureConfigORM.is_enabled == True)  # noqa: E712
            result = await session.execute(query.order_by(InfrastructureConfigORM.service))
            configs = result.scalars().all()
            return [self._orm_to_pydantic(c) for c in configs]

    async def create_infrastructure_config(
        self: ConfigurationService,
        config: InfrastructureConfigCreate,
        user: str | None = None,
    ) -> InfrastructureConfig:
        """
        Create a new infrastructure configuration.

        Args:
            config: Configuration data
            user: User creating the config

        Returns:
            Created InfrastructureConfig
        """
        async with self._session_factory() as session:
            orm_obj = InfrastructureConfigORM(
                service=config.service,
                host=config.host,
                port=config.port,
                connection_url=config.connection_url,
                is_enabled=config.is_enabled,
                extra_config=config.extra_config or {},
            )
            session.add(orm_obj)
            await session.commit()
            await session.refresh(orm_obj)

            self._log_change("create", "infrastructure_config", str(orm_obj.id), None, user)
            return self._orm_to_pydantic(orm_obj)

    async def update_infrastructure_config(
        self: ConfigurationService,
        config_id: UUID,
        updates: InfrastructureConfigUpdate,
        user: str | None = None,
    ) -> InfrastructureConfig | None:
        """
        Update an existing infrastructure configuration.

        Args:
            config_id: ID of config to update
            updates: Update data
            user: User making the update

        Returns:
            Updated InfrastructureConfig or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(InfrastructureConfigORM).where(InfrastructureConfigORM.id == config_id)
            )
            config = result.scalar_one_or_none()

            if not config:
                return None

            changes = {}
            update_data = updates.model_dump(exclude_unset=True)

            for key, value in update_data.items():
                if getattr(config, key, None) != value:
                    changes[key] = {"old": getattr(config, key), "new": value}
                    setattr(config, key, value)

            await session.commit()
            await session.refresh(config)

            self._log_change("update", "infrastructure_config", str(config.id), changes, user)
            return self._orm_to_pydantic(config)

    async def delete_infrastructure_config(
        self: ConfigurationService,
        config_id: UUID,
        user: str | None = None,
    ) -> bool:
        """
        Delete an infrastructure configuration.

        Args:
            config_id: ID of config to delete
            user: User making the deletion

        Returns:
            True if deleted, False if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(InfrastructureConfigORM).where(InfrastructureConfigORM.id == config_id)
            )
            config = result.scalar_one_or_none()

            if not config:
                return False

            await session.delete(config)
            await session.commit()

            self._log_change("delete", "infrastructure_config", str(config.id), None, user)
            return True

    async def update_infrastructure_health(
        self: ConfigurationService,
        config_id: UUID,
        health_status: str,
        latency_ms: float | None,
        error: str | None = None,
    ) -> InfrastructureConfig | None:
        """
        Update infrastructure health check results.

        Args:
            config_id: ID of config to update
            health_status: Health status (healthy, unhealthy, degraded)
            latency_ms: Health check latency in milliseconds
            error: Error message if unhealthy

        Returns:
            Updated InfrastructureConfig or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(InfrastructureConfigORM).where(InfrastructureConfigORM.id == config_id)
            )
            config = result.scalar_one_or_none()

            if not config:
                return None

            config.health_status = health_status
            config.last_health_check = datetime.now(UTC)
            config.health_check_latency_ms = latency_ms
            config.health_check_error = error

            await session.commit()
            await session.refresh(config)

            return self._orm_to_pydantic(config)
