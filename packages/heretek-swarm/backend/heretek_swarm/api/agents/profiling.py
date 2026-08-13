"""Behavior profiling endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.runtime.registry_enhanced import EnhancedAgentRegistry, get_enhanced_registry

logger = structlog.get_logger()
router = APIRouter()


def get_registry() -> EnhancedAgentRegistry:
    """Dependency to get the enhanced agent registry."""
    return get_enhanced_registry()


PROFILING_AVAILABLE = True

try:
    from heretek_swarm.actors.profiling import (
        ActionType,
        AlertSeverity,
        BehaviorProfiler,
        ProfilingConfig,
        get_profiler,
    )
except ImportError:
    PROFILING_AVAILABLE = False
    get_profiler = None
    BehaviorProfiler = None
    ActionType = None
    AlertSeverity = None
    ProfilingConfig = None


def get_profiler_instance() -> "BehaviorProfiler | None":
    """Dependency to get the behavior profiler."""
    if PROFILING_AVAILABLE and get_profiler:
        return get_profiler()
    return None


class ProfilingMetricsResponse(BaseModel):
    """Response model for agent profiling metrics."""

    agentId: str
    totalActions: int = 0
    actionsPerMinute: float = 0.0
    messageSentCount: int = 0
    messageReceivedCount: int = 0
    tasksStarted: int = 0
    tasksCompleted: int = 0
    tasksFailed: int = 0
    taskSuccessRate: float = 0.0
    avgTaskDurationMs: float = 0.0
    errorCount: int = 0
    errorRate: float = 0.0
    avgResponseTimeMs: float = 0.0
    maxResponseTimeMs: float = 0.0
    minResponseTimeMs: float = 0.0
    responseTimeStddev: float = 0.0
    stateChanges: int = 0


class ProfilingProfileResponse(BaseModel):
    """Response model for behavior profile."""

    agentType: str
    createdAt: str
    updatedAt: str
    baselineActionsPerMinute: float = 0.0
    baselineTaskSuccessRate: float = 1.0
    baselineAvgTaskDurationMs: float = 0.0
    baselineErrorRate: float = 0.0
    baselineResponseTimeMs: float = 0.0
    sampleCount: int = 0


class AnomalyResponse(BaseModel):
    """Response model for detected anomaly."""

    timestamp: str
    agentId: str
    anomalyType: str
    severity: str
    description: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    expectedValue: float = 0.0
    actualValue: float = 0.0


class AlertResponse(BaseModel):
    """Response model for alert."""

    timestamp: str
    agentId: str
    anomaly: AnomalyResponse
    message: str
    acknowledged: bool
    acknowledgedAt: str | None = None
    acknowledgedBy: str | None = None


class ProfilingStatsResponse(BaseModel):
    """Response model for profiler statistics."""

    totalActivitiesRecorded: int
    totalAnomaliesDetected: int
    totalAlertsGenerated: int
    profilesCreated: int
    activeAgents: int
    profilesCount: int
    unacknowledgedAlerts: int


@router.get("/{instance_id}/profiling/metrics")
async def get_agent_profiling_metrics(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    profiler: Annotated[BehaviorProfiler | None, Depends(get_profiler_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> ProfilingMetricsResponse:
    """
    Get behavior profiling metrics for an agent.

    Args:
        instance_id: Agent instance ID

    Returns:
        Agent behavior metrics
    """
    if not PROFILING_AVAILABLE or not profiler:
        raise HTTPException(503, "Behavior profiling not available")

    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    # Compute and get metrics
    metrics = profiler.compute_metrics(instance_id)

    if not metrics:
        return ProfilingMetricsResponse(agentId=instance_id)

    return ProfilingMetricsResponse(
        agentId=instance_id,
        totalActions=metrics.total_actions,
        actionsPerMinute=metrics.actions_per_minute,
        messageSentCount=metrics.message_sent_count,
        messageReceivedCount=metrics.message_received_count,
        tasksStarted=metrics.tasks_started,
        tasksCompleted=metrics.tasks_completed,
        tasksFailed=metrics.tasks_failed,
        taskSuccessRate=metrics.task_success_rate,
        avgTaskDurationMs=metrics.avg_task_duration_ms,
        errorCount=metrics.error_count,
        errorRate=metrics.error_rate,
        avgResponseTimeMs=metrics.avg_response_time_ms,
        maxResponseTimeMs=metrics.max_response_time_ms,
        minResponseTimeMs=metrics.min_response_time_ms,
        responseTimeStddev=metrics.response_time_stddev,
        stateChanges=metrics.state_changes,
    )


@router.get("/{instance_id}/profiling/profile")
async def get_agent_profiling_profile(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    profiler: Annotated[BehaviorProfiler | None, Depends(get_profiler_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> ProfilingProfileResponse:
    """
    Get behavior profile for an agent's type.

    Args:
        instance_id: Agent instance ID

    Returns:
        Behavior profile for the agent type
    """
    if not PROFILING_AVAILABLE or not profiler:
        raise HTTPException(503, "Behavior profiling not available")

    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    # Get agent type from instance
    agent_type = instance.agent_type

    # Update profile with current data
    profiler.update_profile(agent_type, instance_id)

    # Get profile
    profile = profiler.get_profile(agent_type)

    if not profile:
        raise HTTPException(404, f"No profile available for agent type '{agent_type}'")

    return ProfilingProfileResponse(
        agentType=profile.agent_type,
        createdAt=profile.created_at.isoformat(),
        updatedAt=profile.updated_at.isoformat(),
        baselineActionsPerMinute=profile.baseline_actions_per_minute,
        baselineTaskSuccessRate=profile.baseline_task_success_rate,
        baselineAvgTaskDurationMs=profile.baseline_avg_task_duration_ms,
        baselineErrorRate=profile.baseline_error_rate,
        baselineResponseTimeMs=profile.baseline_response_time_ms,
        sampleCount=profile.sample_count,
    )


@router.get("/{instance_id}/profiling/anomalies")
async def detect_agent_anomalies(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    profiler: Annotated[BehaviorProfiler | None, Depends(get_profiler_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> list[AnomalyResponse]:
    """
    Detect anomalies in agent behavior.

    Args:
        instance_id: Agent instance ID

    Returns:
        List of detected anomalies
    """
    if not PROFILING_AVAILABLE or not profiler:
        raise HTTPException(503, "Behavior profiling not available")

    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    # Detect anomalies
    anomalies = profiler.detect_anomalies(instance_id)

    return [
        AnomalyResponse(
            timestamp=a.timestamp.isoformat(),
            agentId=a.agent_id,
            anomalyType=a.anomaly_type.value,
            severity=a.severity.value,
            description=a.description,
            metrics=a.metrics,
            expectedValue=a.expected_value,
            actualValue=a.actual_value,
        )
        for a in anomalies
    ]


@router.get("/profiling/alerts")
async def get_profiling_alerts(
    profiler: Annotated[BehaviorProfiler | None, Depends(get_profiler_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
    severity: str | None = None,
    unacknowledged_only: bool = False,
) -> list[AlertResponse]:
    """
    Get all profiling alerts.

    Args:
        severity: Filter by severity (low, medium, high, critical)
        unacknowledged_only: Only return unacknowledged alerts

    Returns:
        List of alerts
    """
    if not PROFILING_AVAILABLE or not profiler:
        raise HTTPException(503, "Behavior profiling not available")

    # Parse severity
    severity_filter = None
    if severity:
        try:
            severity_filter = AlertSeverity(severity.lower())
        except ValueError:
            raise HTTPException(400, f"Invalid severity: {severity}")

    # Get alerts
    alerts = profiler.get_alerts(
        severity=severity_filter,
        unacknowledged_only=unacknowledged_only,
    )

    return [
        AlertResponse(
            timestamp=a.timestamp.isoformat(),
            agentId=a.agent_id,
            anomaly=AnomalyResponse(
                timestamp=a.anomaly.timestamp.isoformat(),
                agentId=a.anomaly.agent_id,
                anomalyType=a.anomaly.anomaly_type.value,
                severity=a.anomaly.severity.value,
                description=a.anomaly.description,
                metrics=a.anomaly.metrics,
                expectedValue=a.anomaly.expected_value,
                actualValue=a.anomaly.actual_value,
            ),
            message=a.message,
            acknowledged=a.acknowledged,
            acknowledgedAt=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            acknowledgedBy=a.acknowledged_by,
        )
        for a in alerts
    ]


@router.post("/profiling/alerts/{index}/acknowledge")
async def acknowledge_profiling_alert(
    index: int,
    acknowledged_by: str,
    profiler: Annotated[BehaviorProfiler | None, Depends(get_profiler_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Acknowledge a profiling alert.

    Args:
        index: Alert index in list
        acknowledged_by: User/system acknowledging

    Returns:
        Success status
    """
    if not PROFILING_AVAILABLE or not profiler:
        raise HTTPException(503, "Behavior profiling not available")

    if not profiler.acknowledge_alert(index, acknowledged_by):
        raise HTTPException(404, f"Alert at index {index} not found")

    return {"status": "success", "message": f"Alert {index} acknowledged"}


