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
from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.observability.metrics import (
    SwarmMetricsCollector,
    get_metrics_collector,
)
from heretek_swarm.observability.prometheus_metrics import (
    PrometheusMetrics,
    get_metrics,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# Singleton for metrics integration
_metrics: PrometheusMetrics | None = None


def get_prometheus_metrics() -> PrometheusMetrics:
    """Get or create the Prometheus metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = get_metrics()
    return _metrics


def sync_with_swarm_collector(collector: SwarmMetricsCollector) -> None:
    """
    Synchronize Prometheus metrics with the SwarmMetricsCollector.

    Call this periodically or on metrics collection to keep
    Prometheus metrics in sync with the internal metrics.

    Args:
        collector: The SwarmMetricsCollector instance
    """
    prom_metrics = get_prometheus_metrics()

    # Collect swarm metrics
    swarm_data = collector.collect_swarm_metrics()
    consciousness_data = collector.collect_consciousness_metrics()

    # Update agent counts
    # Note: Agent type tracking requires integration with the agent registry
    # For now, we track total and active without type breakdown

    # Update health score
    prom_metrics.record_health_score(swarm_data.health_score)

    # Update consciousness metrics
    for agent_id, phi_score in consciousness_data.agent_phi_scores.items():
        prom_metrics.record_phi_score(agent_id, phi_score)

    for agent_id, fep_score in consciousness_data.agent_fep_scores.items():
        prom_metrics.record_free_energy(agent_id, fep_score)

    # Aggregate phi and free energy for the swarm
    if consciousness_data.phi_avg > 0:
        prom_metrics.record_phi_score("swarm_avg", consciousness_data.phi_avg)

    if consciousness_data.free_energy_avg > 0:
        prom_metrics.record_free_energy("swarm_avg", consciousness_data.free_energy_avg)


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
    """
    Get Prometheus metrics for scraping.

    This endpoint is designed to be scraped by Prometheus at regular intervals
    (typically 15-60 seconds).

    Returns:
        PlainTextResponse: Metrics in Prometheus text exposition format

    Example Prometheus scrape config:
        scrape_configs:
          - job_name: 'heretek-swarm'
            static_configs:
              - targets: ['heretek-swarm:8000']
            metrics_path: /metrics
            scrape_interval: 15s
    """
    try:
        # Sync with swarm metrics collector if available
        try:
            collector = get_metrics_collector()
            sync_with_swarm_collector(collector)
        except Exception as e:
            logger.warning("Failed to sync with swarm collector", error=str(e))

        # Get Prometheus metrics
        prom_metrics = get_prometheus_metrics()

        # Export in Prometheus format
        metrics_output = prom_metrics.export_prometheus()
        content_type = prom_metrics.get_content_type()

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
    """
    Get current metrics in JSON format for debugging and monitoring.

    Returns:
        Dictionary of current metric values
    """
    try:
        collector = get_metrics_collector()
        sync_with_swarm_collector(collector)

        swarm_data = collector.collect_swarm_metrics()
        consciousness_data = collector.collect_consciousness_metrics()

        return {
            "swarm": swarm_data.to_dict(),
            "consciousness": consciousness_data.to_dict(),
            "health_score": collector.calculate_health_score(),
        }
    except Exception as e:
        logger.error("Failed to get metrics JSON", error=str(e))
        return {"error": "Failed to retrieve metrics"}
