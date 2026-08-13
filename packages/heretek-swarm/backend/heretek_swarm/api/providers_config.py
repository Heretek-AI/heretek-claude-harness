"""
Config.json-backed LLM and Embedding Provider Management API.

Provides CRUD endpoints under ``/api/v1/providers/llm`` and
``/api/v1/providers/embedding``.  All persistence goes through
``~/.heretek-swarm/config.json`` — zero Postgres dependency.

LLM providers are managed via ``ModelGarage`` (which owns the in-memory
cache and atomic write).  Embedding providers are read/written directly
to config.json using the same atomic-write pattern.

Cross-cutting concerns:
- Structlog audit logging on every endpoint call (endpoint, method,
  caller_ip, duration_ms, status_code).
- Write operations log provider id and name.
- Rate limiting via the existing ``RateLimitMiddleware`` (100 req/min).
- Zero-trust input validation on all write paths.
"""

from __future__ import annotations

import contextlib
import json
import os as _os
import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from heretek_swarm.config import get_config_path
from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm_core.llm.model_garage import (
    ProviderConfig,
    ProviderType,
    get_model_garage,
)

logger = structlog.get_logger("api.providers_config")

router = APIRouter(
    prefix="/api/providers",
    tags=["Providers"],
    dependencies=[Depends(verify_auth)],
)


# =============================================================================
# Pydantic Models
# =============================================================================


class LLMProviderRequest(BaseModel):
    """Shape accepted for creating an LLM provider."""

    type: str = Field(..., description="Provider type: ollama, openai, anthropic, ...")
    name: str = Field(..., min_length=1, max_length=200)
    baseUrl: str = Field(..., min_length=1, max_length=2000)
    apiKey: str | None = None
    defaultModel: str | None = None
    models: list[str] = Field(default_factory=list)
    isEnabled: bool = True
    isDefault: bool = False
    priority: int = Field(default=100, ge=1, le=9999)


class LLMProviderUpdate(BaseModel):
    """Shape accepted for updating an LLM provider (all fields optional)."""

    type: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    baseUrl: str | None = Field(default=None, min_length=1, max_length=2000)
    apiKey: str | None = None
    defaultModel: str | None = None
    models: list[str] | None = None
    isEnabled: bool | None = None
    isDefault: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=9999)


class EmbeddingProviderRequest(BaseModel):
    """Shape accepted for creating an embedding provider."""

    type: str = Field(..., description="Provider type: ollama, openai, ...")
    name: str = Field(..., min_length=1, max_length=200)
    baseUrl: str = Field(..., min_length=1, max_length=2000)
    apiKey: str | None = None
    defaultModel: str | None = None
    models: list[str] = Field(default_factory=list)
    isEnabled: bool = True
    priority: int = Field(default=100, ge=1, le=9999)


class EmbeddingProviderUpdate(BaseModel):
    """Shape accepted for updating an embedding provider (all fields optional)."""

    type: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    baseUrl: str | None = Field(default=None, min_length=1, max_length=2000)
    apiKey: str | None = None
    defaultModel: str | None = None
    models: list[str] | None = None
    isEnabled: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=9999)


# =============================================================================
# Helpers
# =============================================================================


