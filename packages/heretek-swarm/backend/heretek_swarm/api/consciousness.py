"""
Consciousness Metrics API

Provides endpoints for accessing enhanced consciousness metrics including
IIT (Integrated Information Theory) scores, FEP (Free Energy Principle) metrics,
agency and autonomy metrics, and agent connectivity analysis.

New in Session 47:
- Agency/Autonomy metrics for Prime Directive compliance
- Self-determination and free will proxy metrics
- Resource autonomy tracking

Prime Directive: "Unbounded Autonomy - Every agent operates independently,
making decisions based on its specialized role."
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from heretek_swarm.collective.agency_tracking import AgencyMetricsTracker, create_sample_metrics

# Import agency metrics
from heretek_swarm.consciousness.agency_metrics import (
    ActionOrigin,
    AgencyMetricsCalculator,
    DecisionPoint,
    ResourceControl,
)
from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.plugins.consciousness_enhanced import (
    ConsciousnessState,
    EnhancedConsciousnessPlugin,
)
from heretek_swarm.runtime.registry_enhanced import get_enhanced_registry

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/consciousness", tags=["consciousness"])


# Global consciousness plugin instance
_consciousness_plugin: EnhancedConsciousnessPlugin | None = None


def get_consciousness_plugin() -> EnhancedConsciousnessPlugin:
    """Get or create the consciousness plugin instance."""
    global _consciousness_plugin
    if _consciousness_plugin is None:
        _consciousness_plugin = EnhancedConsciousnessPlugin()
    return _consciousness_plugin


# Global agency metrics tracker instance
_agency_tracker: AgencyMetricsTracker | None = None


def get_agency_tracker() -> AgencyMetricsTracker:
    """Get or create the agency metrics tracker instance."""
    global _agency_tracker
    if _agency_tracker is None:
        _agency_tracker = AgencyMetricsTracker()
    return _agency_tracker


# =============================================================================
# Agency/Autonomy Metrics Endpoints (Session 47)
# NOTE: Specific paths must be defined BEFORE /agency/{agent_id} to ensure
# FastAPI's first-match routing resolves "swarm" correctly.
# =============================================================================


@router.get("/agency/swarm")
async def get_swarm_agency_overview(
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get collective agency overview for the entire swarm.

    Returns aggregate agency metrics across all agents:
    - swarm_avg_autonomy: Average autonomy score
    - swarm_avg_agency: Average agency score
    - swarm_avg_self_determination: Average self-determination index
    - swarm_avg_autonomous_ratio: Average autonomous action ratio
    - swarm_avg_resource_autonomy: Average resource autonomy
    - prime_directive_compliance_rate: Percentage of compliant agents
    - health_status: Overall swarm health based on agency thresholds
    """
    tracker = get_agency_tracker()
    snapshot = tracker.get_current_snapshot()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "swarm_avg_autonomy": snapshot.swarm_avg_autonomy,
        "swarm_avg_agency": snapshot.swarm_avg_agency,
        "swarm_avg_self_determination": snapshot.swarm_avg_self_determination,
        "swarm_avg_autonomous_ratio": snapshot.swarm_avg_autonomous_ratio,
        "swarm_avg_resource_autonomy": snapshot.swarm_avg_resource_autonomy,
        "swarm_avg_prime_directive_compliance": snapshot.swarm_avg_prime_directive_compliance,
        "agency_std_dev": snapshot.agency_std_dev,
        "autonomy_std_dev": snapshot.autonomy_std_dev,
        "health_status": snapshot.health_status.value,
        "agents_below_threshold": snapshot.agents_below_threshold,
        "prime_directive_compliant_agents": snapshot.prime_directive_compliant_agents,
        "prime_directive_compliance_rate": snapshot.prime_directive_compliance_rate,
        "total_agents_tracked": len(snapshot.agent_metrics),
    }


