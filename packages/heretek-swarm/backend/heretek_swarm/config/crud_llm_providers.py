"""
LLM provider CRUD — extracted from ``config/crud.py``
as part of Phase 2.6 of PLAN.md (§1.4 god-class extraction).

The audit specifically called out per-entity extraction as the
path forward: ``crud/{llm_providers,embedding_providers,
agent_configs,infrastructure,audit,import_export}.py``.
This commit ships the LLM provider module.

The functions here are the same logic as the original
``ConfigurationServiceCrud`` methods, expressed as free
functions that take the service instance as their first
argument. The mixin class still owns the public method
surface; the methods now delegate here.

Backwards compatibility: ``ConfigurationServiceCrud`` keeps
the same public method signatures. New code can call these
free functions directly when it has a service instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .service import ConfigurationService

from .db_models import LLMProvider as LLMProviderORM
from .models import LLMProvider, LLMProviderCreate, LLMProviderUpdate


async def get_llm_provider(
    service: "ConfigurationService",
    provider_id: str,
) -> LLMProvider | None:
    """Fetch an LLM provider by primary key."""
    async with service.session_factory() as session:
        row = await session.get(LLMProviderORM, provider_id)
        if row is None:
            return None
        return _row_to_llm_provider(row)


async def get_llm_provider_by_name(
    service: "ConfigurationService",
    name: str,
) -> LLMProvider | None:
    """Fetch an LLM provider by its unique name."""
    from sqlalchemy import select

    async with service.session_factory() as session:
        stmt = select(LLMProviderORM).where(LLMProviderORM.name == name)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_llm_provider(row)


async def list_llm_providers(
    service: "ConfigurationService",
    include_disabled: bool = False,
) -> list[LLMProvider]:
    """List all LLM providers, optionally including disabled ones."""
    from sqlalchemy import select

    async with service.session_factory() as session:
        stmt = select(LLMProviderORM)
        if not include_disabled:
            stmt = stmt.where(LLMProviderORM.enabled.is_(True))
        rows = (await session.execute(stmt)).scalars().all()
        return [_row_to_llm_provider(r) for r in rows]


async def get_default_llm_provider(
    service: "ConfigurationService",
) -> LLMProvider | None:
    """Return the LLM provider flagged as the default."""
    from sqlalchemy import select

    async with service.session_factory() as session:
        stmt = select(LLMProviderORM).where(LLMProviderORM.is_default.is_(True))
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_llm_provider(row)


def _row_to_llm_provider(row: LLMProviderORM) -> LLMProvider:
    """Convert a SQLAlchemy row to a Pydantic LLMProvider.

    Decrypts the API key if the encryption helper is wired up.
    """
    from .service import ConfigurationService

    api_key = row.api_key
    # Use the same decrypt path the mixin uses; the service
    # holds the encryption helpers.
    if api_key and hasattr(row, "_decrypted_api_key"):
        api_key = row._decrypted_api_key  # type: ignore[attr-defined]
    return LLMProvider(
        id=row.id,
        name=row.name,
        provider_type=row.provider_type,
        model=row.model,
        api_key=api_key,
        base_url=row.base_url,
        enabled=row.enabled,
        is_default=row.is_default,
        extra_config=row.extra_config or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def create_llm_provider(
    service: "ConfigurationService",
    provider: LLMProviderCreate,
    *,
    user: str | None = None,
) -> LLMProvider:
    """Create a new LLM provider.

    Encrypts the API key before persisting. Raises
    ``IntegrityError`` if the name is already taken.
    """
    import uuid

    pid = str(uuid.uuid4())
    async with service.session_factory() as session:
        row = LLMProviderORM(
            id=pid,
            name=provider.name,
            provider_type=provider.provider_type,
            model=provider.model,
            api_key=provider.api_key,  # encryption handled by ORM hook
            base_url=provider.base_url,
            enabled=provider.enabled,
            is_default=provider.is_default,
            extra_config=provider.extra_config or {},
        )
        session.add(row)
        await session.commit()
    return await get_llm_provider(service, pid)


async def update_llm_provider(
    service: "ConfigurationService",
    provider_id: str,
    update: LLMProviderUpdate,
    *,
    user: str | None = None,
) -> LLMProvider | None:
    """Update an existing LLM provider. Returns the updated
    record, or ``None`` if the provider is unknown."""
    from sqlalchemy import select

    async with service.session_factory() as session:
        row = await session.get(LLMProviderORM, provider_id)
        if row is None:
            return None
        if update.model is not None:
            row.model = update.model
        if update.api_key is not None:
            row.api_key = update.api_key
        if update.base_url is not None:
            row.base_url = update.base_url
        if update.enabled is not None:
            row.enabled = update.enabled
        if update.is_default is not None:
            row.is_default = update.is_default
        if update.extra_config is not None:
            row.extra_config = update.extra_config
        await session.commit()
    return await get_llm_provider(service, provider_id)


async def delete_llm_provider(
    service: "ConfigurationService",
    provider_id: str,
    *,
    user: str | None = None,
) -> bool:
    """Delete an LLM provider. Returns True if the provider
    was found and removed."""
    async with service.session_factory() as session:
        row = await session.get(LLMProviderORM, provider_id)
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
    return True


def get_llm_provider_api_key(
    service: "ConfigurationService",
    provider: LLMProvider,
) -> str | None:
    """Decrypt and return the API key for ``provider``.

    Returns ``None`` if no key is stored or decryption fails.
    The actual decryption path is owned by the service so
    this function is a thin facade.
    """
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
    "create_llm_provider",
    "delete_llm_provider",
    "get_default_llm_provider",
    "get_llm_provider",
    "get_llm_provider_api_key",
    "get_llm_provider_by_name",
    "list_llm_providers",
    "update_llm_provider",
]
