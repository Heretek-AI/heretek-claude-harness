"""Alerts and provider-stats endpoints for the observability API."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from heretek_swarm.security.zero_trust import LayerResult, ZeroTrustResult

from heretek_swarm.gateway.auth import verify_auth

from . import (
    check_rate_limit,
    get_metrics_collector,
    get_zero_trust,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="", tags=["observability"])


@router.get("/alerts")
async def get_alerts(
    request: Request,
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """Get active alerts and anomalies.

    Returns alerts for:
    - Agents with low health scores
    - High error rates
    - Low consciousness metrics
    - System anomalies
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
            "endpoint": "/api/v1/observability/alerts",
            "client_id": client_id,
            "method": "GET",
        },
    )

    collector = get_metrics_collector()
    alerts: list[dict[str, Any]] = []

    agents = collector.get_all_agent_metrics()
    for agent_id, metrics in agents.items():
        if metrics.health_score < 50:
            alerts.append(
                {
                    "alert_id": f"health_{agent_id}",
                    "severity": "critical" if metrics.health_score < 30 else "warning",
                    "type": "low_health",
                    "agent_id": agent_id,
                    "message": f"Agent {agent_id} health score is {metrics.health_score:.1f}",
                    "value": metrics.health_score,
                    "threshold": 50,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

        if metrics.error_count > 10:
            alerts.append(
                {
                    "alert_id": f"errors_{agent_id}",
                    "severity": "warning",
                    "type": "high_errors",
                    "agent_id": agent_id,
                    "message": f"Agent {agent_id} has {metrics.error_count} errors",
                    "value": metrics.error_count,
                    "threshold": 10,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

    consciousness = collector.collect_consciousness_metrics()
    if consciousness.phi_avg < 0.3:
        alerts.append(
            {
                "alert_id": "low_phi",
                "severity": "warning",
                "type": "low_consciousness",
                "message": f"Average Phi score is {consciousness.phi_avg:.3f}",
                "value": consciousness.phi_avg,
                "threshold": 0.3,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    overall_health = collector.calculate_health_score()
    if overall_health < 60:
        alerts.append(
            {
                "alert_id": "low_swarm_health",
                "severity": "critical" if overall_health < 40 else "warning",
                "type": "low_swarm_health",
                "message": f"Swarm health score is {overall_health:.1f}",
                "value": overall_health,
                "threshold": 60,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    return {
        "alerts": alerts,
        "total_alerts": len(alerts),
        "critical_alerts": sum(1 for a in alerts if a["severity"] == "critical"),
        "warning_alerts": sum(1 for a in alerts if a["severity"] == "warning"),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/provider-stats")
async def get_provider_stats(request: Request) -> dict[str, Any]:
    """Get aggregate LLM provider usage statistics across all agents.

    Returns per-provider totals (requests, cost, tokens) and per-model
    breakdowns aggregated from every registered AgentModelRouter, plus
    grand totals.
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
            "endpoint": "/api/v1/observability/provider-stats",
            "client_id": client_id,
            "method": "GET",
        },
    )

    from heretek_swarm.routing.model_router import get_all_provider_stats

    return get_all_provider_stats()
