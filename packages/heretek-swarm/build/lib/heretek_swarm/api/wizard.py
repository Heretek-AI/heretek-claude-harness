"""
Configuration Wizard API Endpoints

HTTP endpoints for the Zero-Touch Configuration Wizard.
Provides a guided setup flow for LLM providers, API keys, and system parameters.

Tenet #1: "Zero-Touch Configuration (Wizard-First)"
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response

from heretek_swarm.config.models import (
    InfrastructureConfigCreate,
    InfrastructureConfigUpdate,
    InfrastructureService,
    LLMProviderCreate,
    LLMProviderType,
    LLMProviderUpdate,
)
from heretek_swarm.config.service import (
    ConfigurationService,
    get_config_service,
)
from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.infrastructure.health import (
    check_all_infrastructure,
    check_infrastructure_health,
)
from heretek_swarm.infrastructure.nats.publisher import (
    SwarmEvent,
    get_nats_publisher,
)

logger = structlog.get_logger("api.wizard")

router = APIRouter(
    prefix="/api/wizard",
    tags=["Configuration Wizard"],
    dependencies=[Depends(verify_auth)],
)


# =============================================================================
# Available Providers Definition
# =============================================================================

AVAILABLE_PROVIDERS = {
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "type": "anthropic",
        "icon": "brain",
        "description": "Claude models via Anthropic's API",
        "default_model": "claude-sonnet-4-20250514",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "requires_api_key": True,
        "api_key_label": "Anthropic API Key",
        "api_key_env_var": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com",
        "color": "#ff6b35",
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "type": "openai",
        "icon": "sparkles",
        "description": "GPT models via OpenAI's API",
        "default_model": "gpt-4o",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "requires_api_key": True,
        "api_key_label": "OpenAI API Key",
        "api_key_env_var": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "color": "#10a37f",
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama",
        "type": "ollama",
        "icon": "cpu",
        "description": "Local LLM inference with Ollama",
        "default_model": "llama3.2",
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "requires_api_key": False,
        "api_key_label": "Ollama API Key (optional)",
        "api_key_env_var": "OLLAMA_API_KEY",
        "base_url": "http://localhost:11434",
        "color": "#ff6b9d",
    },
    "groq": {
        "id": "groq",
        "name": "Groq",
        "type": "openai_compatible",
        "icon": "zap",
        "description": "Fast inference via Groq's API",
        "default_model": "llama-3.3-70b-versatile",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "requires_api_key": True,
        "api_key_label": "Groq API Key",
        "api_key_env_var": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "color": "#fb5a47",
    },
    "mistral": {
        "id": "mistral",
        "name": "Mistral AI",
        "type": "openai_compatible",
        "icon": "cloud",
        "description": "Mistral models via Mistral's API",
        "default_model": "mistral-large-latest",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "requires_api_key": True,
        "api_key_label": "Mistral API Key",
        "api_key_env_var": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "color": "#d636f8",
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "type": "openai_compatible",
        "icon": "fish",
        "description": "DeepSeek V3 and Coder models",
        "default_model": "deepseek-chat",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "requires_api_key": True,
        "api_key_label": "DeepSeek API Key",
        "api_key_env_var": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "color": "#4ade80",
    },
    "local": {
        "id": "local",
        "name": "Local / LiteLLM",
        "type": "openai_compatible",
        "icon": "server",
        "description": "Local models via LiteLLM proxy",
        "default_model": "gpt-3.5-turbo",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "requires_api_key": False,
        "api_key_label": "LiteLLM API Key (optional)",
        "api_key_env_var": "LITELLM_API_KEY",
        "base_url": "http://localhost:4000",
        "color": "#60a5fa",
    },
}

# Agent tier configurations
AGENT_TIERS = {
    "minimal": {
        "id": "minimal",
        "name": "Minimal",
        "description": "Single agent for basic tasks",
        "agent_count": 1,
        "agents": ["coordinator"],
        "memory_enabled": False,
        "consciousness_enabled": False,
    },
    "standard": {
        "id": "standard",
        "name": "Standard",
        "description": "Multi-agent swarm for collaborative work",
        "agent_count": 5,
        "agents": ["coordinator", "coder", "examiner", "historian", "catalyst"],
        "memory_enabled": True,
        "consciousness_enabled": False,
    },
    "enhanced": {
        "id": "enhanced",
        "name": "Enhanced",
        "description": "Full swarm with memory and coordination",
        "agent_count": 11,
        "agents": [
            "coordinator",
            "coder",
            "examiner",
            "historian",
            "catalyst",
            "explorer",
            "dreamer",
            "echo",
            "metis",
            "nexus",
            "arbiter",
        ],
        "memory_enabled": True,
        "consciousness_enabled": True,
    },
    "maximal": {
        "id": "maximal",
        "name": "Maximal",
        "description": "Complete 23-agent collective with full capabilities",
        "agent_count": 23,
        "agents": [
            "alpha",
            "beta",
            "charlie",
            "coordinator",
            "coder",
            "examiner",
            "historian",
            "catalyst",
            "explorer",
            "dreamer",
            "echo",
            "metis",
            "nexus",
            "arbiter",
            "prism",
            "perceiver",
            "perceiver_plus",
            "steward",
            "sentinel",
            "sentinel_prime",
            "triad",
            "handoff",
            "validation",
        ],
        "memory_enabled": True,
        "consciousness_enabled": True,
    },
}


# Module-level provider type mapping (avoids re-creating dict inside loops)
_PROVIDER_TYPE_MAP: dict[str, LLMProviderType] = {
    "anthropic": LLMProviderType.OPENAI_COMPATIBLE,
    "openai": LLMProviderType.OPENAI,
    "ollama": LLMProviderType.OLLAMA,
    "groq": LLMProviderType.OPENAI_COMPATIBLE,
    "mistral": LLMProviderType.OPENAI_COMPATIBLE,
    "deepseek": LLMProviderType.OPENAI_COMPATIBLE,
    "local": LLMProviderType.OPENAI_COMPATIBLE,
}
_PROVIDER_TYPE_FALLBACK = LLMProviderType.OPENAI_COMPATIBLE

# Common HTTP error detail (extracted to avoid duplicate literals)
_INTERNAL_SERVER_ERROR = "Internal server error"


# =============================================================================
# Wizard State Management
# =============================================================================


class WizardState:
    """In-memory wizard state (would be Redis/DB in production)."""

    def __init__(self):
        self._providers: dict[str, dict[str, Any]] = {}
        self._config: dict[str, Any] = {}
        self._completed: bool = False

    def set_provider_config(self, provider_id: str, config: dict[str, Any]) -> None:
        """Store provider configuration."""
        self._providers[provider_id] = config

    def get_provider_config(self, provider_id: str) -> dict[str, Any] | None:
        """Get provider configuration."""
        return self._providers.get(provider_id)

    def get_all_providers(self) -> dict[str, dict[str, Any]]:
        """Get all configured providers."""
        return self._providers.copy()

    def set_wizard_config(self, config: dict[str, Any]) -> None:
        """Store wizard configuration."""
        self._config.update(config)

    def get_wizard_config(self) -> dict[str, Any]:
        """Get wizard configuration."""
        return self._config.copy()

    def set_completed(self, completed: bool) -> None:
        """Set wizard completion status."""
        self._completed = completed

    def is_completed(self) -> bool:
        """Check if wizard was completed."""
        return self._completed

    def clear(self) -> None:
        """Clear all wizard state."""
        self._providers.clear()
        self._config.clear()
        self._completed = False


# Global wizard state instance
_wizard_state = WizardState()


# =============================================================================
# Helper Functions
# =============================================================================


def get_service() -> ConfigurationService:
    """Dependency injection for ConfigurationService."""
    return get_config_service()


def get_wizard_state() -> WizardState:
    """Get the wizard state instance."""
    return _wizard_state


# =============================================================================
# Provider Endpoints
# =============================================================================


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    """
    List available LLM providers for the wizard.

    Returns:
        Available providers with their capabilities
    """
    return {
        "providers": list(AVAILABLE_PROVIDERS.values()),
        "total": len(AVAILABLE_PROVIDERS),
    }


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str) -> dict[str, Any]:
    """
    Get details for a specific provider.

    Args:
        provider_id: Provider identifier

    Returns:
        Provider details
    """
    if provider_id not in AVAILABLE_PROVIDERS:
        raise HTTPException(404, f"Provider '{provider_id}' not found")

    return AVAILABLE_PROVIDERS[provider_id]


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """
    Update a configured LLM provider.

    Updates provider settings in the database. If a new API key is provided,
    it will be re-encrypted using Fernet encryption before storage.

    Args:
        provider_id: UUID of the provider to update
        updates: Provider update data including optional new api_key

    Returns:
        Updated provider details

    Raises:
        HTTPException: If provider not found or update fails
    """
    service = get_service()

    try:
        provider_uuid = UUID(provider_id)
    except ValueError:
        raise HTTPException(400, f"Invalid provider ID format: '{provider_id}'")  # noqa: B904

    # Get existing provider
    existing = await service.get_llm_provider(provider_uuid)
    if not existing:
        raise HTTPException(404, f"Provider '{provider_id}' not found")

    # Build update model - handle API key re-encryption
    update_data = LLMProviderUpdate(
        base_url=updates.get("base_url"),
        api_key=updates.get("api_key"),
        api_key_hint=updates.get("api_key_hint"),
        default_model=updates.get("default_model"),
        available_models=updates.get("available_models"),
        model_aliases=updates.get("model_aliases"),
        supports_streaming=updates.get("supports_streaming"),
        supports_function_calling=updates.get("supports_function_calling"),
        supports_vision=updates.get("supports_vision"),
        max_tokens=updates.get("max_tokens"),
        max_context_length=updates.get("max_context_length"),
        rate_limit_requests_per_minute=updates.get("rate_limit_requests_per_minute"),
        rate_limit_tokens_per_minute=updates.get("rate_limit_tokens_per_minute"),
        is_enabled=updates.get("is_enabled"),
        is_default=updates.get("is_default"),
        priority=updates.get("priority"),
        extra_config=updates.get("extra_config"),
    )

    # Perform update (service handles API key encryption)
    updated = await service.update_llm_provider(
        provider_uuid,
        update_data,
        user="wizard",
    )

    if not updated:
        logger.error("provider_update_failed", provider_id=str(provider_uuid))
        raise HTTPException(500, _INTERNAL_SERVER_ERROR)

    logger.info(
        "provider_updated",
        provider_id=str(provider_uuid),
        user="wizard",
    )

    return {
        "id": str(updated.id),
        "name": updated.provider_name,
        "type": updated.provider_type,
        "base_url": updated.base_url,
        "default_model": updated.default_model,
        "is_enabled": updated.is_enabled,
        "is_default": updated.is_default,
    }


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str) -> Response:
    """
    Delete a configured LLM provider.

    Removes the provider from the database. Returns 204 on success.

    Args:
        provider_id: UUID of the provider to delete

    Raises:
        HTTPException: If provider not found or deletion fails
    """
    service = get_service()

    try:
        provider_uuid = UUID(provider_id)
    except ValueError:
        raise HTTPException(400, f"Invalid provider ID format: '{provider_id}'")  # noqa: B904

    # Check if provider exists
    existing = await service.get_llm_provider(provider_uuid)
    if not existing:
        raise HTTPException(404, f"Provider '{provider_id}' not found")

    # Delete provider
    deleted = await service.delete_llm_provider(
        provider_uuid,
        user="wizard",
    )

    if not deleted:
        logger.error("provider_delete_failed", provider_id=str(provider_uuid))
        raise HTTPException(500, "Internal server error")

    logger.info(
        "provider_deleted",
        provider_id=str(provider_uuid),
        user="wizard",
    )

    # Return 204 No Content
    return Response(status_code=204)


# =============================================================================
# Agent Tier Endpoints
# =============================================================================


@router.get("/tiers")
async def list_tiers() -> dict[str, Any]:
    """
    List available agent tier configurations.

    Returns:
        Available tiers with agent counts and capabilities
    """
    return {
        "tiers": list(AGENT_TIERS.values()),
        "total": len(AGENT_TIERS),
    }


@router.get("/tiers/{tier_id}")
async def get_tier(tier_id: str) -> dict[str, Any]:
    """
    Get details for a specific agent tier.

    Args:
        tier_id: Tier identifier

    Returns:
        Tier details
    """
    if tier_id not in AGENT_TIERS:
        raise HTTPException(404, f"Tier '{tier_id}' not found")

    return AGENT_TIERS[tier_id]


# =============================================================================
# Config Status Endpoint
# =============================================================================


@router.get("/config")
async def get_config_status() -> dict[str, Any]:
    """
    Get current configuration status.

    Returns:
        What's configured vs what needs setup
    """
    wizard_state = get_wizard_state()
    service = get_service()

    # Check what's already configured in the database
    configured_providers = []
    try:
        providers = await service.list_llm_providers(include_disabled=True)
        configured_providers = [
            {
                "id": str(p.id),
                "name": p.provider_name,
                "type": p.provider_type,
                "is_enabled": p.is_enabled,
                "is_default": p.is_default,
            }
            for p in providers
        ]
    except Exception as e:
        logger.warning("Failed to list providers", error=str(e))

    # Check system configuration
    system_config = {}
    try:
        db_url = await service.get_config_value("database.url")
        redis_url = await service.get_config_value("redis.url")
        qdrant_url = await service.get_config_value("qdrant.url")

        system_config = {
            "database": bool(db_url),
            "redis": bool(redis_url),
            "qdrant": bool(qdrant_url),
        }
    except Exception as e:
        logger.warning("Failed to get system config", error=str(e))

    # Get infrastructure configurations with health status
    infrastructure = []
    try:
        infra_configs = await service.list_infrastructure_configs(include_disabled=False)
        infrastructure = [
            {
                "id": str(c.id),
                "service": c.service,
                "host": c.host,
                "port": c.port,
                "health_status": c.health_status,
                "last_health_check": c.last_health_check.isoformat()
                if c.last_health_check
                else None,
                "health_check_latency_ms": c.health_check_latency_ms,
            }
            for c in infra_configs
        ]
    except Exception as e:
        logger.warning("Failed to list infrastructure configs", error=str(e))

    return {
        "wizard_completed": wizard_state.is_completed(),
        "wizard_state": {
            "providers_configured": list(wizard_state.get_all_providers().keys()),
            "config": wizard_state.get_wizard_config(),
        },
        "database_configured": {
            "providers": configured_providers,
            "total_providers": len(configured_providers),
        },
        "infrastructure": infrastructure,
        "system_config": system_config,
        "needs_setup": {
            "providers": len(configured_providers) == 0,
            "agents": True,  # Always needs setup initially
            "api_keys": any(p.get("requires_api_key") for p in AVAILABLE_PROVIDERS.values()),
            "infrastructure": len(infrastructure) == 0,
        },
    }


# =============================================================================
# Validation Error Messages (Constants)
# =============================================================================

API_KEY_REQUIRED = "API key is required"
APPLICATION_JSON = "application/json"
API_KEY_VALID = "API key is valid"
CONNECTION_TIMED_OUT = "Connection timed out"
CONNECTION_FAILED = "Connection failed: {error}"
INVALID_API_KEY = "Invalid API key"
LITE_LLM_NOT_HEALTHY = "LiteLLM proxy not healthy"
OLLAMA_NOT_RUNNING = "Ollama not running"
UNKNOWN_PROVIDER_TYPE = "Unknown provider type"
VALIDATION_FAILED = "Validation failed"


# =============================================================================
# Provider Validation Dispatch
# =============================================================================


async def _dispatch_validation(
    provider_id: str,
    api_key: str | None,
    base_url: str,
) -> dict[str, Any]:
    """
    Dispatch to the appropriate validator based on provider type.

    Args:
        provider_id: Provider identifier
        api_key: API key to validate
        base_url: Base URL for the provider

    Returns:
        Validation result
    """
    validators = {
        "anthropic": _validate_anthropic,
        "openai": _validate_openai,
        "ollama": _validate_ollama,
        "groq": _validate_groq,
        "mistral": _validate_mistral,
        "deepseek": _validate_deepseek,
        "local": _validate_local,
    }

    validator = validators.get(provider_id)
    if validator:
        return await validator(api_key, base_url)
    return {"valid": False, "error": UNKNOWN_PROVIDER_TYPE}


# =============================================================================
# Validation Endpoint
# =============================================================================


@router.post("/validate")
async def validate_credentials(
    provider_id: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """
    Validate provider credentials before saving.

    Args:
        provider_id: Provider to validate
        api_key: API key to validate (optional for some providers)
        base_url: Base URL override (optional)

    Returns:
        Validation result
    """
    if provider_id not in AVAILABLE_PROVIDERS:
        raise HTTPException(404, f"Provider '{provider_id}' not found")

    provider = AVAILABLE_PROVIDERS[provider_id]

    # Check if API key is required
    if provider["requires_api_key"] and not api_key:
        return {
            "valid": False,
            "error": f"{provider['api_key_label']} is required",
            "provider_id": provider_id,
        }

    # Perform validation via dispatch
    try:
        result = await _dispatch_validation(provider_id, api_key, base_url or provider["base_url"])
        result["provider_id"] = provider_id
        return result
    except Exception as e:
        logger.error("Provider validation failed", provider=provider_id, error=str(e))
        return {
            "valid": False,
            "error": VALIDATION_FAILED,
            "provider_id": provider_id,
        }


async def _validate_anthropic(api_key: str | None, base_url: str) -> dict[str, Any]:
    """Validate Anthropic API key."""
    import httpx

    if not api_key:
        return {"valid": False, "error": API_KEY_REQUIRED}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": APPLICATION_JSON,
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                return {
                    "valid": True,
                    "provider_id": "anthropic",
                    "message": API_KEY_VALID,
                }
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error", {}).get("message", response.text) or INVALID_API_KEY
            return {"valid": False, "error": error_msg}
    except httpx.TimeoutException:
        return {"valid": False, "error": CONNECTION_TIMED_OUT}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


async def _validate_openai(api_key: str | None, base_url: str) -> dict[str, Any]:
    """Validate OpenAI API key."""
    import httpx

    if not api_key:
        return {"valid": False, "error": API_KEY_REQUIRED}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                return {
                    "valid": True,
                    "provider_id": "openai",
                    "message": API_KEY_VALID,
                }
            return {"valid": False, "error": INVALID_API_KEY}
    except httpx.TimeoutException:
        return {"valid": False, "error": CONNECTION_TIMED_OUT}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


async def _validate_ollama(api_key: str | None, base_url: str) -> dict[str, Any]:
    """Validate Ollama connection."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/api/tags", timeout=10.0)

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name") for m in models[:5]]
                return {
                    "valid": True,
                    "provider_id": "ollama",
                    "message": f"Connected. Available models: {', '.join(model_names) or 'none'}",
                    "available_models": model_names,
                }
            return {"valid": False, "error": "Failed to connect to Ollama"}
    except httpx.TimeoutException:
        return {"valid": False, "error": OLLAMA_NOT_RUNNING}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


