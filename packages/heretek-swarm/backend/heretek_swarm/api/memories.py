"""
mem0 REST API Router

Exposes mem0 memory endpoints via the Heretek Swarm FastAPI app.
Endpoints mirror mem0_server/main.py for feature parity.

All endpoints accept optional X-API-Key header when ADMIN_API_KEY is set.
"""

import os
import secrets
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# Auth configuration
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """A single message in a memory conversation."""

    role: Annotated[str, Field(description="Role of the message (user or assistant).")]
    content: Annotated[str, Field(description="Message content.")]


class MemoryCreate(BaseModel):
    """Request body for creating memories."""

    messages: Annotated[list[Message], Field(description="List of messages to store.")]
    user_id: str | None = None
    agent_id: str | None = None
    run_id: str | None = None
    metadata: dict[str, Any] | None = None
    infer: bool | None = None
    memory_type: str | None = None
    prompt: str | None = None


class MemoryUpdate(BaseModel):
    """Request body for updating a memory."""

    text: Annotated[str, Field(description="New content to update the memory with.")]
    metadata: dict[str, Any] | None = None


class SearchRequest(BaseModel):
    """Request body for searching memories."""

    query: Annotated[str, Field(description="Search query.")]
    user_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    filters: dict[str, Any] | None = None
    top_k: int | None = None
    threshold: float | None = None


# ---------------------------------------------------------------------------
# Auth Dependency
# ---------------------------------------------------------------------------


async def verify_mem0_api_key(x_api_key: str | None = Header(None)) -> str | None:
    """
    Verify API key when ADMIN_API_KEY is configured.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        The API key if valid, None otherwise

    Raises:
        HTTPException: 401 if key is missing or invalid
    """
    if ADMIN_API_KEY:
        if x_api_key is None or not secrets.compare_digest(x_api_key, ADMIN_API_KEY):
            raise HTTPException(401, "Invalid API key.")
    return x_api_key


# ---------------------------------------------------------------------------
# Availability Guard
# ---------------------------------------------------------------------------


def _require_mem0():
    """
    Return the mem0_backend from main.py if available.

    Raises:
        HTTPException: 503 if mem0 is not installed or not initialized
    """
    # Import lazily to avoid circular import at module level.
    # See heretek_swarm.memory.mem0_backend for the wrapper; main.py holds
    # the process-global backend instance after ``_init_mem0`` runs.
    from heretek_swarm.api.main import MEM0_AVAILABLE, mem0_backend

    if not MEM0_AVAILABLE or not mem0_backend or mem0_backend.client is None:
        raise HTTPException(503, "mem0 not available")
    return mem0_backend


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/mem0", tags=["mem0"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/configure", summary="Configure mem0")
async def configure_mem0(
    config: dict[str, Any],
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> dict[str, str]:
    """
    Reconfigure mem0 with a new configuration.

    Args:
        config: Full mem0 configuration dict (vector store, LLM, embedder)

    Returns:
        Success message
    """
    backend = _require_mem0()
    await backend.configure(config)
    return {"message": "Configuration set successfully"}


@router.post("/memories", summary="Create memories")
async def add_memory(
    mc: MemoryCreate,
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> Any:
    """
    Store new memories from message list.

    Args:
        mc: MemoryCreate body with messages and identifiers

    Returns:
        Raw mem0 API response

    Raises:
        HTTPException: 400 if no identifier provided
    """
    if not any([mc.user_id, mc.agent_id, mc.run_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one identifier (user_id, agent_id, run_id) is required.",
        )

    backend = _require_mem0()

    params = {k: v for k, v in mc.model_dump().items() if v is not None and k != "messages"}
    return backend.add(messages=[m.model_dump() for m in mc.messages], **params)


@router.get("/memories", summary="Get memories")
async def get_all_memories(
    user_id: str | None = None,
    run_id: str | None = None,
    agent_id: str | None = None,
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> Any:
    """
    Retrieve stored memories for an identifier.

    Args:
        user_id: User identifier
        run_id: Run identifier
        agent_id: Agent identifier

    Returns:
        List of memory dicts

    Raises:
        HTTPException: 400 if no identifier provided
    """
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one identifier is required.",
        )

    backend = _require_mem0()
    return backend.get_all(user_id=user_id, run_id=run_id, agent_id=agent_id)


@router.get("/memories/{memory_id}", summary="Get a memory")
async def get_memory(
    memory_id: str,
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> Any:
    """
    Retrieve a specific memory by ID.

    Args:
        memory_id: Memory identifier

    Returns:
        Memory dict
    """
    backend = _require_mem0()
    return backend.get(memory_id)


@router.put("/memories/{memory_id}", summary="Update a memory")
async def update_memory(
    memory_id: str,
    updated_memory: MemoryUpdate,
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> Any:
    """
    Update an existing memory with new content.

    Args:
        memory_id: ID of the memory to update
        updated_memory: New content and optional metadata

    Returns:
        Raw mem0 API response
    """
    backend = _require_mem0()
    return backend.update(
        memory_id=memory_id,
        data=updated_memory.text,
        metadata=updated_memory.metadata,
    )


@router.delete("/memories/{memory_id}", summary="Delete a memory")
async def delete_memory(
    memory_id: str,
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> dict[str, str]:
    """
    Delete a specific memory by ID.

    Args:
        memory_id: Memory identifier

    Returns:
        Success message
    """
    backend = _require_mem0()
    backend.delete_memory(memory_id)
    return {"message": "Memory deleted successfully"}


@router.get("/memories/{memory_id}/history", summary="Get memory history")
async def memory_history(
    memory_id: str,
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> Any:
    """
    Retrieve memory edit history.

    Args:
        memory_id: Memory identifier

    Returns:
        List of history entries
    """
    backend = _require_mem0()
    return backend.history(memory_id)


@router.delete("/memories", summary="Delete all memories")
async def delete_all_memories(
    user_id: str | None = None,
    run_id: str | None = None,
    agent_id: str | None = None,
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> dict[str, str]:
    """
    Delete all memories for a given identifier.

    Args:
        user_id: User identifier
        run_id: Run identifier
        agent_id: Agent identifier

    Returns:
        Success message

    Raises:
        HTTPException: 400 if no identifier provided
    """
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one identifier is required.",
        )

    backend = _require_mem0()
    backend.delete_all(user_id=user_id, run_id=run_id, agent_id=agent_id)
    return {"message": "All relevant memories deleted"}


@router.post("/search", summary="Search memories")
async def search_memories(
    search_req: SearchRequest,
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> Any:
    """
    Search for memories based on a query.

    Args:
        search_req: SearchRequest body with query and filters

    Returns:
        List of matching memory dicts
    """
    backend = _require_mem0()

    params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
    return backend.search(query=search_req.query, **params)


@router.post("/reset", summary="Reset all memories")
async def reset_memories(
    _api_key: Annotated[str | None, Depends(verify_mem0_api_key)] = None,
) -> dict[str, str]:
    """
    Completely reset all stored memories.

    Returns:
        Success message
    """
    backend = _require_mem0()
    backend.reset()
    return {"message": "All memories reset"}


@router.get("/", summary="Redirect to docs", include_in_schema=False)
async def memories_home() -> RedirectResponse:
    """Redirect root to OpenAPI docs."""
    return RedirectResponse(url="/docs")
