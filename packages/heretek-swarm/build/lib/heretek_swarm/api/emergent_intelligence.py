"""
API Endpoints for Session 46: Emergent Intelligence Enhancement

Provides HTTP endpoints for:
- Swarm Intelligence Quotient (SIQ) metrics
- Collective efficiency metrics
- Knowledge transfer metrics
- Emergence coefficient
- Adaptive learning rate control
- Agent adaptation status
- Emergent pattern detection
- Real-time dashboard data

All endpoints require authentication and follow zero-trust principles.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from heretek_swarm.collective import (
    CollectiveIntelligenceMetrics,
    EmergenceLevel,
    EmergentPatternClass,
    MetricsExporter,
)
from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/emergent-intelligence", tags=["emergent-intelligence"])

# Global instances (initialized on first use)
_metrics_instance: CollectiveIntelligenceMetrics | None = None
_exporter_instance: MetricsExporter | None = None


def get_metrics_instance() -> CollectiveIntelligenceMetrics:
    """Get or create metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = CollectiveIntelligenceMetrics()
    return _metrics_instance


def get_exporter_instance() -> MetricsExporter:
    """Get or create exporter instance."""
    global _exporter_instance
    if _exporter_instance is None:
        _exporter_instance = MetricsExporter(get_metrics_instance())
    return _exporter_instance


