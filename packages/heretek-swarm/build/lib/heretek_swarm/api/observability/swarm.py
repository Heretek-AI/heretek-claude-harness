"""Swarm metrics endpoints for the observability API."""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.security.zero_trust import LayerResult, ZeroTrustResult

from . import (
    check_rate_limit,
    get_metrics_collector,
    get_zero_trust,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="", tags=["observability"])


@router.get("/swarm")
async def get_swarm_health(
    request: Request, authenticated: str = Depends(verify_auth)
) -> dict[str, Any]:
    """Get swarm health overview.

    Returns aggregate metrics including:
    - Total/active/idle agents
    - Task completion statistics
    - Message statistics
    - Overall health score (0-100)
    """
    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    validator = get_zero_trust()
    request_id = str(uuid.uuid4())
    audit_result = ZeroTrustResult(
        passed=True,
        layer1=LayerResult(layer="input_validation", passed=True),
        layer2=LayerResult(layer="context_validation", passed=True),
        layer3=LayerResult(layer="output_validation", passed=True),
        layer4=LayerResult(layer="audit_logging", passed=True),
        request_id=request_id,
    )
    validator.audit_logger.log(
        event_type="api_call",
        result=audit_result,
        additional_context={
            "endpoint": "/api/v1/observability/swarm",
            "client_id": client_id,
            "method": "GET",
        },
    )

    collector = get_metrics_collector()
    swarm_data = collector.collect_swarm_metrics()

    try:
        from heretek_swarm.api.autonomous import get_autonomous_agent_count_sync

        auto_agent_count = get_autonomous_agent_count_sync()
    except Exception as e:
        logger.warning("autonomous_agent_count_unavailable", error=str(e))
        auto_agent_count = 0

    result = swarm_data.to_dict()
    result["total_agents"] = result.get("total_agents", 0) + auto_agent_count
    result["active_agents"] = result.get("active_agents", 0) + auto_agent_count

    return {
        **result,
        "health_score": collector.calculate_health_score(),
    }


@router.get("/agents/{agent_id}")
async def get_agent_metrics(
    agent_id: str, request: Request, authenticated: str = Depends(verify_auth)
) -> dict[str, Any]:
    """Get individual agent metrics.

    Returns per-agent performance metrics including:
    - Tasks completed/failed
    - Average task duration
    - Messages sent/received
    - Error count
    - Health score
    """
    validator = get_zero_trust()
    from . import validate_input

    validate_input(validator, {"agent_id": agent_id}, "agent_id")

    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    request_id = str(uuid.uuid4())
    audit_result = ZeroTrustResult(
        passed=True,
        layer1=LayerResult(layer="input_validation", passed=True),
        layer2=LayerResult(layer="context_validation", passed=True),
        layer3=LayerResult(layer="output_validation", passed=True),
        layer4=LayerResult(layer="audit_logging", passed=True),
        request_id=request_id,
        agent_id=agent_id,
    )
    validator.audit_logger.log(
        event_type="api_call",
        result=audit_result,
        additional_context={
            "endpoint": f"/api/v1/observability/agents/{agent_id}",
            "client_id": client_id,
            "method": "GET",
        },
    )

    collector = get_metrics_collector()
    agent_data = collector.collect_agent_metrics(agent_id)

    return agent_data.to_dict()


@router.get("/agents")
async def get_all_agents(
    request: Request, authenticated: str = Depends(verify_auth)
) -> dict[str, Any]:
    """Get metrics for all agents.

    Returns:
        Dictionary mapping agent IDs to their metrics
    """
    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    collector = get_metrics_collector()
    agents = collector.get_all_agent_metrics()
    states = collector.get_agent_states()

    try:
        from heretek_swarm.api import autonomous as autonomous_module

        auto_agents = autonomous_module._autonomous_agents  # noqa: SLF001
        for agent_id, agent_data in auto_agents.items():
            if agent_id not in agents:
                agents[agent_id] = type(
                    "AutoAgentMetrics",
                    (),
                    {
                        "to_dict": lambda self, a=agent_data: {  # noqa: ARG005
                            "agent_id": a["agent_id"],
                            "agent_type": a["agent_type"],
                            "tasks_completed": 0,
                            "tasks_failed": a.get("error_count", 0),
                            "avg_task_duration_seconds": 0.0,
                            "messages_sent": a.get("message_count", 0),
                            "messages_received": 0,
                            "error_count": a.get("error_count", 0),
                            "success_rate": 1.0 if a.get("error_count", 0) == 0 else 0.0,
                            "health_score": 100.0 if a.get("state") == "running" else 50.0,
                            "last_activity": a.get("last_activity"),
                        },
                    },
                )()
                states[agent_id] = agent_data.get("state", "unknown")
    except Exception as e:
        logger.warning("autonomous_runtime_unavailable", error=str(e))

    return {
        "agents": {k: v.to_dict() for k, v in agents.items()},
        "states": states,
        "total_agents": len(agents),
        "timestamp": datetime.now(UTC).isoformat(),
    }
