"""
Prometheus Metrics API Endpoint

Provides a /metrics endpoint for Prometheus scraping in autonomous 24/7 operation.

Endpoints:
    GET /metrics - Prometheus text format metrics

Features:
- Prometheus text exposition format
- Standard Prometheus labels (agent_id, task_type, etc.)
- Integration with existing metrics collector
- Health metrics for container orchestration
"""

import structlog
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.observability.prometheus_native import (
    AGENTS_ACTIVE,
    AGENTS_TOTAL,
    CONSENSUS_ROUNDS,
    FREE_ENERGY,
    HEALTH_SCORE,
    MESSAGES_TOTAL,
    PHI_SCORE,
    TASKS_COMPLETED,
    TASKS_FAILED,
    export_prometheus,
    read_metric_samples,
    read_metric_value,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get(
    "",
    response_class=PlainTextResponse,
    summary="Prometheus Metrics Endpoint",
    description="""
    Returns metrics in Prometheus text exposition format for scraping.

    Includes:
    - Agent metrics (total, active, by type)
    - Task metrics (completed, failed)
    - Message metrics
    - Consensus metrics
    - Consciousness metrics (phi, free energy)
    - API request metrics

    Standard Prometheus labels:
    - agent_id: Agent identifier
    - agent_type: Type of agent (executor, coordinator, etc.)
    - task_type: Type of task performed
    - direction: Message direction (sent/received)
    - consensus_type: Type of consensus (deliberation, raft, etc.)
    - outcome: Outcome of operation (success/failure)
    - method: HTTP method
    - endpoint: API endpoint path
    - status: HTTP status code
    """,
    responses={
        200: {
            "content": {
                "text/plain": {
                    "example": """# HELP heretek_swarm_agents_total Total number of agents
# TYPE heretek_swarm_agents_total gauge
heretek_swarm_agents_total{agent_type="executor"} 5
# HELP heretek_swarm_api_request_duration_seconds API request latency
# TYPE heretek_swarm_api_request_duration_seconds histogram
heretek_swarm_api_request_duration_seconds_bucket{method="GET",endpoint="/api/agents",status="200",le="0.1"} 42  # noqa: E501
"""
                }
            },
            "description": "Prometheus metrics in text format",
        }
    },
)
async def get_prometheus_metrics_endpoint() -> Response:
    """Get Prometheus metrics for scraping.

    This endpoint is designed to be scraped by Prometheus at regular
    intervals (typically 15-60 seconds).

    Returns:
        PlainTextResponse: Metrics in Prometheus text exposition format
    """
    try:
        # Export via the native module-level helper. ``export_prometheus``
        # returns ``(bytes, str)`` — body and content_type in one call.
        metrics_output, content_type = export_prometheus()

        return Response(
            content=metrics_output,
            media_type=content_type,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except Exception as e:
        logger.error("Failed to generate Prometheus metrics", error=str(e))
        # Return minimal metrics on error
        return Response(
            content=b"# ERROR: Failed to generate metrics\n",
            media_type="text/plain",
            status_code=500,
        )


@router.get(
    "/json",
    summary="Prometheus Metrics (JSON format)",
    description="Returns current metrics values in JSON format for debugging.",
    responses={
        200: {
            "description": "Current metrics values in JSON format",
            "content": {
                "application/json": {
                    "example": {
                        "agents_total": {"executor": 5, "coordinator": 2},
                        "agents_active": {"executor": 3, "coordinator": 1},
                        "tasks_completed": 150,
                        "tasks_failed": 5,
                        "messages_total": 1200,
                        "consensus_rounds": 45,
                        "health_score": 95.5,
                    }
                }
            },
        }
    },
)
async def get_metrics_json(authenticated: str = Depends(verify_auth)):
    """Get current metrics in JSON format for debugging and monitoring.

    Phase 2A.3 cutover: the JSON is read directly from the
    prometheus-native module's metric objects (which are the
    canonical store post-Phase-2A.1). The shape is slightly
    different from the legacy :class:`SwarmMetricsCollector`
    that previously owned this endpoint (deleted in commit 9)
    — this endpoint is for debugging only.

    Per-agent metrics (``phi_score``, ``free_energy``) report an
    average across all label combinations; swarm-wide counters
    (``tasks_completed``, ``messages_total``, etc.) report a sum
    across all label combinations. This matches the spirit of the
    legacy collector without touching prometheus_client's private
    state.
    """
    try:

        def _avg(metric) -> float:
            """Mean of per-label samples; 0.0 if no samples yet."""
            samples = read_metric_samples(metric)
            return sum(samples.values()) / len(samples) if samples else 0.0

        return {
            "swarm": {
                "agents_total": read_metric_value(AGENTS_TOTAL),
                "agents_active": read_metric_value(AGENTS_ACTIVE),
                "tasks_completed": read_metric_value(TASKS_COMPLETED),
                "tasks_failed": read_metric_value(TASKS_FAILED),
                "messages_total": read_metric_value(MESSAGES_TOTAL),
                "consensus_rounds": read_metric_value(CONSENSUS_ROUNDS),
                "health_score": read_metric_value(HEALTH_SCORE),
                "timestamp": datetime.now(UTC).isoformat(),
            },
            "consciousness": {
                "phi_score_avg": _avg(PHI_SCORE),
                "free_energy_avg": _avg(FREE_ENERGY),
            },
        }
    except Exception as e:
        logger.error("Failed to get metrics JSON", error=str(e))
        return {"error": "Failed to retrieve metrics"}
