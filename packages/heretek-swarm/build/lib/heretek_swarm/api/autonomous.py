"""
Autonomous Runtime Integration Endpoints.

Provides endpoints for the autonomous runtime to register its agents
and for the frontend to query autonomous agent status.

The autonomous runtime periodically POSTs agent status to this endpoint,
and the frontend queries it via GET.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger("api.autonomous")

router = APIRouter(
    prefix="/api/autonomous",
    tags=["autonomous"],
    dependencies=[Depends(verify_auth)],
)

# In-memory cache of autonomous agent statuses
# Key: agent_id, Value: status dict with timestamp
_autonomous_agents: dict[str, dict[str, Any]] = {}
_last_update: datetime | None = None
_cache_lock = asyncio.Lock()


def get_autonomous_agent_count_sync() -> int:
    """Synchronous access to agent count (for use in sync endpoints)."""
    return len(_autonomous_agents)


class AutonomousAgentStatus(BaseModel):
    """Agent status from the autonomous runtime."""

    agent_id: str
    agent_type: str
    state: str
    message_count: int = 0
    error_count: int = 0
    mailbox_size: int = 0
    last_activity: str | None = None
    uptime_seconds: float = 0.0


class AutonomousStatusUpdate(BaseModel):
    """Request model for autonomous runtime status updates."""

    runtime_id: str
    agents: list[AutonomousAgentStatus]
    total_agents: int
    uptime_seconds: float = 0.0


class AutonomousAgentsResponse(BaseModel):
    """Response model for autonomous agents query."""

    agents: list[AutonomousAgentStatus]
    total: int
    last_update: str | None
    healthy: bool


@router.post("/agents", status_code=200)
async def register_autonomous_agents(
    update: AutonomousStatusUpdate,
) -> dict[str, str]:
    """
    Receive agent status update from autonomous runtime.

    The autonomous runtime calls this endpoint periodically to register
    its running agents. This data is cached and served to the frontend.

    Args:
        update: Status update from autonomous runtime
    """
    global _autonomous_agents, _last_update

    async with _cache_lock:
        _autonomous_agents = {agent.agent_id: agent.model_dump() for agent in update.agents}
        _last_update = datetime.now(UTC)

    logger.debug(
        "autonomous_agents_registered",
        runtime_id=update.runtime_id,
        agent_count=update.total_agents,
    )

    return {"status": "ok", "agents": str(update.total_agents)}


@router.get("/agents")
async def get_autonomous_agents() -> AutonomousAgentsResponse:
    """
    Get current autonomous agent statuses.

    Returns the cached list of agents running in the autonomous runtime.
    This is queried by the frontend to display agent health.

    Returns:
        List of autonomous agents with their statuses
    """
    async with _cache_lock:
        agents = list(_autonomous_agents.values())
        total = len(agents)

    # Determine health: agents are healthy if we have data less than 2 minutes old
    healthy = True
    if _last_update:
        age = (datetime.now(UTC) - _last_update).total_seconds()
        healthy = age < 120

    return AutonomousAgentsResponse(
        agents=[AutonomousAgentStatus(**a) for a in agents],
        total=total,
        last_update=_last_update.isoformat() if _last_update else None,
        healthy=healthy,
    )


@router.get("/status")
async def get_autonomous_status() -> dict[str, Any]:
    """
    Get autonomous runtime status.

    Returns basic status about the autonomous runtime connection.
    """
    async with _cache_lock:
        agent_count = len(_autonomous_agents)

    return {
        "connected": _last_update is not None,
        "agent_count": agent_count,
        "last_update": _last_update.isoformat() if _last_update else None,
    }
