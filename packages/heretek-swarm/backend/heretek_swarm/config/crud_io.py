"""
Configuration import/export — extracted from ``config/crud.py``
as part of Phase 2.6 of PLAN.md (§1.4 god-class extraction —
``config/crud.py`` was 1,438 LOC with a single
``ConfigurationServiceCrud`` mixin owning CRUD for 8 entity
types).

The audit specifically called out ``import_export`` as a
distinct concern worth its own module. The functions here are
the same logic as the original
``ConfigurationServiceCrud.export_configurations`` /
``import_configurations`` / ``_import_rows`` methods, but
expressed as free functions that take the service instance as
their first argument. The mixin keeps these method names so
existing call sites work; the methods now delegate here.

Backwards compatibility: ``ConfigurationServiceCrud`` still
has the same public method signatures. New code that needs
import/export logic can call these free functions directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .service import ConfigurationService

from .models import (
    AgentConfigCreate,
    ConfigurationExport,
    EmbeddingProviderCreate,
    ImportOptions,
    ImportResult,
    LLMProviderCreate,
    UserConfigurationCreate,
)


async def export_configurations(
    service: "ConfigurationService",
    config_type: Any | None = None,
    include_sensitive: bool = False,
    exported_by: str | None = None,
) -> ConfigurationExport:
    """Export configurations.

    Args:
        service: The :class:`ConfigurationService` instance.
        config_type: Optional type filter (currently unused — kept
            for backwards compatibility with the method signature).
        include_sensitive: Whether to include sensitive data
            (API keys, etc.).
        exported_by: User performing the export.

    Returns:
        :class:`ConfigurationExport` bundle.
    """
    _ = config_type  # backwards-compat: ignored
    llm_providers = await service.list_llm_providers(include_disabled=True)
    embedding_providers = await service.list_embedding_providers(
        include_disabled=True
    )
    agent_configs = await service.list_agent_configs(include_disabled=True)
    user_configs = await service.list_configs(include_sensitive=include_sensitive)

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
    service: "ConfigurationService",
    import_data: Any,
    options: ImportOptions | None = None,
    user: str | None = None,
) -> ImportResult:
    """Import configurations.

    Args:
        service: The :class:`ConfigurationService` instance.
        import_data: Data to import (:class:`ConfigurationImport`
            or dict).
        options: Import options.
        user: User performing the import.

    Returns:
        :class:`ImportResult` with counts and errors.
    """
    opts = options or ImportOptions()
    payload = (
        import_data.model_dump()
        if hasattr(import_data, "model_dump")
        else import_data
    )
    imported: dict[str, int] = {
        "user_configurations": 0,
        "llm_providers": 0,
        "embedding_providers": 0,
        "agent_configs": 0,
    }
    errors: list[str] = []

    if opts.import_llm_providers and payload.get("llm_providers"):
        await _import_rows(
            service,
            payload["llm_providers"],
            LLMProviderCreate,
            service.create_llm_provider,
            imported,
            "llm_providers",
            errors,
            user,
        )

    if opts.import_embedding_providers and payload.get("embedding_providers"):
        await _import_rows(
            service,
            payload["embedding_providers"],
            EmbeddingProviderCreate,
            service.create_embedding_provider,
            imported,
            "embedding_providers",
            errors,
            user,
        )

    if opts.import_agent_configs and payload.get("agent_configs"):
        await _import_rows(
            service,
            payload["agent_configs"],
            AgentConfigCreate,
            service.create_agent_config,
            imported,
            "agent_configs",
            errors,
            user,
        )

    if opts.import_user_configs and payload.get("user_configurations"):
        await _import_rows(
            service,
            payload["user_configurations"],
            UserConfigurationCreate,
            service.create_config,
            imported,
            "user_configurations",
            errors,
            user,
        )

    return ImportResult(
        success=len(errors) == 0,
        imported_count=imported,
        errors=errors,
    )


async def _import_rows(
    service: "ConfigurationService",
    rows: list[dict[str, Any]],
    create_type: type,
    create_fn: Any,
    imported: dict[str, int],
    key: str,
    errors: list[str],
    user: str | None,
) -> None:
    """Import a list of rows using the given create function.

    Label is derived from ``key`` by stripping the trailing
    ``s`` (``"llm_providers"`` → ``"llm_provider"``).
    """
    label = key.rstrip("s")
    for row in rows:
        try:
            await create_fn(create_type(**row), user=user)
            imported[key] += 1
        except Exception as exc:
            errors.append(f"{label}: {exc}")


__all__ = [
    "export_configurations",
    "import_configurations",
    "_import_rows",
]