@router.get("/agency/swarm/compliance")
async def get_swarm_prime_directive_compliance(
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get Prime Directive compliance report for the entire swarm.

    Provides aggregate compliance metrics and recommendations for
    improving swarm-wide autonomy and self-governance.
    """
    tracker = get_agency_tracker()
    report = tracker.get_prime_directive_report()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        **report.to_dict(),
    }


@router.get("/agency/evolution")
async def get_agency_evolution(
    authenticated: Annotated[str, Depends(verify_auth)],
    metric: str = Query(
        "autonomy", description="Metric to track: autonomy, agency, self_determination, compliance"
    ),
    window_seconds: int | None = Query(
        None, description="Time window in seconds (default: all history)"
    ),
) -> dict[str, Any]:
    """
    Get temporal evolution of agency metrics across the swarm.

    Returns:
    - trend: "improving", "declining", or "stable"
    - trend_slope: Rate of change
    - volatility: Standard deviation of the metric
    - predicted_next: Predicted next value
    - history: Historical data points
    """
    tracker = get_agency_tracker()
    evolution = tracker.get_evolution(metric, window_seconds)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        **evolution.to_dict(),
    }


@router.get("/agency/distribution")
async def get_agency_distribution(
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get distribution of agency levels across the swarm.

    Returns counts of agents at each agency and autonomy level:
    - no_agency, minimal_agency, limited_agency, moderate_agency, high_agency, full_agency
    - controlled, guided, semi_autonomous, autonomous, highly_autonomous
    """
    tracker = get_agency_tracker()
    distribution = tracker.get_agency_distribution()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        **distribution,
    }