@router.get("/dashboard")
async def get_dashboard_data(auth: dict = Depends(verify_auth)):  # noqa: B008
    """
    Get real-time metrics dashboard data.

    Returns comprehensive swarm metrics including:
    - Swarm health score
    - Swarm Intelligence Quotient (SIQ)
    - Collective efficiency
    - Emergence coefficient
    - Agent statistics
    - Pattern metrics
    - Learning metrics
    - Historical trends
    - Active alerts

    **Health Score Impact:** Positive - Provides observability
    """
    try:
        metrics = get_metrics_instance()
        dashboard = metrics.get_dashboard_data()

        return {
            "success": True,
            "data": dashboard.to_dict(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("dashboard_data_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {e!s}") from e


@router.get("/siq")
async def get_siq(
    auth: dict = Depends(verify_auth),  # noqa: B008
    include_history: bool = Query(False, description="Include historical SIQ data"),
    history_limit: int = Query(20, ge=1, le=100, description="Number of history items"),
):
    """
    Get Swarm Intelligence Quotient (SIQ) calculation.

    Returns:
    - Overall SIQ score (50-150 scale, 100 = average)
    - SIQ percentile
    - Component scores (coordination, adaptation, knowledge sharing, etc.)
    - Component weights and contributions
    - Historical trend (optional)

    **Health Score Impact:** Positive - Enables SIQ monitoring
    """
    try:
        metrics = get_metrics_instance()
        siq = await metrics.calculate_siq()
        result = siq.to_dict()

        if include_history:
            limit = int(history_limit)
            result["history"] = [s.to_dict() for s in metrics._siq_history[-limit:]]  # noqa: SLF001

        return {
            "success": True,
            "data": result,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("siq_calculation_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to calculate SIQ: {e!s}") from e


@router.get("/efficiency")
async def get_collective_efficiency(
    auth: dict = Depends(verify_auth),  # noqa: B008
    include_history: bool = Query(False, description="Include historical efficiency data"),
    history_limit: int = Query(20, ge=1, le=100, description="Number of history items"),
):
    """
    Get collective problem-solving efficiency metrics.

    Returns:
    - Task completion rate
    - Efficiency ratio
    - Resource utilization
    - Parallel efficiency
    - Solution quality metrics
    - Collective efficiency factor

    **Health Score Impact:** Positive - Enables efficiency monitoring
    """
    try:
        metrics = get_metrics_instance()
        efficiency = await metrics.calculate_collective_efficiency()
        result = efficiency.to_dict()

        if include_history:
            limit = int(history_limit)
            result["history"] = [e.to_dict() for e in metrics._efficiency_history[-limit:]]  # noqa: SLF001

        return {
            "success": True,
            "data": result,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("efficiency_calculation_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to calculate efficiency: {e!s}") from e


@router.get("/knowledge-transfer")
async def get_knowledge_transfer_metrics(
    auth: dict = Depends(verify_auth),  # noqa: B008
    include_history: bool = Query(False, description="Include historical transfer data"),
    history_limit: int = Query(20, ge=1, le=100, description="Number of history items"),
):
    """
    Get knowledge transfer rate metrics.

    Returns:
    - Patterns shared and adopted
    - Adoption rate
    - Transfer rate per hour
    - Knowledge flow (inflow/outflow/balance)
    - Network metrics (density, path length)
    - Knowledge retention rate

    **Health Score Impact:** Positive - Enables knowledge flow monitoring
    """
    try:
        metrics = get_metrics_instance()
        transfer = await metrics.calculate_knowledge_transfer()
        result = transfer.to_dict()

        if include_history:
            limit = int(history_limit)
            result["history"] = [t.to_dict() for t in metrics._transfer_history[-limit:]]  # noqa: SLF001

        return {
            "success": True,
            "data": result,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("knowledge_transfer_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate knowledge transfer: {e!s}"
        ) from e


@router.get("/emergence-coefficient")
async def get_emergence_coefficient(
    auth: dict = Depends(verify_auth),  # noqa: B008
    include_history: bool = Query(False, description="Include historical emergence data"),
    history_limit: int = Query(20, ge=1, le=100, description="Number of history items"),
):
    """
    Get emergence coefficient calculation.

    Returns:
    - Overall emergence coefficient (0.0-1.0)
    - Component coefficients (behavioral, structural, functional, cognitive)
    - Emergence indicators
    - Emergence type and strength classification

    **Health Score Impact:** Positive - Enables emergence monitoring
    """
    try:
        metrics = get_metrics_instance()
        coefficient = await metrics.calculate_emergence_coefficient()
        result = coefficient.to_dict()

        if include_history:
            limit = int(history_limit)
            result["history"] = [e.to_dict() for e in metrics._emergence_history[-limit:]]  # noqa: SLF001

        return {
            "success": True,
            "data": result,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("emergence_coefficient_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate emergence coefficient: {e!s}"
        ) from e


@router.get("/emergent-patterns")
async def get_emergent_patterns(
    auth: dict = Depends(verify_auth),  # noqa: B008
    pattern_class: EmergentPatternClass | None = Query(None, description="Filter by pattern class"),  # noqa: B008
    min_level: EmergenceLevel | None = Query(None, description="Minimum emergence level"),  # noqa: B008
    limit: int = Query(100, ge=1, le=500, description="Maximum patterns to return"),
):
    """
    Get detected emergent patterns.

    Returns patterns detected by the EmergentPatternDetector including:
    - Pattern classification
    - Emergence level
    - Participating agents
    - Emergence metrics
    - Validation status

    **Health Score Impact:** Positive - Enables pattern analysis
    """
    try:
        metrics = get_metrics_instance()
        detector = metrics.emergence_detector

        patterns = detector.get_emergent_patterns(
            pattern_class=pattern_class,
            min_emergence_level=min_level,
            limit=limit,
        )

        return {
            "success": True,
            "data": {
                "patterns": [p.to_dict() for p in patterns],
                "total_count": len(patterns),
                "statistics": detector.get_emergence_statistics(),
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("emergent_patterns_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get emergent patterns: {e!s}") from e  # noqa: E501


@router.get("/learning-rates")
async def get_learning_rates(
    auth: dict = Depends(verify_auth),  # noqa: B008
    agent_id: str | None = Query(None, description="Filter by specific agent ID"),
):
    """
    Get adaptive learning rates for agents.

    Returns:
    - Current learning rates per agent
    - Learning state (success rate, convergence)
    - Adaptation history
    - Convergence metrics

    **Health Score Impact:** Positive - Enables learning monitoring
    """
    try:
        metrics = get_metrics_instance()
        controller = metrics.learning_controller

        if agent_id:
            state = controller.get_agent_state(agent_id)
            convergence = controller.get_convergence_metrics(agent_id)
            data = {
                "agent_id": agent_id,
                "state": state.to_dict(),
                "convergence": convergence.to_dict(),
            }
        else:
            states = controller.get_all_agent_states()
            data = {
                "agents": {aid: s.to_dict() for aid, s in states.items()},
                "swarm_statistics": controller.get_swarm_statistics(),
            }

        return {
            "success": True,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("learning_rates_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get learning rates: {e!s}") from e


@router.get("/agent-adaptation")
async def get_agent_adaptation(
    auth: dict = Depends(verify_auth),  # noqa: B008
    agent_id: str | None = Query(None, description="Filter by specific agent ID"),
):
    """
    Get agent adaptation status.

    Returns:
    - Behavioral weights
    - Strategy profiles
    - Adaptation history
    - Adopted/rejected patterns
    - Audit log

    **Health Score Impact:** Positive - Enables adaptation monitoring
    """
    try:
        metrics = get_metrics_instance()
        adaptor = metrics.agent_adaptor

        if agent_id:
            state = adaptor.get_adaptation_state(agent_id)
            history = adaptor.get_adaptation_history(agent_id, limit=20)
            audit = adaptor.get_audit_log(agent_id, limit=20)
            data = {
                "agent_id": agent_id,
                "state": state.to_dict(),
                "recent_adaptations": [h.to_dict() for h in history],
                "recent_audit": [a.to_dict() for a in audit],
            }
        else:
            data = {
                "swarm_statistics": adaptor.get_swarm_adaptation_stats(),
                "total_agents": len(adaptor._agent_states),  # noqa: SLF001
            }

        return {
            "success": True,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("agent_adaptation_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get agent adaptation: {e!s}") from e


@router.get("/metrics-definitions")
async def get_metric_definitions(auth: dict = Depends(verify_auth)):  # noqa: B008
    """
    Get all registered metric definitions.

    Returns definitions of all available metrics including:
    - Metric name and description
    - Category
    - Unit of measurement
    - Aggregation method
    - Min/max/target values

    **Health Score Impact:** Positive - Provides metric documentation
    """
    try:
        metrics = get_metrics_instance()
        definitions = metrics.get_all_metric_definitions()

        return {
            "success": True,
            "data": {
                "definitions": [d.to_dict() for d in definitions],
                "total_count": len(definitions),
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("metric_definitions_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get metric definitions: {e!s}") from e  # noqa: E501


@router.get("/metrics/{metric_id}/timeseries")
async def get_metric_timeseries(
    metric_id: str,
    auth: dict = Depends(verify_auth),  # noqa: B008
    start_time: str | None = Query(None, description="Start time (ISO 8601)"),
    end_time: str | None = Query(None, description="End time (ISO 8601)"),
):
    """
    Get time series data for a specific metric.

    Returns historical values for the specified metric with optional time filtering.

    **Health Score Impact:** Positive - Enables historical analysis
    """
    try:
        metrics = get_metrics_instance()

        from datetime import datetime as dt

        start = dt.fromisoformat(start_time) if start_time else None
        end = dt.fromisoformat(end_time) if end_time else None

        series = metrics.get_metric_time_series(metric_id, start_time=start, end_time=end)

        return {
            "success": True,
            "data": series.to_dict(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {e!s}") from e
    except Exception as e:
        logger.error("metric_timeseries_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get metric time series: {e!s}") from e  # noqa: E501


@router.get("/export/summary")
async def export_summary(auth: dict = Depends(verify_auth)):  # noqa: B008
    """
    Export metrics summary.

    Returns a comprehensive summary of all current metrics suitable for
    reporting or dashboard display.

    **Health Score Impact:** Positive - Enables reporting
    """
    try:
        exporter = get_exporter_instance()
        summary = exporter.export_summary()

        return {
            "success": True,
            "data": summary,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("export_summary_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to export summary: {e!s}") from e


@router.get("/status")
async def get_emergent_intelligence_status(auth: dict = Depends(verify_auth)):  # noqa: B008
    """
    Get emergent intelligence system status.

    Returns overall status of all Session 46 components:
    - Adaptive learning controller
    - Agent adaptor
    - Emergence detector
    - Metrics calculator

    **Health Score Impact:** Positive - Provides system health
    """
    try:
        metrics = get_metrics_instance()

        status = {
            "metrics": metrics.get_status(),
            "learning_controller": metrics.learning_controller.get_status(),
            "agent_adaptor": metrics.agent_adaptor.get_status(),
            "emergence_detector": metrics.emergence_detector.get_status(),
            "pattern_library": (
                metrics.pattern_library.get_library_status() if metrics.pattern_library else None
            ),
        }

        return {
            "success": True,
            "data": status,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error("status_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e!s}") from e
