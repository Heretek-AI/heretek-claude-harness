"""Consciousness metrics endpoints for the observability API."""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request

from heretek_swarm.security.zero_trust import LayerResult, ZeroTrustResult

from . import (
    check_rate_limit,
    get_metrics_collector,
    get_zero_trust,
    validate_input,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="", tags=["observability"])


@router.get("/consciousness")
async def get_consciousness_metrics(request: Request) -> dict[str, Any]:
    """Get consciousness metrics (IIT Phi and FEP).

    Returns:
    - Phi scores (avg, max, min)
    - Integration/differentiation levels
    - Free energy metrics
    - Per-agent phi/fep scores
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
            "endpoint": "/api/v1/observability/consciousness",
            "client_id": client_id,
            "method": "GET",
        },
    )

    collector = get_metrics_collector()
    consciousness_data = collector.collect_consciousness_metrics()

    return consciousness_data.to_dict()


@router.get("/consciousness/agent/{agent_id}")
async def get_agent_consciousness(agent_id: str, request: Request) -> dict[str, Any]:
    """Get consciousness metrics for a specific agent."""
    validator = get_zero_trust()
    validate_input(validator, {"agent_id": agent_id}, "agent_id")

    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    collector = get_metrics_collector()
    consciousness_data = collector.collect_consciousness_metrics()

    agent_phi = consciousness_data.agent_phi_scores.get(agent_id, 0.0)
    agent_fep = consciousness_data.agent_fep_scores.get(agent_id, 0.0)

    return {
        "agent_id": agent_id,
        "phi_score": agent_phi,
        "fep_score": agent_fep,
        "timestamp": datetime.now(UTC).isoformat(),
    }
