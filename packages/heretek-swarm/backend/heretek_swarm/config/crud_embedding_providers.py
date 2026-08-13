"""
Embedding provider CRUD — extracted from ``config/crud.py``
as part of Phase 2.6 of PLAN.md (§1.4 god-class extraction).

The audit's recommendation was to split
``config/crud.py`` (1,438 LOC) into per-entity modules:
``crud/{user,llm_providers,embedding_providers,agent_configs,
infrastructure,audit,import_export}.py``.

This commit ships the embedding_providers module. The
methods here are the same logic as the original
``ConfigurationServiceCrud`` methods, expressed as free
functions that take the service instance as their first
argument. The mixin class still owns the public method
surface; the methods now delegate here.

Backwards compatibility: ``ConfigurationServiceCrud`` keeps
the same public method signatures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from .service import ConfigurationService

from .db_models import EmbeddingProvider as EmbeddingProviderORM
from .models import (
    EmbeddingProvider,
    EmbeddingProviderCreate,
    EmbeddingProviderUpdate,
)


def _row_to_embedding_provider(row: EmbeddingProviderORM) -> EmbeddingProvider:
    """Convert a SQLAlchemy row to a Pydantic EmbeddingProvider."""
    return EmbeddingProvider(
        id=row.id,
        name=row.name,
        provider_type=row.provider_type,
        model=row.model,
        api_key=row.api_key,
        base_url=row.base_url,
        dimensions=row.dimensions,
        enabled=row.enabled,
        is_default=row.is_default,
        extra_config=row.extra_config or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def get_embedding_provider(
    service: "ConfigurationService",
    provider_id: UUID,
) -> EmbeddingProvider | None:
    """Fetch an embedding provider by primary key."""
    async with service.session_factory() as session:
        row = await session.get(EmbeddingProviderORM, provider_id)
        if row is None:
            return None
        return _row_to_embedding_provider(row)


async def get_embedding_provider_by_name(
    service: "ConfigurationService",
    name: str,
) -> EmbeddingProvider | None:
    """Fetch an embedding provider by its unique name."""
    from sqlalchemy import select

    async with service.session_factory() as session:
        stmt = select(EmbeddingProviderORM).where(EmbeddingProviderORM.name == name)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_embedding_provider(row)


async def list_embedding_providers(
    service: "ConfigurationService",
    include_disabled: bool = False,
) -> list[EmbeddingProvider]:
    """List all embedding providers, optionally including disabled ones."""
    from sqlalchemy import select

    async with service.session_factory() as session:
        stmt = select(EmbeddingProviderORM)
        if not include_disabled:
            stmt = stmt.where(EmbeddingProviderORM.enabled.is_(True))
        rows = (await session.execute(stmt)).scalars().all()
        return [_row_to_embedding_provider(r) for r in rows]


async def create_embedding_provider(
    service: "ConfigurationService",
    provider: EmbeddingProviderCreate,
    *,
    user: str | None = None,
) -> EmbeddingProvider:
    """Create a new embedding provider."""
    async with service.session_factory() as session:
        row = EmbeddingProviderORM(
            id=provider.id or __import__("uuid").uuid4(),
            name=provider.name,
            provider_type=provider.provider_type,
            model=provider.model,
            api_key=provider.api_key,
            base_url=provider.base_url,
            dimensions=provider.dimensions,
            enabled=provider.enabled,
            is_default=provider.is_default,
            extra_config=provider.extra_config or {},
        )
        session.add(row)
        await session.commit()
    return await get_embedding_provider(service, row.id)


async def update_embedding_provider(
    service: "ConfigurationService",
    provider_id: UUID,
    update: EmbeddingProviderUpdate,
    *,
    user: str | None = None,
) -> EmbeddingProvider | None:
    """Update an existing embedding provider."""
    async with service.session_factory() as session:
        row = await session.get(EmbeddingProviderORM, provider_id)
        if row is None:
            return None
        if update.model is not None:
            row.model = update.model
        if update.api_key is not None:
            row.api_key = update.api_key
        if update.base_url is not None:
            row.base_url = update.base_url
        if update.dimensions is not None:
            row.dimensions = update.dimensions
        if update.enabled is not None:
            row.enabled = update.enabled
        if update.is_default is not None:
            row.is_default = update.is_default
        if update.extra_config is not None:
            row.extra_config = update.extra_config
        await session.commit()
    return await get_embedding_provider(service, provider_id)


async def delete_embedding_provider(
    service: "ConfigurationService",
    provider_id: UUID,
    *,
    user: str | None = None,
) -> bool:
    """Delete an embedding provider."""
    async with service.session_factory() as session:
        row = await session.get(EmbeddingProviderORM, provider_id)
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
    return True


def get_embedding_provider_api_key(
    service: "ConfigurationService",
    provider: EmbeddingProvider,
) -> str | None:
    """Decrypt and return the API key for ``provider``."""
    if not provider.api_key:
        return None
    decrypt = getattr(service, "_decrypt_secret", None)
    if callable(decrypt):
        try:
            return str(decrypt(provider.api_key))
        except Exception:
            return provider.api_key
    return provider.api_key


__all__ = [
    "create_embedding_provider",
    "delete_embedding_provider",
    "get_default_embedding_provider",
    "get_embedding_provider",
    "get_embedding_provider_api_key",
    "get_embedding_provider_by_name",
    "list_embedding_providers",
    "update_embedding_provider",
]
