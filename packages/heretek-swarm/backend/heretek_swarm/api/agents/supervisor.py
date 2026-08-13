"""
Supervisor-based agent endpoints.

Provides the supervisor-management surface for the swarm:
- GET  /                       → list all supervisor-managed actors
- GET  /{agent_id}/metrics     → get agent performance metrics
- POST /{agent_id}/terminate   → terminate an agent

Note: the bare GET /{agent_id} route was previously exposed here but is
now shadowed by instances.router's GET /{instance_id}, which serves as
the unified lookup endpoint — it checks supervisor.actors first (for
registered agent types like "steward") and falls back to the instance
registry (for deployed instance ids). The metrics and terminate
sub-paths remain uniquely owned by this router.

All routes use lazy import of get_supervisor() to avoid circular imports
(main.py → agents_management → supervisor → get_supervisor from actors.supervisor).
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException

from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger(__name__)

router = APIRouter()


def _uptime_seconds(created_at: str) -> float:
    """Compute uptime in seconds from an ISO-8601 created_at timestamp."""
    try:
        created = datetime.fromisoformat(created_at)
        now = datetime.now(UTC)
        return (now - created).total_seconds()
    except (ValueError, TypeError):
        return 0.0


@router.get("/")
async def list_supervisor_agents(authenticated: str = Depends(verify_auth)):
    """
    List all agents managed by the supervisor.

    Returns:
        {agents: [...], total: N}
    """
    from heretek_swarm.actors.supervisor import get_supervisor

    supervisor = get_supervisor()
    if not supervisor or not supervisor.actors:
        return {"agents": [], "total": 0}

    agents = []
    for agent_id, actor in supervisor.actors.items():
        status = actor.get_status()
        agents.append(
            {
                "id": agent_id,
                "type": actor.__class__.__name__,
                "status": status.state.value if status else "unknown",
                "message_count": status.message_count if status else 0,
                "error_count": status.error_count if status else 0,
                "last_activity": (
                    status.last_activity if status and status.last_activity else None
                ),
            }
        )

    return {"agents": agents, "total": len(agents)}


@router.get("/{agent_id}/metrics")
async def get_supervisor_agent_metrics(
    agent_id: str,
    authenticated: str = Depends(verify_auth),
):
    """
    Get performance metrics for a specific agent.

    Returns:
        {agent_id, messages_processed, errors, uptime_seconds}
    """
    from heretek_swarm.actors.supervisor import get_supervisor

    supervisor = get_supervisor()
    if not supervisor or agent_id not in supervisor.actors:
        raise HTTPException(404, f"Agent {agent_id} not found")

    actor = supervisor.actors[agent_id]
    status = actor.get_status()

    return {
        "agent_id": agent_id,
        "messages_processed": status.message_count if status else 0,
        "errors": status.error_count if status else 0,
        "uptime_seconds": (
            _uptime_seconds(status.created_at)
            if status and status.created_at
            else 0.0
        ),
    }


@router.post("/{agent_id}/terminate")
async def terminate_supervisor_agent(
    agent_id: str,
    authenticated: str = Depends(verify_auth),
):
    """
    Terminate a specific agent via the supervisor.

    Returns:
        {status: "terminated", agent_id}
    """
    from heretek_swarm.actors.supervisor import get_supervisor

    supervisor = get_supervisor()
    if not supervisor or agent_id not in supervisor.actors:
        raise HTTPException(404, f"Agent {agent_id} not found")

    await supervisor.terminate_actor(agent_id)

    return {
        "status": "terminated",
        "agent_id": agent_id,
    }