def _get_caller_ip(request: Request) -> str:
    """Extract caller IP, respecting proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"


def _log_request(request: Request, t0: float, extra: dict[str, Any] | None = None) -> None:
    """Emit a structured info log for the completed request."""
    duration_ms = round((time.time() - t0) * 1000, 2)
    log_data: dict[str, Any] = {
        "endpoint": request.url.path,
        "method": request.method,
        "caller_ip": _get_caller_ip(request),
        "duration_ms": duration_ms,
    }
    if extra:
        log_data.update(extra)
    logger.info("api_request", **log_data)


def _validate_provider_type(raw: str) -> ProviderType:
    """Convert a raw type string to a ``ProviderType`` or raise 400."""
    try:
        return ProviderType(raw)
    except ValueError:
        valid = ", ".join(sorted(t.value for t in ProviderType))
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider type '{raw}'. Valid: {valid}",
        ) from None


def _normalise_id(provider_id: str, label: str) -> None:
    """Reject obviously invalid IDs before they hit the garage."""
    if not provider_id or len(provider_id) > 256 or provider_id.isspace():
        raise HTTPException(status_code=400, detail=f"Invalid {label} id")


# ---------------------------------------------------------------------------
# Embedding provider config.json read/write (same atomic pattern as ModelGarage)
# ---------------------------------------------------------------------------


def _read_embedding_providers() -> tuple[dict, list[dict]]:
    """Return ``(full_config, embedding_providers_list)`` from config.json."""
    path = get_config_path()
    if not path.exists():
        return {"version": "1.0.0"}, []
    with open(path, encoding="utf-8") as f:
        data: dict = json.load(f)
    return data, data.get("embeddingProviders", [])


def _write_embedding_providers(full_config: dict, embedding_list: list[dict]) -> None:
    """Persist the embedding providers list atomically."""
    path = get_config_path()
    full_config["embeddingProviders"] = embedding_list
    if "version" not in full_config:
        full_config["version"] = "1.0.0"

    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(full_config, f, indent=2)
            f.flush()
            _os.fsync(f.fileno())
        tmp.replace(path)
        logger.info("embedding_config_saved", count=len(embedding_list))
    except OSError as e:
        logger.error(
            "embedding_config_save_failed",
            error=e.__class__.__name__,
            detail=str(e),
        )
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise HTTPException(
            status_code=500,
            detail="Failed to persist embedding provider config",
        ) from e


# =============================================================================
# LLM Provider Endpoints
# =============================================================================


@router.get("/llm")
async def list_llm_providers(request: Request) -> dict[str, Any]:
    """List all configured LLM providers from ModelGarage."""
    t0 = time.time()
    garage = get_model_garage()
    providers = garage.list_providers()
    _log_request(request, t0, extra={"provider_count": len(providers)})
    return {"providers": providers}


@router.post("/llm")
async def create_llm_provider(request: Request, body: LLMProviderRequest) -> dict[str, Any]:
    """Add a new LLM provider.  Auto-generates an id."""
    t0 = time.time()

    # Validate provider type
    provider_type = _validate_provider_type(body.type)

    # Build ProviderConfig
    provider_id = str(uuid.uuid4())
    config = ProviderConfig(
        id=provider_id,
        name=body.name,
        provider_type=provider_type,
        base_url=body.baseUrl,
        api_key=body.apiKey,
        default_model=body.defaultModel,
        available_models=body.models,
        is_enabled=body.isEnabled,
        is_default=body.isDefault,
        priority=body.priority,
    )

    garage = get_model_garage()
    garage.add_provider(config)
    garage.reload_config()

    _log_request(
        request,
        t0,
        extra={
            "status_code": 201,
            "provider_id": provider_id,
            "provider_name": body.name,
            "provider_type": body.type,
        },
    )
    return config.to_dict()


@router.put("/llm/{provider_id}")
async def update_llm_provider(
    request: Request, provider_id: str, body: LLMProviderUpdate
) -> dict[str, Any]:
    """Update an existing LLM provider."""
    t0 = time.time()
    _normalise_id(provider_id, "llm")

    garage = get_model_garage()
    existing = garage.get_provider_config(provider_id)
    if existing is None:
        _log_request(request, t0, extra={"status_code": 404, "provider_id": provider_id})
        raise HTTPException(status_code=404, detail=f"LLM provider '{provider_id}' not found")

    # Merge: use existing values for fields not in the update
    provider_type = _validate_provider_type(body.type) if body.type else existing.provider_type

    updated = ProviderConfig(
        id=provider_id,
        name=body.name if body.name is not None else existing.name,
        provider_type=provider_type,
        base_url=body.baseUrl if body.baseUrl is not None else existing.base_url,
        api_key=body.apiKey if body.apiKey is not None else existing.api_key,
        default_model=body.defaultModel
        if body.defaultModel is not None
        else existing.default_model,
        available_models=body.models if body.models is not None else existing.available_models,
        is_enabled=body.isEnabled if body.isEnabled is not None else existing.is_enabled,
        is_default=body.isDefault if body.isDefault is not None else existing.is_default,
        priority=body.priority if body.priority is not None else existing.priority,
        metadata=existing.metadata,
    )

    garage.update_provider(provider_id, updated)
    garage.reload_config()

    _log_request(
        request,
        t0,
        extra={
            "provider_id": provider_id,
            "provider_name": updated.name,
            "operation": "update",
        },
    )
    return updated.to_dict()


@router.delete("/llm/{provider_id}")
async def delete_llm_provider(request: Request, provider_id: str) -> dict[str, Any]:
    """Remove an LLM provider by id."""
    t0 = time.time()
    _normalise_id(provider_id, "llm")

    garage = get_model_garage()
    existing = garage.get_provider_config(provider_id)
    if existing is None:
        _log_request(request, t0, extra={"status_code": 404, "provider_id": provider_id})
        raise HTTPException(status_code=404, detail=f"LLM provider '{provider_id}' not found")

    garage.remove_provider(provider_id)
    garage.reload_config()

    _log_request(
        request,
        t0,
        extra={"provider_id": provider_id, "provider_name": existing.name, "operation": "delete"},
    )
    return {"deleted": provider_id}


@router.post("/llm/{provider_id}/test")
async def test_llm_provider(request: Request, provider_id: str) -> dict[str, Any]:
    """Test connectivity to an LLM provider."""
    t0 = time.time()
    _normalise_id(provider_id, "llm")

    garage = get_model_garage()
    existing = garage.get_provider_config(provider_id)
    if existing is None:
        _log_request(request, t0, extra={"status_code": 404, "provider_id": provider_id})
        raise HTTPException(status_code=404, detail=f"LLM provider '{provider_id}' not found")

    result = await garage.test_provider(provider_id)

    _log_request(
        request,
        t0,
        extra={
            "provider_id": provider_id,
            "provider_name": existing.name,
            "reachable": result["reachable"],
            "latency_ms": result["latency_ms"],
        },
    )
    return result


# =============================================================================
# Embedding Provider Endpoints
# =============================================================================


@router.get("/embedding")
async def list_embedding_providers(request: Request) -> dict[str, Any]:
    """List all configured embedding providers from config.json."""
    t0 = time.time()
    _full_cfg, providers = _read_embedding_providers()
    _log_request(request, t0, extra={"provider_count": len(providers)})
    return {"providers": providers}


@router.post("/embedding")
async def create_embedding_provider(
    request: Request, body: EmbeddingProviderRequest
) -> dict[str, Any]:
    """Add a new embedding provider.  Auto-generates an id."""
    t0 = time.time()

    provider = {
        "id": str(uuid.uuid4()),
        "type": body.type,
        "name": body.name,
        "baseUrl": body.baseUrl,
        "defaultModel": body.defaultModel,
        "models": body.models,
        "isEnabled": body.isEnabled,
        "priority": body.priority,
    }
    if body.apiKey:
        provider["apiKey"] = body.apiKey

    full_cfg, existing = _read_embedding_providers()
    existing.append(provider)
    _write_embedding_providers(full_cfg, existing)

    _log_request(
        request,
        t0,
        extra={
            "status_code": 201,
            "provider_id": provider["id"],
            "provider_name": body.name,
            "provider_type": body.type,
        },
    )
    return provider


@router.put("/embedding/{provider_id}")
async def update_embedding_provider(
    request: Request, provider_id: str, body: EmbeddingProviderUpdate
) -> dict[str, Any]:
    """Update an existing embedding provider."""
    t0 = time.time()
    _normalise_id(provider_id, "embedding")

    full_cfg, providers = _read_embedding_providers()
    existing: dict | None = None
    for _i, p in enumerate(providers):
        if p.get("id") == provider_id:
            existing = p
            break

    if existing is None:
        _log_request(request, t0, extra={"status_code": 404, "provider_id": provider_id})
        raise HTTPException(status_code=404, detail=f"Embedding provider '{provider_id}' not found")

    # Merge
    if body.type is not None:
        existing["type"] = body.type
    if body.name is not None:
        existing["name"] = body.name
    if body.baseUrl is not None:
        existing["baseUrl"] = body.baseUrl
    if body.apiKey is not None:
        existing["apiKey"] = body.apiKey
    if body.defaultModel is not None:
        existing["defaultModel"] = body.defaultModel
    if body.models is not None:
        existing["models"] = body.models
    if body.isEnabled is not None:
        existing["isEnabled"] = body.isEnabled
    if body.priority is not None:
        existing["priority"] = body.priority

    _write_embedding_providers(full_cfg, providers)

    _log_request(
        request,
        t0,
        extra={
            "provider_id": provider_id,
            "provider_name": existing.get("name"),
            "operation": "update",
        },
    )
    return existing


@router.delete("/embedding/{provider_id}")
async def delete_embedding_provider(request: Request, provider_id: str) -> dict[str, Any]:
    """Remove an embedding provider by id."""
    t0 = time.time()
    _normalise_id(provider_id, "embedding")

    full_cfg, providers = _read_embedding_providers()
    new_list = [p for p in providers if p.get("id") != provider_id]
    if len(new_list) == len(providers):
        _log_request(request, t0, extra={"status_code": 404, "provider_id": provider_id})
        raise HTTPException(status_code=404, detail=f"Embedding provider '{provider_id}' not found")

    _write_embedding_providers(full_cfg, new_list)

    _log_request(
        request,
        t0,
        extra={"provider_id": provider_id, "operation": "delete"},
    )
    return {"deleted": provider_id}


@router.post("/embedding/{provider_id}/test")
async def test_embedding_provider(request: Request, provider_id: str) -> dict[str, Any]:
    """Test connectivity to an embedding provider."""
    t0 = time.time()
    _normalise_id(provider_id, "embedding")

    _full_cfg, providers = _read_embedding_providers()
    existing: dict | None = None
    for p in providers:
        if p.get("id") == provider_id:
            existing = p
            break

    if existing is None:
        _log_request(request, t0, extra={"status_code": 404, "provider_id": provider_id})
        raise HTTPException(status_code=404, detail=f"Embedding provider '{provider_id}' not found")

    base_url = existing.get("baseUrl", "")
    api_key = existing.get("apiKey")

    import httpx

    try:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        test_t0 = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url.rstrip("/") + "/", headers=headers)
        latency_ms = round((time.time() - test_t0) * 1000, 2)
        reachable = resp.status_code < 500

        result: dict[str, Any] = {
            "reachable": reachable,
            "latency_ms": latency_ms,
            "error": None if reachable else f"HTTP {resp.status_code}",
        }
    except Exception as e:
        logger.error("embedding_provider_test_failed", provider_id=provider_id, error=str(e))
        latency_ms = round(
            (time.time() - t0 - 0.001) * 1000, 2
        )  # rough, excluding routing overhead
        result = {
            "reachable": False,
            "latency_ms": latency_ms,
            "error": "Embedding provider connectivity test failed",
        }

    _log_request(
        request,
        t0,
        extra={
            "provider_id": provider_id,
            "provider_name": existing.get("name"),
            "reachable": result["reachable"],
            "latency_ms": result["latency_ms"],
        },
    )
    return result
