"""
Configuration API Endpoints

HTTP endpoints for managing system configurations, LLM providers, and embedding providers.
Provides CRUD operations through a RESTful API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

logger = structlog.get_logger(__name__)

from heretek_swarm.config.models import (
    AgentConfigCreate,
    AgentConfigUpdate,
    ConfigurationImport,
    EmbeddingProviderCreate,
    EmbeddingProviderTestRequest,
    EmbeddingProviderUpdate,
    ImportOptions,
    UserConfigurationCreate,
    UserConfigurationUpdate,
)
from heretek_swarm.config.service import (
    ConfigurationService,
    get_config_service,
)
from heretek_swarm.gateway.auth import verify_auth

# Use lazy imports to break circular dependency at module load time
# These imports are resolved only when the functions are called
from heretek_swarm_core.utils import get_lazy_import

if TYPE_CHECKING:
    from uuid import UUID

# Lazy-loaded provider factory functions (embedding factory only; LLM CRUD
# routes were consolidated onto the ModelGarage-backed /api/providers/llm
# surface in Phase 4 follow-up).
_embedding_factory = get_lazy_import("heretek_swarm_core.embeddings.providers.factory")


def _get_embedding_provider_factory():
    """Get embedding provider factory functions with lazy resolution."""
    return _embedding_factory


logger = structlog.get_logger("api.configuration")

router = APIRouter(prefix="/api/config", tags=["Configuration"])


# =============================================================================
# Helper Functions
# =============================================================================


def get_service() -> ConfigurationService:
    """Dependency injection for ConfigurationService."""
    return get_config_service()


# =============================================================================
# User Configuration Endpoints
# =============================================================================


@router.get("")
async def get_all_configs(
    category: str | None = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Get all configurations with optional filtering."""
    configs = await service.list_configs(category=category, limit=limit, offset=offset)
    return {
        "configurations": [c.model_dump() for c in configs],
        "total": len(configs),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{key}")
async def get_config(
    key: str,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Get a specific configuration by key."""
    config = await service.get_config(key)
    if not config:
        raise HTTPException(404, f"Configuration '{key}' not found")
    return config.model_dump()


@router.put("/{key}")
async def update_config(
    key: str,
    update: UserConfigurationUpdate,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Update a configuration."""
    config = await service.update_config(key, update, user=authenticated)
    if not config:
        raise HTTPException(404, f"Configuration '{key}' not found")
    return config.model_dump()


@router.post("")
async def create_config(
    config: UserConfigurationCreate,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Create a new configuration."""
    try:
        new_config = await service.create_config(config, user=authenticated)
        return new_config.model_dump()
    except ValueError as e:
        logger.warning("create_config_validation_failed", error=str(e))
        raise HTTPException(400, "Invalid configuration data") from e


async def delete_config(
    key: str,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Delete a configuration."""
    success = await service.delete_config(key, user=authenticated)
    if not success:
        raise HTTPException(404, f"Configuration '{key}' not found")
    return {"status": "deleted", "key": key}


# =============================================================================
# Embedding Provider Endpoints
# =============================================================================


def _list_embedding_provider_types() -> list[str]:
    """List available embedding provider type identifiers."""
    return ["openai", "google", "huggingface", "ollama", "local"]


def _get_embedding_provider_info(provider_type: str) -> dict[str, Any]:
    """Get information about a specific embedding provider type."""
    info_map: dict[str, dict[str, Any]] = {
        "openai": {"type": "openai", "name": "OpenAI", "models": ["text-embedding-3-small"]},
        "google": {"type": "google", "name": "Google AI", "models": ["text-embedding-004"]},
        "huggingface": {"type": "huggingface", "name": "HuggingFace", "models": ["all-MiniLM-L6-v2"]},
        "ollama": {"type": "ollama", "name": "Ollama", "models": ["nomic-embed-text"]},
        "local": {"type": "local", "name": "Local", "models": ["local"]},
    }
    return info_map.get(provider_type, {"type": provider_type, "name": provider_type, "models": []})


@router.get("/embedding/types")
async def list_embedding_provider_types(
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """List available embedding provider types."""
    types = _list_embedding_provider_types()
    info = [_get_embedding_provider_info(t) for t in types]
    return {"provider_types": info}


@router.get("/embedding/providers")
async def list_embedding_providers(
    enabled_only: bool = Query(False, description="Only return enabled providers"),
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """List configured embedding providers."""
    providers = await service.list_embedding_providers(
        include_disabled=not enabled_only,
    )
    return {
        "providers": [p.model_dump() for p in providers],
        "total": len(providers),
    }


@router.get("/embedding/providers/{provider_id}")
async def get_embedding_provider(
    provider_id: UUID,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Get a specific embedding provider."""
    provider = await service.get_embedding_provider(provider_id)
    if not provider:
        raise HTTPException(404, f"Embedding provider '{provider_id}' not found")
    return provider.model_dump()


@router.post("/embedding/providers")
async def create_embedding_provider(
    provider: EmbeddingProviderCreate,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Create a new embedding provider."""
    try:
        new_provider = await service.create_embedding_provider(provider, user=authenticated)
        return new_provider.model_dump()
    except ValueError as e:
        logger.warning("create_embedding_provider_validation_failed", error=str(e))
        raise HTTPException(400, "Invalid embedding provider data") from e


async def update_embedding_provider(
    provider_id: UUID,
    update: EmbeddingProviderUpdate,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Update an embedding provider."""
    provider = await service.update_embedding_provider(provider_id, update, user=authenticated)
    if not provider:
        raise HTTPException(404, f"Embedding provider '{provider_id}' not found")
    return provider.model_dump()


@router.delete("/embedding/providers/{provider_id}")
async def delete_embedding_provider(
    provider_id: UUID,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Delete an embedding provider."""
    success = await service.delete_embedding_provider(provider_id, user=authenticated)
    if not success:
        raise HTTPException(404, f"Embedding provider '{provider_id}' not found")
    return {"status": "deleted", "id": str(provider_id)}


@router.post("/embedding/providers/{provider_id}/test")
async def test_embedding_provider(
    provider_id: UUID,
    test_request: EmbeddingProviderTestRequest,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Test embedding provider connectivity."""
    provider = await service.get_embedding_provider(provider_id)
    if not provider:
        raise HTTPException(404, f"Embedding provider '{provider_id}' not found")

    try:
        # Create provider instance
        embedding_provider = _get_embedding_provider_factory().create_embedding_provider(
            provider.provider_type,
            {
                "base_url": provider.base_url,
                "api_key": "test-key",  # In production, decrypt the actual key
                "default_model": test_request.model or provider.default_model,
                "extra_config": provider.extra_config,
            },
        )

        # Test connectivity by generating an embedding
        import time

        start_time = time.time()
        response = await embedding_provider.embed(
            texts=[test_request.text],
            model=test_request.model,
        )
        latency_ms = (time.time() - start_time) * 1000

        return {
            "provider_id": str(provider_id),
            "provider_name": provider.provider_name,
            "success": True,
            "model_used": response.model,
            "dimensions": response.dimensions,
            "latency_ms": latency_ms,
        }

    except Exception:
        logger.exception(
            "Embedding provider connectivity test failed",
            provider_id=str(provider_id),
            provider_name=provider.provider_name,
        )
        return {
            "provider_id": str(provider_id),
            "provider_name": provider.provider_name,
            "success": False,
            "error": "Embedding provider test failed",
        }


# =============================================================================
# Agent Configuration Endpoints
# =============================================================================


@router.get("/agent/configs")
async def list_agent_configs(
    agent_type: str | None = Query(None, description="Filter by agent type"),
    active_only: bool = Query(True, description="Only return active configs"),
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """List agent configurations."""
    configs = await service.list_agent_configs(agent_type=agent_type, include_inactive=not active_only)
    return {
        "configs": [c.model_dump() for c in configs],
        "total": len(configs),
    }


@router.get("/agent/configs/{config_id}")
async def get_agent_config(
    config_id: UUID,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Get a specific agent configuration."""
    config = await service.get_agent_config(config_id)
    if not config:
        raise HTTPException(404, f"Agent config '{config_id}' not found")
    return config.model_dump()


@router.post("/agent/configs")
async def create_agent_config(
    config: AgentConfigCreate,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Create a new agent configuration."""
    try:
        new_config = await service.create_agent_config(config, user=authenticated)
        return new_config.model_dump()
    except ValueError as e:
        logger.warning("create_agent_config_validation_failed", error=str(e))
        raise HTTPException(400, "Invalid agent configuration data") from e


async def update_agent_config(
    config_id: UUID,
    update: AgentConfigUpdate,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Update an agent configuration."""
    config = await service.update_agent_config(config_id, update, user=authenticated)
    if not config:
        raise HTTPException(404, f"Agent config '{config_id}' not found")
    return config.model_dump()


@router.delete("/agent/configs/{config_id}")
async def delete_agent_config(
    config_id: UUID,
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Delete an agent configuration."""
    success = await service.delete_agent_config(config_id, user=authenticated)
    if not success:
        raise HTTPException(404, f"Agent config '{config_id}' not found")
    return {"status": "deleted", "id": str(config_id)}


# =============================================================================
# Audit Log Endpoints
# =============================================================================


@router.get("/audit-log")
async def get_audit_log(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    limit: int = Query(100, ge=1, le=1000),
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Get configuration audit log."""
    logs = await service.get_audit_log(entity_type=entity_type, limit=limit)
    return {
        "logs": [log.model_dump() for log in logs],
        "total": len(logs),
    }


# =============================================================================
# Import/Export Endpoints
# =============================================================================


@router.get("/export")
async def export_configurations(
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Export all configurations."""
    export_data = await service.export_configurations(exported_by=authenticated)
    return export_data.model_dump()


@router.post("/import")
async def import_configurations(
    import_data: ConfigurationImport,
    options: ImportOptions = ImportOptions(),
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Import configurations from a bundle."""
    result = await service.import_configurations(import_data, options, user=authenticated)
    return result.model_dump()


# =============================================================================
# Migration Endpoint
# =============================================================================


@router.post("/migrate-from-env")
async def migrate_from_env(
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """Migrate configurations from environment variables to database."""
    return await service.migrate_from_env(user=authenticated)


@router.post("/seed-from-env")
async def seed_from_env(
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """
    Re-trigger idempotent seeding of LLM providers, embedding providers,
    and system configs from docker-compose environment variables.

    This gives operators a manual way to re-seed without restarting the API.
    Idempotent: already-existing records are skipped with reasons logged.
    Startup errors during seeding are caught and logged as warnings.

    Returns:
        SeedResult dict with providers_created, embedding_providers_created,
        configs_created, and skipped_reasons.
    """
    return await service.seed_from_env()


# =============================================================================
# Configuration Reload Endpoint
# =============================================================================


@router.post("/reload")
async def reload_configurations(
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """
    Reload configuration cache from database.

    This endpoint invalidates the cached configurations and reloads them
    from the database. Useful for applying configuration changes at runtime
    without restarting the application.

    Returns:
        Reload status and cache statistics
    """
    from heretek_swarm.config.loader import get_config_loader, reload_config

    try:
        # Reload the configuration cache
        reload_result = await reload_config()

        # Get cache stats
        loader = get_config_loader()
        cache_stats = loader.get_cache_stats()

        logger.info("Configuration reloaded", cached_keys=reload_result.get("cached_keys", []))

        return {
            "status": "reloaded",
            "cached_keys": reload_result.get("cached_keys", []),
            "cache_count": reload_result.get("cache_count", 0),
            "cache_stats": cache_stats,
            "reloaded_by": authenticated,
            "reloaded_at": datetime.now(UTC).isoformat() if hasattr(datetime, "utcnow") else datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Configuration reload failed", error=str(e))
        raise HTTPException(500, "Configuration reload failed") from e


# =============================================================================
# Configuration Health Check Endpoint
# =============================================================================


@router.get("/health")
async def configuration_health(
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """
    Check configuration service health status.

    Returns:
        Health status including database connectivity and cache status
    """
    from heretek_swarm.config.loader import get_config_loader

    try:
        # Test database connectivity
        test_config = await service.get_config("system.health_check")
        database_healthy = test_config is not None or True  # Config may not exist but connection works

        # Get cache stats
        loader = get_config_loader()
        cache_stats = loader.get_cache_stats()

        return {
            "status": "healthy",
            "database_connected": database_healthy,
            "cache_entries": cache_stats.get("total_entries", 0),
            "cache_hit_rate": cache_stats.get("hit_rate", 0),
        }
    except Exception as e:
        logger.error("configuration_health_failed", error=str(e))
        return {
            "status": "unhealthy",
            "database_connected": False,
            "error": "Configuration health check failed",
        }


# =============================================================================
# Configuration Import/Export Enhanced Endpoints
# =============================================================================


@router.get("/export/bundle")
async def export_configuration_bundle(
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """
    Export all configurations as a downloadable bundle.

    Returns:
        Complete configuration export with metadata
    """

    export_data = await service.export_configurations(exported_by=authenticated)

    return {
        "version": export_data.version,
        "exported_at": export_data.exported_at.isoformat(),
        "exported_by": export_data.exported_by,
        "user_configurations": [uc.model_dump() for uc in export_data.user_configurations],
        "llm_providers": [p.model_dump() for p in export_data.llm_providers],
        "embedding_providers": [p.model_dump() for p in export_data.embedding_providers],
        "agent_configs": [c.model_dump() for c in export_data.agent_configs],
        "summary": {
            "user_config_count": len(export_data.user_configurations),
            "llm_provider_count": len(export_data.llm_providers),
            "embedding_provider_count": len(export_data.embedding_providers),
            "agent_config_count": len(export_data.agent_configs),
        },
    }


@router.post("/import/bundle")
async def import_configuration_bundle(
    import_data: ConfigurationImport,
    options: ImportOptions = ImportOptions(),
    authenticated: str = Depends(verify_auth),
    service: ConfigurationService = Depends(get_service),
) -> dict[str, Any]:
    """
    Import configurations from a bundle.

    Args:
        import_data: Configuration bundle to import
        options: Import options (skip_conflicts, etc.)
        authenticated: Authenticated user

    Returns:
        Import result summary
    """
    result = await service.import_configurations(import_data, options, user=authenticated)

    return {
        "success": result.success,
        "imported_count": result.imported_count,
        "skipped_count": result.skipped_count,
        "error_count": result.error_count,
        "errors": result.errors,
        "imported_by": authenticated,
        "imported_at": datetime.now(UTC).isoformat(),
    }