@router.get("/profiling/stats")
async def get_profiling_stats(
    profiler: Annotated[BehaviorProfiler | None, Depends(get_profiler_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> ProfilingStatsResponse:
    """
    Get profiler statistics.

    Returns:
        Profiler statistics
    """
    if not PROFILING_AVAILABLE or not profiler:
        raise HTTPException(503, "Behavior profiling not available")

    stats = profiler.get_stats()

    return ProfilingStatsResponse(
        totalActivitiesRecorded=stats["total_activities_recorded"],
        totalAnomaliesDetected=stats["total_anomalies_detected"],
        totalAlertsGenerated=stats["total_alerts_generated"],
        profilesCreated=stats["profiles_created"],
        activeAgents=stats["active_agents"],
        profilesCount=stats["profiles_count"],
        unacknowledgedAlerts=stats["alerts_count"],
    )


@router.get("/profiling/prometheus")
async def get_profiling_prometheus_metrics(
    profiler: Annotated[BehaviorProfiler | None, Depends(get_profiler_instance)],
) -> str:
    """
    Get profiling metrics in Prometheus format.

    Returns:
        Prometheus-formatted metrics string
    """
    if not PROFILING_AVAILABLE or not profiler:
        return "# Behavior profiling not available\n"

    return profiler.export_prometheus_metrics()


@router.post("/{instance_id}/profiling/record")
async def record_agent_activity(
    instance_id: str,
    action: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    profiler: Annotated[BehaviorProfiler | None, Depends(get_profiler_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
    duration_ms: float = 0.0,
    success: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Record an agent activity for profiling.

    Args:
        instance_id: Agent instance ID
        action: Action type (message_sent, task_completed, etc.)
        duration_ms: Action duration in milliseconds
        success: Whether action was successful
        metadata: Additional metadata

    Returns:
        Success status
    """
    if not PROFILING_AVAILABLE or not profiler:
        raise HTTPException(503, "Behavior profiling not available")

    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    # Parse action type
    try:
        action_type = ActionType(action.lower())
    except ValueError:
        action_type = ActionType.CUSTOM

    # Record activity
    profiler.record_activity(
        agent_id=instance_id,
        action=action_type,
        metadata=metadata or {},
        duration_ms=duration_ms,
        success=success,
    )

    return {"status": "success", "message": f"Activity recorded: {action}"}


# =============================================================================