async def _validate_groq(api_key: str | None, base_url: str) -> dict[str, Any]:
    """Validate Groq API key."""
    import httpx

    if not api_key:
        return {"valid": False, "error": API_KEY_REQUIRED}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": APPLICATION_JSON,
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                return {
                    "valid": True,
                    "provider_id": "groq",
                    "message": API_KEY_VALID,
                }
            return {"valid": False, "error": INVALID_API_KEY}
    except httpx.TimeoutException:
        return {"valid": False, "error": CONNECTION_TIMED_OUT}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


async def _validate_mistral(api_key: str | None, base_url: str) -> dict[str, Any]:
    """Validate Mistral API key."""
    import httpx

    if not api_key:
        return {"valid": False, "error": API_KEY_REQUIRED}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": APPLICATION_JSON,
                },
                json={
                    "model": "mistral-small-latest",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                return {
                    "valid": True,
                    "provider_id": "mistral",
                    "message": API_KEY_VALID,
                }
            return {"valid": False, "error": INVALID_API_KEY}
    except httpx.TimeoutException:
        return {"valid": False, "error": CONNECTION_TIMED_OUT}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


async def _validate_deepseek(api_key: str | None, base_url: str) -> dict[str, Any]:
    """Validate DeepSeek API key."""
    import httpx

    if not api_key:
        return {"valid": False, "error": API_KEY_REQUIRED}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": APPLICATION_JSON,
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                return {
                    "valid": True,
                    "provider_id": "deepseek",
                    "message": API_KEY_VALID,
                }
            return {"valid": False, "error": INVALID_API_KEY}
    except httpx.TimeoutException:
        return {"valid": False, "error": CONNECTION_TIMED_OUT}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


async def _validate_local(base_url: str, api_key: str | None) -> dict[str, Any]:
    """Validate local/LiteLLM connection."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            response = await client.get(f"{base_url}/health", headers=headers, timeout=10.0)

            if response.status_code == 200:
                return {
                    "valid": True,
                    "provider_id": "local",
                    "message": "LiteLLM proxy is healthy",
                }
            return {"valid": False, "error": "LiteLLM proxy not healthy"}
    except httpx.TimeoutException:
        return {"valid": False, "error": "Connection timed out - is LiteLLM running?"}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


# =============================================================================
# Wizard Event Emission
# =============================================================================


async def _emit_wizard_completed_event(tier_config: dict[str, Any]) -> None:
    """
    Emit a wizard.completed SwarmEvent to trigger autonomous runtime startup.

    Args:
        tier_config: The tier configuration including tier_id, agents, etc.
    """
    try:
        publisher = get_nats_publisher()

        event = SwarmEvent(
            event_type="wizard.completed",
            source_agent="wizard",
            target_agent=None,
            payload={
                "tier_id": tier_config.get("tier", "standard"),
                "agent_count": tier_config.get("agent_count", 0),
                "agents": tier_config.get("agents", []),
                "memory_enabled": tier_config.get("memory_enabled", False),
                "consciousness_enabled": tier_config.get("consciousness_enabled", False),
            },
        )

        success = await publisher.publish_event(event)

        if success:
            logger.info(
                "wizard_completed_event_emitted",
                tier_id=tier_config.get("tier"),
                agent_count=tier_config.get("agent_count", 0),
            )
        else:
            logger.warning(
                "wizard_completed_event_publish_failed",
                tier_id=tier_config.get("tier"),
            )

    except Exception as e:
        # Gracefully handle NATS unavailable - log warning but don't fail wizard
        logger.warning(
            "wizard_completed_event_error",
            error=str(e),
            tier_id=tier_config.get("tier"),
        )


# =============================================================================
# Configuration Submission Endpoint
# =============================================================================


async def _create_single_provider(
    service: ConfigurationService,
    provider_config: dict[str, Any],
    provider_info: dict[str, Any],
    provider_id: str,
    api_key: str | None,
    model: str,
    is_default: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    """Create a single LLM provider from wizard config.

    Returns (result_dict, error_str) — exactly one is non-None.
    """
    llm_provider_type = _PROVIDER_TYPE_MAP.get(provider_id, _PROVIDER_TYPE_FALLBACK)

    create_data = LLMProviderCreate(
        provider_name=provider_info["name"],
        provider_type=llm_provider_type,
        base_url=provider_config.get("base_url") or provider_info["base_url"],
        api_key=api_key,
        api_key_hint=f"***{api_key[-4:]}" if api_key else None,
        default_model=model,
        is_enabled=True,
        is_default=is_default,
        supports_streaming=provider_info.get("supports_streaming", True),
        supports_function_calling=provider_info.get("supports_function_calling", False),
        supports_vision=provider_info.get("supports_vision", False),
        extra_config=provider_config.get("extra_config", {}),
    )

    created = await service.create_llm_provider(create_data, user="wizard")
    return {
        "id": str(created.id),
        "name": created.provider_name,
        "type": created.provider_type,
        "model": created.default_model,
    }, None


async def submit_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Submit wizard configuration.

    This creates LLM providers, sets system configuration, and
    initializes the agent swarm based on the selected tier.

    Args:
        config: Wizard configuration containing:
            - providers: List of provider configs with api_key, model preferences
            - tier: Selected agent tier
            - preferences: Model preferences and settings

    Returns:
        Configuration result with created resources
    """
    wizard_state = get_wizard_state()
    service = get_service()

    result: dict[str, Any] = {
        "success": True,
        "providers_created": [],
        "config": {},
        "errors": [],
    }

    providers = config.get("providers", [])
    for provider_config in providers:
        provider_id = provider_config.get("provider_id")
        api_key = provider_config.get("api_key")
        model = provider_config.get("model") or AVAILABLE_PROVIDERS.get(provider_id, {}).get(
            "default_model"
        )
        is_default = provider_config.get("is_default", False)

        if not provider_id or provider_id not in AVAILABLE_PROVIDERS:
            result["errors"].append(f"Invalid provider: {provider_id}")
            continue

        provider_info = AVAILABLE_PROVIDERS[provider_id]

        try:
            created_dict, _ = await _create_single_provider(
                service, provider_config, provider_info,
                provider_id, api_key, model, is_default,
            )
            if created_dict:
                result["providers_created"].append(created_dict)
                wizard_state.set_provider_config(
                    provider_id,
                    {
                        "provider_id": created_dict["id"],
                        "model": model,
                        "api_key_provided": bool(api_key),
                    },
                )
        except Exception as e:
            logger.error("Failed to create provider", provider=provider_id, error=str(e))
            result["errors"].append(f"Failed to create {provider_info['name']}: {e!s}")

    # Store tier configuration
    tier_id = config.get("tier", "standard")
    tier_config = {}
    if tier_id in AGENT_TIERS:
        tier_config = AGENT_TIERS[tier_id]
        wizard_state.set_wizard_config(
            {
                "tier": tier_id,
                "agent_count": tier_config["agent_count"],
                "agents": tier_config["agents"],
                "memory_enabled": tier_config["memory_enabled"],
                "consciousness_enabled": tier_config["consciousness_enabled"],
            }
        )

        result["config"]["tier"] = tier_id
        result["config"]["agent_count"] = tier_config["agent_count"]

    # Store preferences
    preferences = config.get("preferences", {})
    wizard_state.set_wizard_config({"preferences": preferences})

    # Mark wizard as completed
    wizard_state.set_completed(True)

    # Emit wizard.completed event for autonomous runtime startup (fire-and-forget)
    # This triggers the runtime to begin agent spawning without requiring user action
    asyncio.create_task(_emit_wizard_completed_event(tier_config))  # noqa: RUF006

    result["success"] = len(result["errors"]) == 0

    logger.info("Wizard configuration submitted", result=result)

    return result


# =============================================================================
# Infrastructure Configuration Endpoints
# =============================================================================


@router.get("/infrastructure")
async def list_infrastructure_configs() -> dict[str, Any]:
    """
    List all infrastructure service configurations.

    Returns:
        List of infrastructure configs with health status
    """
    service = get_service()

    try:
        configs = await service.list_infrastructure_configs(include_disabled=True)

        return {
            "infrastructure": [
                {
                    "id": str(c.id),
                    "service": c.service,
                    "host": c.host,
                    "port": c.port,
                    "connection_url": c.connection_url,
                    "is_enabled": c.is_enabled,
                    "health_status": c.health_status,
                    "last_health_check": c.last_health_check.isoformat()
                    if c.last_health_check
                    else None,
                    "health_check_latency_ms": c.health_check_latency_ms,
                    "health_check_error": c.health_check_error,
                }
                for c in configs
            ],
            "total": len(configs),
        }
    except Exception as e:
        logger.exception("infrastructure_config_list_failed")
        raise HTTPException(500, _INTERNAL_SERVER_ERROR) from e


@router.post("/infrastructure")
async def create_infrastructure_config(
    config: InfrastructureConfigCreate,
) -> dict[str, Any]:
    """
    Create or update infrastructure service configuration.

    If a config for the same service already exists, updates it.
    Otherwise creates a new config.

    Args:
        config: Infrastructure config data

    Returns:
        Created or updated config
    """
    service = get_service()

    try:
        # Check if config already exists for this service
        existing = await service.get_infrastructure_config_by_service(config.service.value)

        if existing:
            # Update existing config
            updates = InfrastructureConfigUpdate(
                host=config.host,
                port=config.port,
                connection_url=config.connection_url,
                is_enabled=config.is_enabled,
                extra_config=config.extra_config,
            )
            updated = await service.update_infrastructure_config(existing.id, updates)

            logger.info(
                "infrastructure_config_updated",
                service=config.service.value,
                id=str(existing.id),
            )

            return {
                "id": str(updated.id),
                "service": updated.service,
                "host": updated.host,
                "port": updated.port,
                "connection_url": updated.connection_url,
                "is_enabled": updated.is_enabled,
                "message": "Configuration updated",
            }
        # Create new config
        created = await service.create_infrastructure_config(config)

        logger.info(
            "infrastructure_config_created",
            service=config.service.value,
            id=str(created.id),
        )

        return {
            "id": str(created.id),
            "service": created.service,
            "host": created.host,
            "port": created.port,
            "connection_url": created.connection_url,
            "is_enabled": created.is_enabled,
            "message": "Configuration created",
        }
    except Exception as e:
        logger.exception(
            "infrastructure_config_create_failed",
            service=config.service.value,
        )
        raise HTTPException(500, _INTERNAL_SERVER_ERROR) from e


@router.get("/infrastructure/{service}")
async def get_infrastructure_config(service: str) -> dict[str, Any]:
    """
    Get infrastructure configuration for a specific service.

    Args:
        service: Infrastructure service type (postgres, redis, qdrant, nats, mem0)

    Returns:
        Infrastructure config with health status
    """
    config_service = get_service()

    try:
        infra_service = InfrastructureService(service.lower())
    except ValueError:
        raise HTTPException(  # noqa: B904
            400,
            f"Invalid service type: {service}. Valid types: postgres, redis, qdrant, nats, mem0",
        )

    try:
        config = await config_service.get_infrastructure_config_by_service(infra_service.value)

        if not config:
            raise HTTPException(404, f"No configuration found for service: {service}")

        return {
            "id": str(config.id),
            "service": config.service,
            "host": config.host,
            "port": config.port,
            "connection_url": config.connection_url,
            "is_enabled": config.is_enabled,
            "health_status": config.health_status,
            "last_health_check": config.last_health_check.isoformat()
            if config.last_health_check
            else None,
            "health_check_latency_ms": config.health_check_latency_ms,
            "health_check_error": config.health_check_error,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("infrastructure_config_get_failed", service=service)
        raise HTTPException(500, _INTERNAL_SERVER_ERROR) from e


@router.post("/infrastructure/{service}/health-check")
async def check_service_health(service: str) -> dict[str, Any]:
    """
    Run health check for a specific infrastructure service.

    Args:
        service: Infrastructure service type (postgres, redis, qdrant, nats, mem0)

    Returns:
        Health check result
    """
    config_service = get_service()

    try:
        infra_service = InfrastructureService(service.lower())
    except ValueError:
        raise HTTPException(  # noqa: B904
            400,
            f"Invalid service type: {service}. Valid types: postgres, redis, qdrant, nats, mem0",
        )

    try:
        config = await config_service.get_infrastructure_config_by_service(infra_service.value)

        if not config:
            raise HTTPException(404, f"No configuration found for service: {service}")

        # Run health check
        result = await check_infrastructure_health(
            service=infra_service,
            host=config.host,
            port=config.port,
            timeout=5.0,
        )

        # Update health status in database
        await config_service.update_infrastructure_health(
            config_id=config.id,
            health_status=result.status.value,
            latency_ms=result.latency_ms,
            error=result.error,
        )

        logger.info(
            "infrastructure_health_check",
            service=infra_service.value,
            status=result.status.value,
            latency_ms=result.latency_ms,
            error=result.error,
        )

        return {
            "service": result.service.value,
            "status": result.status.value,
            "latency_ms": result.latency_ms,
            "error": result.error,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("infrastructure_health_check_failed", service=service)
        raise HTTPException(500, _INTERNAL_SERVER_ERROR) from e


@router.post("/infrastructure/health-check-all")
async def check_all_services_health() -> dict[str, Any]:
    """
    Run health check for all configured infrastructure services.

    Returns:
        Health check results for all services
    """
    config_service = get_service()

    try:
        configs = await config_service.list_infrastructure_configs(include_disabled=False)

        if not configs:
            return {
                "results": [],
                "summary": "No infrastructure services configured",
            }

        # Convert configs to dict format for health check
        config_dicts = [
            {
                "service": c.service,
                "host": c.host,
                "port": c.port,
            }
            for c in configs
        ]

        # Run all health checks concurrently
        results = await check_all_infrastructure(config_dicts, timeout=5.0)

        # Update health status in database for each service
        for i, result in enumerate(results):
            config = configs[i]
            await config_service.update_infrastructure_health(
                config_id=config.id,
                health_status=result.status.value,
                latency_ms=result.latency_ms,
                error=result.error,
            )

            logger.info(
                "infrastructure_health_check",
                service=result.service.value,
                status=result.status.value,
                latency_ms=result.latency_ms,
            )

        # Count statuses
        healthy = sum(1 for r in results if r.status.value == "healthy")
        unhealthy = sum(1 for r in results if r.status.value == "unhealthy")
        degraded = sum(1 for r in results if r.status.value == "degraded")

        return {
            "results": [
                {
                    "service": r.service.value,
                    "status": r.status.value,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                }
                for r in results
            ],
            "summary": {
                "total": len(results),
                "healthy": healthy,
                "unhealthy": unhealthy,
                "degraded": degraded,
            },
        }
    except Exception as e:
        logger.exception("infrastructure_health_check_all_failed")
        raise HTTPException(500, _INTERNAL_SERVER_ERROR) from e


@router.delete("/infrastructure/{service}")
async def delete_infrastructure_config(service: str) -> Response:
    """
    Delete infrastructure configuration for a specific service.

    Args:
        service: Infrastructure service type

    Returns:
        204 No Content on success
    """
    config_service = get_service()

    try:
        infra_service = InfrastructureService(service.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid service type: {service}")  # noqa: B904

    try:
        config = await config_service.get_infrastructure_config_by_service(infra_service.value)

        if not config:
            raise HTTPException(404, f"No configuration found for service: {service}")

        await config_service.delete_infrastructure_config(config.id)

        logger.info("infrastructure_config_deleted", service=service)

        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("infrastructure_config_delete_failed", service=service)
        raise HTTPException(500, _INTERNAL_SERVER_ERROR) from e


# =============================================================================
# Reset Endpoint
# =============================================================================


@router.post("/reset")
async def reset_wizard() -> dict[str, Any]:
    """
    Reset wizard state to allow reconfiguration.

    Returns:
        Reset confirmation
    """
    wizard_state = get_wizard_state()
    wizard_state.clear()

    logger.info("Wizard state reset")

    return {
        "success": True,
        "message": "Wizard state has been reset",
    }