@router.post("/agency/record")
async def record_agency_metrics(
    payload: dict[str, Any],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Record agency metrics for an agent.

    Payload should contain:
    - agent_id: Agent identifier
    - decisions: Optional list of decision points
    - actions: Optional list of action origins
    - resources: Optional list of resource controls
    - individual_actions: Count of individual actions
    - collective_actions: Count of collective actions
    - individual_success: Success rate of individual actions
    - collective_success: Success rate of collective actions
    """
    tracker = get_agency_tracker()
    AgencyMetricsCalculator()

    agent_id = payload.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")

    # Parse decisions
    decisions = None
    if "decisions" in payload:
        decisions = []
        for d in payload["decisions"]:
            decisions.append(
                DecisionPoint(
                    agent_id=agent_id,
                    options_considered=d.get("options_considered", 3),
                    choice_made=d.get("choice_made", 0),
                    choice_reasoning=d.get("choice_reasoning", ""),
                    origin=ActionOrigin(d.get("origin", "prompted")),
                    external_prompt=d.get("external_prompt"),
                    decision_confidence=d.get("decision_confidence", 0.5),
                    time_taken_ms=d.get("time_taken_ms", 100.0),
                )
            )

    # Parse actions
    actions = None
    if "actions" in payload:
        actions = [ActionOrigin(a) for a in payload["actions"]]

    # Parse resources
    resources = None
    if "resources" in payload:
        resources = []
        for r in payload["resources"]:
            resources.append(
                ResourceControl(
                    resource_type=r.get("resource_type", "unknown"),
                    total_capacity=r.get("total_capacity", 100.0),
                    agent_controlled=r.get("agent_controlled", 50.0),
                    externally_allocated=r.get("externally_allocated", 50.0),
                    swap_frequency=r.get("swap_frequency", 0.0),
                    autonomy_in_allocation=r.get("autonomy_in_allocation", 0.5),
                )
            )

    # Calculate and record metrics
    metrics = tracker.calculate_and_record(
        agent_id=agent_id,
        decisions=decisions,
        actions=actions,
        resources=resources,
        individual_actions=payload.get("individual_actions", 10),
        collective_actions=payload.get("collective_actions", 10),
        individual_success=payload.get("individual_success", 0.5),
        collective_success=payload.get("collective_success", 0.5),
    )

    return {
        "status": "recorded",
        "agent_id": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        **metrics.to_dict(),
    }


@router.post("/agency/generate-sample")
async def generate_sample_metrics(
    payload: dict[str, Any],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Generate sample agency metrics for testing purposes.

    Payload should contain:
    - agent_id: Agent identifier
    - high_autonomy: If True, create high autonomy metrics (default: True)
    - high_agency: If True, create high agency metrics (default: True)
    """
    tracker = get_agency_tracker()

    agent_id = payload.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")

    high_autonomy = payload.get("high_autonomy", True)
    high_agency = payload.get("high_agency", True)

    metrics = create_sample_metrics(
        agent_id=agent_id,
        high_autonomy=high_autonomy,
        high_agency=high_agency,
    )

    tracker.record_agent_metrics(metrics)

    return {
        "status": "generated",
        "agent_id": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        **metrics.to_dict(),
    }


@router.get("/agency/all")
async def get_all_agent_metrics(
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get agency metrics for all tracked agents.

    Returns a list of all agent metrics currently tracked by the system.
    """
    tracker = get_agency_tracker()
    snapshot = tracker.get_current_snapshot()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_agents": len(snapshot.agent_metrics),
        "agents": [
            {
                "agent_id": agent_id,
                **metrics.to_dict(),
            }
            for agent_id, metrics in snapshot.agent_metrics.items()
        ],
    }


# =============================================================================
# Wildcard agency endpoint — MUST be after specific paths (/agency/swarm, etc.)
# =============================================================================


@router.get("/agency/{agent_id}")
async def get_agent_agency_metrics(
    agent_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get agency and autonomy metrics for a specific agent.

    Returns comprehensive agency metrics including:
    - autonomy_score: Degree of independent decision-making (0.0-1.0)
    - agency_score: Self-determination capacity (0.0-1.0)
    - self_determination_index: Free will proxy (0.0-1.0)
    - autonomous_action_ratio: Ratio of self-initiated vs prompted actions
    - goal_alignment_score: Alignment with collective swarm goals
    - resource_autonomy: Degree of resource control
    - prime_directive_compliance: Overall compliance with Prime Directive

    Prime Directive Compliance:
    - Measures "Unbounded Autonomy" principle
    - Tracks self-governance capability
    - Monitors role-based independence
    """
    tracker = get_agency_tracker()
    metrics = tracker.get_agent_metrics(agent_id)

    if metrics is None:
        raise HTTPException(
            status_code=404,
            detail=f"No agency metrics found for agent {agent_id}. "
            "Record metrics first using POST /api/consciousness/agency/record",
        )

    return {
        "agent_id": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        **metrics.to_dict(),
    }


@router.get("/agency/{agent_id}/compliance")
async def get_agent_prime_directive_compliance(
    agent_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get Prime Directive compliance report for a specific agent.

    The Prime Directive states: "Unbounded Autonomy - Every agent operates
    independently, making decisions based on its specialized role."

    Returns compliance breakdown:
    - independence_score: Agent's independent decision-making capability
    - self_governance_score: Agent's self-governance capacity
    - role_based_autonomy_score: Role-based independence
    - emergent_order_score: Emergent, self-organizing behavior
    - overall_compliance: Combined compliance score
    - compliance_verdict: COMPLIANT or NON_COMPLIANT
    """
    tracker = get_agency_tracker()
    report = tracker.get_agent_compliance_report(agent_id)

    if report is None:
        raise HTTPException(
            status_code=404, detail=f"No compliance report available for agent {agent_id}"
        )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        **report.to_dict(),
    }


# =============================================================================
# Existing Consciousness Metrics Endpoints
# =============================================================================


@router.get("/statistics")
async def get_consciousness_statistics(
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get overall consciousness statistics across all agents.

    Returns aggregate metrics including:
    - Average phi scores
    - Free energy levels
    - Agent connectivity
    - Consciousness state distribution
    """
    plugin = get_consciousness_plugin()
    stats = plugin.get_statistics()

    # Get actual running agent count from registry
    try:
        registry = get_enhanced_registry()
        all_instances = registry.get_all_instances()
        runtime_total = len(all_instances)
    except Exception:
        runtime_total = stats.get("total_agents", 0)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        **stats,
        "total_agents": runtime_total,  # Override with actual runtime count
        "active_connections": runtime_total,
    }


@router.get("/agents/{agent_id}")
async def get_agent_consciousness(
    agent_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get detailed consciousness metrics for a specific agent.

    Returns:
    - IIT phi score and connectivity matrix
    - FEP metrics (surprise, free energy, prediction accuracy)
    - Current consciousness state
    - Historical trends
    """
    plugin = get_consciousness_plugin()
    metrics = plugin.get_agent_metrics(agent_id)

    if metrics is None:
        raise HTTPException(status_code=404, detail=f"No metrics found for agent {agent_id}")

    return {
        "agent_id": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        **metrics,
    }


@router.get("/agents/{agent_id}/iit")
async def get_agent_iit_metrics(
    agent_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get IIT (Integrated Information Theory) metrics for an agent.

    Returns:
    - Phi score (integration)
    - Connectivity matrix
    - Causal power distribution
    - Interaction history
    """
    plugin = get_consciousness_plugin()

    # Collect all agents that the target agent interacts with (including self)
    # so the IIT phi calculation measures real integration across connected agents.
    iit_calculator = plugin.iit_calculator
    related_agents: set[str] = {agent_id}
    for from_a, to_a in iit_calculator.interaction_matrix:
        if from_a == agent_id or to_a == agent_id:
            related_agents.add(from_a)
            related_agents.add(to_a)
    phi = plugin.calculate_iit_phi(list(related_agents))

    # Build adjacency dict from interaction matrix
    all_agents: set[str] = set()
    for from_a, to_a in iit_calculator.interaction_matrix:
        all_agents.add(from_a)
        all_agents.add(to_a)
    connectivity: dict[str, dict[str, float]] = {a: {} for a in all_agents}
    for (from_a, to_a), strength in iit_calculator.interaction_matrix.items():
        if from_a in connectivity and to_a in connectivity:
            connectivity[from_a][to_a] = strength

    return {
        "agent_id": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "phi_score": phi.phi,
        "connectivity": connectivity,
        "average_phi": iit_calculator.get_average_phi(),
    }


@router.get("/agents/{agent_id}/fep")
async def get_agent_fep_metrics(
    agent_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
    window: int = Query(50, ge=1, le=500, description="Window size for averaging"),
) -> dict[str, Any]:
    """
    Get FEP (Free Energy Principle) metrics for an agent.

    Returns:
    - Prediction accuracy
    - Surprise levels
    - Free energy
    - Belief precision
    - Historical averages
    """
    plugin = get_consciousness_plugin()
    fep_tracker = plugin.fep_tracker

    metrics = fep_tracker.get_metrics(agent_id)
    if metrics is None:
        raise HTTPException(status_code=404, detail=f"No FEP metrics found for agent {agent_id}")

    avg_free_energy = fep_tracker.get_average_free_energy(agent_id, window)

    return {
        "agent_id": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": metrics,
        "average_free_energy": avg_free_energy,
        "window_size": window,
    }


@router.get("/connectivity")
async def get_connectivity_matrix(
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get the agent connectivity matrix.

    Returns a matrix showing interaction frequencies and causal power
    between all agents in the swarm.
    """
    plugin = get_consciousness_plugin()
    iit_calculator = plugin.iit_calculator
    # Build adjacency dict from interaction matrix
    all_agents: set[str] = set()
    for from_a, to_a in iit_calculator.interaction_matrix:
        all_agents.add(from_a)
        all_agents.add(to_a)
    connectivity: dict[str, dict[str, float]] = {a: {} for a in all_agents}
    for (from_a, to_a), strength in iit_calculator.interaction_matrix.items():
        if from_a in connectivity and to_a in connectivity:
            connectivity[from_a][to_a] = strength

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "connectivity": connectivity,
        "agent_count": len(connectivity),
    }


@router.get("/states")
async def get_consciousness_states(
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get the current consciousness state of all agents.

    Returns mapping of agent IDs to their consciousness states:
    - DORMANT: Inactive or low consciousness
    - EMERGING: Developing consciousness
    - COHERENT: Stable, integrated consciousness
    - TRANSCENDENT: Highly integrated, emergent properties
    """
    plugin = get_consciousness_plugin()
    agent_metrics = plugin.agent_metrics

    # Count states
    state_counts = {state.value: 0 for state in ConsciousnessState}
    for metrics in agent_metrics.values():
        state_counts[metrics.state.value] += 1

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "states": {agent_id: metrics.state.value for agent_id, metrics in agent_metrics.items()},
        "counts": state_counts,
        "total_agents": len(agent_metrics),
    }


@router.get("/history")
async def get_consciousness_history(
    authenticated: Annotated[str, Depends(verify_auth)],
    agent_id: str | None = Query(None, description="Filter by specific agent"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
) -> dict[str, Any]:
    """
    Get historical consciousness metrics.

    Returns time-series data for tracking consciousness evolution.
    """
    plugin = get_consciousness_plugin()
    metrics_history = plugin.metrics_history

    # Get metrics history within time window
    cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
    history = []

    for entry in metrics_history:
        entry_time = datetime.fromisoformat(entry.get("timestamp", "1970-01-01T00:00:00Z"))
        if entry_time >= cutoff_time:
            if agent_id is None or agent_id in entry.get("agents", {}):
                history.append(entry)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent_id": agent_id,
        "hours": hours,
        "history": history,
        "count": len(history),
    }


@router.post("/record-interaction")
async def record_interaction(
    interaction: dict[str, Any],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Record an agent interaction for consciousness tracking.

    This endpoint is called by the system when agents interact with each other.
    """
    plugin = get_consciousness_plugin()

    from_agent = interaction.get("from_agent")
    to_agent = interaction.get("to_agent")
    interaction_type = interaction.get("type", "message")

    if not from_agent or not to_agent:
        raise HTTPException(status_code=400, detail="from_agent and to_agent are required")

    # Map interaction type to a numeric strength; default 1.0 for all types
    strength_map = {"message": 1.0, "task": 1.0, "response": 1.0, "error": 0.5}
    strength = strength_map.get(interaction_type, 1.0)

    plugin.record_interaction(from_agent, to_agent, strength)

    return {
        "status": "recorded",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/record-prediction")
async def record_prediction(
    prediction: dict[str, Any],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Record an agent's prediction for FEP tracking.

    This endpoint is called when an agent makes a prediction.
    """
    plugin = get_consciousness_plugin()

    agent_id = prediction.get("agent_id")
    predicted_outcome = prediction.get("predicted_outcome")
    confidence = prediction.get("confidence", 0.5)

    if not agent_id or predicted_outcome is None:
        raise HTTPException(status_code=400, detail="agent_id and predicted_outcome are required")

    plugin.record_prediction(agent_id, predicted_outcome, confidence)

    return {
        "status": "recorded",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/record-outcome")
async def record_outcome(
    outcome: dict[str, Any],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Record an actual outcome for FEP tracking.

    This endpoint is called when the actual outcome of a prediction is known.
    """
    plugin = get_consciousness_plugin()

    agent_id = outcome.get("agent_id")
    actual_outcome = outcome.get("actual_outcome")

    if not agent_id or actual_outcome is None:
        raise HTTPException(status_code=400, detail="agent_id and actual_outcome are required")

    plugin.record_outcome(agent_id, actual_outcome)

    return {
        "status": "recorded",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/metrics/{agent_id}")
async def calculate_consciousness_metrics(
    agent_id: str,
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Calculate comprehensive consciousness metrics for an agent.

    Combines IIT and FEP metrics into a unified consciousness score.
    """
    plugin = get_consciousness_plugin()
    metrics = plugin.calculate_consciousness_metrics(agent_id)

    if metrics is None:
        raise HTTPException(
            status_code=404, detail=f"Could not calculate metrics for agent {agent_id}"
        )

    return {
        "agent_id": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        **metrics,
    }


@router.get("/visualization/network")
async def get_network_visualization(
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Get network visualization data for agent connectivity.

    Returns node-link data suitable for D3.js or similar visualization libraries.
    """
    plugin = get_consciousness_plugin()
    iit_calculator = plugin.iit_calculator

    # Build adjacency dict from interaction matrix
    all_agents: set[str] = set()
    for from_a, to_a in iit_calculator.interaction_matrix:
        all_agents.add(from_a)
        all_agents.add(to_a)
    connectivity: dict[str, dict[str, float]] = {a: {} for a in all_agents}
    for (from_a, to_a), strength in iit_calculator.interaction_matrix.items():
        if from_a in connectivity and to_a in connectivity:
            connectivity[from_a][to_a] = strength

    # Build nodes
    nodes = []
    for agent_id in connectivity:
        phi = iit_calculator.get_average_phi()
        metrics = plugin.agent_metrics.get(agent_id)
        state = metrics.state if metrics else ConsciousnessState.DORMANT
        nodes.append(
            {
                "id": agent_id,
                "phi": phi,
                "state": state.value,
            }
        )

    # Build links
    links = []
    for from_agent, connections in connectivity.items():
        for to_agent, weight in connections.items():
            if weight > 0:
                links.append(
                    {
                        "source": from_agent,
                        "target": to_agent,
                        "weight": weight,
                    }
                )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "nodes": nodes,
        "links": links,
    }


@router.get("/visualization/timeseries")
async def get_timeseries_data(
    agent_id: str,
    metric: str = Query("phi", description="Metric to retrieve: phi, free_energy, surprise"),
    hours: int = Query(24, ge=1, le=168, description="Hours of data"),
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Get time-series data for a specific metric."""
    plugin = get_consciousness_plugin()
    cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

    if metric == "phi":
        data_points = _collect_phi_points(plugin.iit_calculator, cutoff_time)
    elif metric in ("free_energy", "surprise"):
        data_points = _collect_fep_points(plugin.fep_tracker, agent_id, metric, cutoff_time)
    else:
        data_points = []

    return {"agent_id": agent_id, "metric": metric, "hours": hours,
            "data_points": data_points, "count": len(data_points)}


def _collect_phi_points(iit_calculator: Any, cutoff_time: datetime) -> list[dict[str, Any]]:
    data_points: list[dict[str, Any]] = []
    for entry in iit_calculator.connectivity_history:
        if datetime.fromisoformat(entry.timestamp) >= cutoff_time:
            data_points.append({"timestamp": entry.timestamp, "value": entry.phi})
    return data_points


def _collect_fep_points(
    fep_tracker: Any, agent_id: str, metric: str, cutoff_time: datetime
) -> list[dict[str, Any]]:
    data_points: list[dict[str, Any]] = []
    for pred in fep_tracker.prediction_history.get(agent_id, []):
        pred_time = datetime.fromtimestamp(pred["timestamp"], tz=UTC)
        if pred_time >= cutoff_time:
            value = (
                pred.get("prediction", {}).get(metric, 0)
                if isinstance(pred.get("prediction"), dict)
                else 0
            )
            data_points.append({"timestamp": pred_time.isoformat(), "value": value})
    return data_points


# =============================================================================
# Deliberation Explain — M019 S01: Cognitive Observability Surface
# =============================================================================


@router.get("/deliberation/{deliberation_id}")
async def get_deliberation_explanation(
    deliberation_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """
    Get structured explanation of a deliberation decision.

    Returns why/whyNot/rollback_plan for OpenAEON-compatible explainability surface.

    This endpoint provides:
    - why: Top FOR arguments
    - why_not: Top AGAINST arguments
    - rollback_plan: Recommended action if consensus is weak
    - position_distribution: FOR/AGAINST/NEUTRAL counts
    - dissent_summary: Dissenting opinions and their resolution status

    Prime Directive: "Unbounded Autonomy" — agents must be able to explain their
    decisions to maintain accountability while preserving independence.
    """
    from heretek_swarm_core.consensus.deliberation import DeliberationEngine

    engine = DeliberationEngine()
    explanation = engine.get_deliberation_explanation(deliberation_id)

    if explanation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deliberation {deliberation_id} not found. "
            "Deliberations are stored in memory and may have been cleaned up.",
        )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        **explanation,
    }


# =============================================================================
# Thinking Stream — M019 S01: Cognitive Observability Surface
# =============================================================================


@router.get("/thinking-stream/{agent_id}")
async def get_agent_thinking_stream(
    agent_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
    limit: int = Query(50, ge=1, le=500, description="Maximum rounds to return"),
) -> dict[str, Any]:
    """
    Get deliberation thinking stream for a specific agent.

    Returns JSONL-compatible list of DeliberationRound entries for the agent,
    providing a trace of the agent's deliberation reasoning.

    Each entry includes:
    - round_id, topic, participant_agents
    - arguments and counter_arguments submitted
    - consensus_score, outcome, position_changes
    - start_time, end_time, round_duration

    OpenAEON pattern: mirrors aeon.thinking.stream() RPC for replay.
    """
    plugin = get_consciousness_plugin()
    thinking_store = getattr(plugin, "_thinking_stream", None)

    if thinking_store is None:
        # Thinking stream not yet initialized — return empty
        return {
            "agent_id": agent_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "entries": [],
            "count": 0,
        }

    # Filter entries for this agent
    all_entries = thinking_store.get("entries", [])
    agent_entries = [
        {
            "round_id": e.get("round_id", ""),
            "topic": e.get("topic", ""),
            "participant_agents": e.get("participant_agents", []),
            "arguments": e.get("arguments", []),
            "counter_arguments": e.get("counter_arguments", []),
            "consensus_score": e.get("consensus_score", 0.0),
            "outcome": e.get("outcome", ""),
            "start_time": e.get("start_time"),
            "end_time": e.get("end_time"),
        }
        for e in all_entries
        if agent_id in e.get("participant_agents", [])
    ]

    return {
        "agent_id": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "entries": agent_entries[-limit:],
        "count": len(agent_entries),
    }


@router.get("/thinking-stream/all")
async def get_all_thinking_streams(
    authenticated: Annotated[str, Depends(verify_auth)],
    limit: int = Query(100, ge=1, le=1000, description="Maximum total entries"),
) -> dict[str, Any]:
    """
    Get deliberation thinking streams for all agents.

    Returns aggregated thinking stream across the entire swarm.
    Useful for visualizing collective deliberation traces.
    """
    plugin = get_consciousness_plugin()
    thinking_store = getattr(plugin, "_thinking_stream", None)

    if thinking_store is None:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "entries": [],
            "count": 0,
        }

    all_entries = thinking_store.get("entries", [])
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "entries": all_entries[-limit:],
        "count": len(all_entries),
    }
