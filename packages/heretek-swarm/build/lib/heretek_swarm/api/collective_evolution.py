"""
Collective Evolution API - Session 46 Emergent Intelligence

API endpoints for organic evolution mechanisms including:
- Evolution status and metrics
- Capability tracking
- Fitness landscape analysis
- Adaptability monitoring

GET /api/collective/evolution-status
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from heretek_swarm.collective.adaptive_learning import (
    AdaptiveLearningRateController,
)
from heretek_swarm.collective.emergent_detection import (
    EvolutionEngine,
)
from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger("api.collective_evolution")

router = APIRouter(
    prefix="/api/collective",
    tags=["collective"],
    dependencies=[Depends(verify_auth)],
)


# Global instances (will be initialized by lifespan or manually)
_evolution_engine: EvolutionEngine | None = None
_adaptive_learning: AdaptiveLearningRateController | None = None


def set_evolution_engine(engine: EvolutionEngine) -> None:
    """Set the global evolution engine instance."""
    global _evolution_engine
    _evolution_engine = engine


def set_adaptive_learning(controller: AdaptiveLearningRateController) -> None:
    """Set the global adaptive learning controller instance."""
    global _adaptive_learning
    _adaptive_learning = controller


def get_evolution_engine() -> EvolutionEngine:
    """Get the evolution engine, creating if necessary."""
    global _evolution_engine
    if _evolution_engine is None:
        _evolution_engine = EvolutionEngine()
    return _evolution_engine


def get_adaptive_learning() -> AdaptiveLearningRateController:
    """Get the adaptive learning controller, creating if necessary."""
    global _adaptive_learning
    if _adaptive_learning is None:
        _adaptive_learning = AdaptiveLearningRateController()
    return _adaptive_learning


# =============================================================================
# Evolution Status Endpoint
# =============================================================================


@router.get("/evolution-status")
async def get_evolution_status() -> dict[str, Any]:
    """
    Get the current evolution status of the swarm.

    Returns comprehensive evolution metrics including:
    - evolution_rate: Speed of capability development (capabilities/hour)
    - fitness_landscape: Current environment-agent fit (0-1)
    - adaptability_index: How quickly swarm adapts (0-1)
    - current_phase: Current evolution phase
    - capability_diversity: Diversity of capabilities
    - fitness_trend: Direction of fitness change

    Returns:
        Evolution status with all metrics
    """
    try:
        engine = get_evolution_engine()
        adaptive = get_adaptive_learning()

        # Get evolution metrics from engine
        metrics = engine.get_evolution_metrics()

        # Get environment profile
        env_profile = adaptive.get_environment_profile()

        # Get swarm statistics
        swarm_stats = adaptive.get_swarm_statistics()

        # Get capability records
        capabilities = engine.get_capability_records()

        # Get recent evolution events
        recent_capabilities = capabilities[-10:] if capabilities else []

        return {
            "status": "healthy",
            "timestamp": metrics.timestamp.isoformat() if hasattr(metrics, "timestamp") else None,
            "metrics": {
                "evolution_rate": metrics.evolution_rate,
                "fitness_landscape": metrics.fitness_landscape,
                "adaptability_index": metrics.adaptability_index,
                "capability_diversity": metrics.capability_diversity,
                "fitness_trend": metrics.fitness_trend,
                "current_phase": metrics.current_phase.value,
            },
            "capabilities": {
                "total": metrics.total_capabilities,
                "stabilized": metrics.stabilized_capabilities,
                "inherited": metrics.inherited_capabilities,
                "active": metrics.active_capabilities,
            },
            "fitness": {
                "average": metrics.avg_fitness,
                "maximum": metrics.max_fitness,
                "minimum": metrics.min_fitness,
                "variance": metrics.fitness_variance,
            },
            "environment": {
                "stability": env_profile.get("stability", 0.5),
                "complexity": env_profile.get("complexity", 0.5),
                "optimal_learning_rate": env_profile.get("optimal_learning_rate", 0.1),
                "selection_pressure": env_profile.get("selection_pressure", 0.5),
            },
            "swarm": {
                "total_agents": swarm_stats.get("total_agents", 0),
                "avg_learning_rate": swarm_stats.get("avg_learning_rate", 0.0),
                "avg_success_rate": swarm_stats.get("avg_success_rate", 0.0),
                "converged_agents": swarm_stats.get("converged_agents", 0),
                "avg_fitness": swarm_stats.get("avg_fitness", 0.0),
                "behavior_pool_size": swarm_stats.get("behavior_pool_size", 0),
            },
            "recent_capabilities": [
                {
                    "capability_type": cap.capability_type,
                    "capability_name": cap.capability_name,
                    "fitness_contribution": cap.fitness_contribution,
                    "first_observed": cap.first_observed,
                    "is_stabilized": cap.is_stabilized,
                }
                for cap in recent_capabilities
            ],
            "generations": metrics.generations,
        }

    except Exception as e:
        logger.error("evolution_status_error", error=str(e))
        raise HTTPException(500, f"Failed to get evolution status: {e!s}") from e


@router.get("/capabilities")
async def get_capabilities(
    capability_type: str | None = None,
    min_fitness: float | None = None,
    stabilized_only: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Get capability records with optional filtering.

    Args:
        capability_type: Filter by capability type
        min_fitness: Minimum fitness contribution
        stabilized_only: Only return stabilized capabilities
        limit: Maximum records to return

    Returns:
        List of matching capabilities
    """
    try:
        engine = get_evolution_engine()

        capabilities = engine.get_capability_records(
            capability_type=capability_type,
            min_fitness=min_fitness,
            stabilized_only=stabilized_only,
        )

        # Apply limit
        capabilities = capabilities[-limit:]

        return {
            "total": len(capabilities),
            "capabilities": [
                {
                    "capability_id": cap.capability_id,
                    "capability_type": cap.capability_type,
                    "capability_name": cap.capability_name,
                    "description": cap.description,
                    "origin_agent_id": cap.origin_agent_id,
                    "contributing_agents": cap.contributing_agents,
                    "development_time_seconds": cap.development_time_seconds,
                    "evolution_rate": cap.evolution_rate,
                    "fitness_contribution": cap.fitness_contribution,
                    "first_observed": cap.first_observed,
                    "last_reinforced": cap.last_reinforced,
                    "is_stabilized": cap.is_stabilized,
                    "is_inherited": cap.is_inherited,
                    "inheritance_count": cap.inheritance_count,
                }
                for cap in capabilities
            ],
        }

    except Exception as e:
        logger.error("get_capabilities_error", error=str(e))
        raise HTTPException(500, f"Failed to get capabilities: {e!s}") from e


@router.get("/capabilities/{capability_id}")
async def get_capability(capability_id: str) -> dict[str, Any]:
    """
    Get a specific capability by ID.

    Args:
        capability_id: The capability ID to retrieve

    Returns:
        Capability details
    """
    try:
        engine = get_evolution_engine()

        # Search for the capability
        for cap in engine.get_capability_records():
            if cap.capability_id == capability_id:
                return {
                    "capability": {
                        "capability_id": cap.capability_id,
                        "capability_type": cap.capability_type,
                        "capability_name": cap.capability_name,
                        "description": cap.description,
                        "origin_agent_id": cap.origin_agent_id,
                        "contributing_agents": cap.contributing_agents,
                        "development_time_seconds": cap.development_time_seconds,
                        "evolution_rate": cap.evolution_rate,
                        "fitness_contribution": cap.fitness_contribution,
                        "selection_pressure": cap.selection_pressure,
                        "first_observed": cap.first_observed,
                        "last_reinforced": cap.last_reinforced,
                        "stabilization_time": cap.stabilization_time,
                        "is_stabilized": cap.is_stabilized,
                        "is_inherited": cap.is_inherited,
                        "inheritance_count": cap.inheritance_count,
                    }
                }

        raise HTTPException(404, f"Capability not found: {capability_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_capability_error", error=str(e))
        raise HTTPException(500, f"Failed to get capability: {e!s}") from e


@router.get("/agent/{agent_id}/evolution")
async def get_agent_evolution(agent_id: str) -> dict[str, Any]:
    """
    Get evolution data for a specific agent.

    Args:
        agent_id: The agent ID to query

    Returns:
        Agent evolution history and current state
    """
    try:
        engine = get_evolution_engine()
        adaptive = get_adaptive_learning()

        # Get agent capability history
        history = engine.get_agent_capability_history(agent_id)

        # Get agent learning state
        state = adaptive.get_agent_state(agent_id)

        # Get convergence metrics
        convergence = adaptive.get_convergence_metrics(agent_id)

        return {
            "agent_id": agent_id,
            "capability_history": [
                {
                    "timestamp": snap.timestamp,
                    "capability_levels": snap.capability_levels,
                    "fitness_score": snap.fitness_score,
                    "behavior_diversity": snap.behavior_diversity,
                    "behavior_innovation": snap.behavior_innovation,
                    "success_rate": snap.success_rate,
                    "newly_acquired": snap.newly_acquired,
                }
                for snap in history[-20:]  # Last 20 snapshots
            ],
            "learning_state": {
                "current_rate": state.current_rate,
                "initial_rate": state.initial_rate,
                "total_updates": state.total_updates,
                "successful_updates": state.successful_updates,
                "failed_updates": state.failed_updates,
                "success_rate": state.success_rate,
                "fitness_score": state.fitness_score,
                "behavior_pool_size": len(state.behavior_pool),
                "active_behaviors": state.active_behaviors,
                "capability_levels": state.capability_levels,
            },
            "convergence": {
                "is_converged": convergence.is_converged,
                "convergence_score": convergence.convergence_score,
                "iterations_to_convergence": convergence.iterations_to_convergence,
                "final_rate": convergence.final_rate,
                "performance_stability": convergence.performance_stability,
            },
        }

    except Exception as e:
        logger.error("agent_evolution_error", error=str(e))
        raise HTTPException(500, f"Failed to get agent evolution: {e!s}") from e


@router.get("/fitness-landscape")
async def get_fitness_landscape() -> dict[str, Any]:
    """
    Get the current fitness landscape analysis.

    Returns:
        Fitness landscape visualization data
    """
    try:
        engine = get_evolution_engine()
        adaptive = get_adaptive_learning()

        # Get all agent states
        states = adaptive.get_all_agent_states()

        # Build fitness distribution
        fitness_values = [s.fitness_score for s in states.values()]

        # Get environment profile
        env_profile = adaptive.get_environment_profile()

        # Get evolution metrics
        metrics = engine.get_evolution_metrics()

        # Calculate fitness percentiles
        if fitness_values:
            sorted_fitness = sorted(fitness_values)
            p25 = sorted_fitness[len(sorted_fitness) // 4] if sorted_fitness else 0
            p50 = sorted_fitness[len(sorted_fitness) // 2] if sorted_fitness else 0
            p75 = sorted_fitness[3 * len(sorted_fitness) // 4] if sorted_fitness else 0
        else:
            p25 = p50 = p75 = 0

        return {
            "fitness_landscape": metrics.fitness_landscape,
            "fitness_variance": metrics.fitness_variance,
            "fitness_trend": metrics.fitness_trend,
            "distribution": {
                "mean": metrics.avg_fitness,
                "min": metrics.min_fitness,
                "max": metrics.max_fitness,
                "p25": p25,
                "p50": p50,
                "p75": p75,
            },
            "agent_count": len(fitness_values),
            "environment": {
                "stability": env_profile.get("stability", 0.5),
                "complexity": env_profile.get("complexity", 0.5),
                "selection_pressure": env_profile.get("selection_pressure", 0.5),
            },
            "phases": {
                "current": metrics.current_phase.value,
                "description": _get_phase_description(metrics.current_phase),
            },
        }

    except Exception as e:
        logger.error("fitness_landscape_error", error=str(e))
        raise HTTPException(500, f"Failed to get fitness landscape: {e!s}") from e


def _get_phase_description(phase) -> str:
    """Get human-readable description of evolution phase."""
    descriptions = {
        "initialization": "Swarm is just forming, agents are initializing capabilities.",
        "exploration": "Agents are exploring different behaviors and strategies.",
        "selection": "Behaviors are being selected based on fitness.",
        "consolidation": "Successful traits are stabilizing.",
        "emergence": "New capabilities are emerging from interactions.",
        "maturation": "Capabilities are maturing and becoming refined.",
        "equilibrium": "Stable evolutionary state achieved.",
    }
    return descriptions.get(phase.value, "Unknown phase")


@router.get("/adaptability")
async def get_adaptability_metrics() -> dict[str, Any]:
    """
    Get adaptability metrics for the swarm.

    Returns:
        Adaptability analysis
    """
    try:
        engine = get_evolution_engine()
        adaptive = get_adaptive_learning()

        # Get evolution metrics
        metrics = engine.get_evolution_metrics()

        # Get environment profile
        env_profile = adaptive.get_environment_profile()

        # Calculate adaptability components
        rate_component = min(metrics.evolution_rate / 10.0, 1.0) if metrics.evolution_rate else 0
        diversity_component = metrics.capability_diversity
        environment_component = env_profile.get("stability", 0.5)

        return {
            "adaptability_index": metrics.adaptability_index,
            "adaptation_latency": metrics.adaptation_latency,
            "selection_fidelity": metrics.selection_fidelity,
            "components": {
                "evolution_rate_contribution": rate_component,
                "diversity_contribution": diversity_component,
                "environment_stability_contribution": environment_component,
            },
            "environment": {
                "stability": env_profile.get("stability", 0.5),
                "complexity": env_profile.get("complexity", 0.5),
                "optimal_learning_rate": env_profile.get("optimal_learning_rate", 0.1),
            },
            "capabilities": {
                "total": metrics.total_capabilities,
                "active": metrics.active_capabilities,
                "evolution_rate": metrics.evolution_rate,
            },
        }

    except Exception as e:
        logger.error("adaptability_metrics_error", error=str(e))
        raise HTTPException(500, f"Failed to get adaptability metrics: {e!s}") from e


@router.post("/agent/{agent_id}/evolve")
async def evolve_agent_behaviors(
    agent_id: str,
    environment_demands: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Trigger evolution cycle for an agent.

    Args:
        agent_id: Agent to evolve
        environment_demands: Optional environment capability demands

    Returns:
        Evolution result
    """
    try:
        adaptive = get_adaptive_learning()

        result = await adaptive.evolve_behaviors(agent_id, environment_demands)

        return {
            "agent_id": agent_id,
            "evolution_result": {
                "mutated_behaviors": result.mutated_behaviors,
                "selected_behaviors": result.selected_behaviors,
                "crossovers": result.crossovers,
                "eliminated_behaviors": result.eliminated_behaviors,
                "new_capabilities": result.new_capabilities,
                "fitness_improvement": result.fitness_improvement,
            },
        }

    except Exception as e:
        logger.error("evolve_agent_error", error=str(e))
        raise HTTPException(500, f"Failed to evolve agent: {e!s}") from e


@router.post("/record-capability")
async def record_capability(
    agent_id: str,
    capability_type: str,
    capability_name: str,
    fitness_contribution: float = 0.0,
    description: str = "",
    contributing_agents: list[str] | None = None,
) -> dict[str, Any]:
    """
    Record a new capability gained by an agent.

    Args:
        agent_id: ID of agent that gained the capability
        capability_type: Type of capability
        capability_name: Human-readable name
        fitness_contribution: How much this improves fitness
        description: Description of the capability
        contributing_agents: Other agents that contributed

    Returns:
        Created capability record
    """
    try:
        engine = get_evolution_engine()

        record = engine.record_capability_gain(
            agent_id=agent_id,
            capability_type=capability_type,
            capability_name=capability_name,
            fitness_contribution=fitness_contribution,
            description=description,
            contributing_agents=contributing_agents,
        )

        return {
            "status": "recorded",
            "capability": {
                "capability_id": record.capability_id,
                "capability_type": record.capability_type,
                "capability_name": record.capability_name,
                "fitness_contribution": record.fitness_contribution,
                "evolution_rate": record.evolution_rate,
                "first_observed": record.first_observed,
            },
        }

    except Exception as e:
        logger.error("record_capability_error", error=str(e))
        raise HTTPException(500, f"Failed to record capability: {e!s}") from e


@router.post("/detect-evolution")
async def detect_evolution(
    agent_states: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Detect capability emergence across agents.

    Args:
        agent_states: Dictionary mapping agent_id to state

    Returns:
        Detected capabilities
    """
    try:
        engine = get_evolution_engine()

        new_capabilities = engine.detect_evolution(agent_states)

        return {
            "detected_count": len(new_capabilities),
            "capabilities": [
                {
                    "capability_id": cap.capability_id,
                    "capability_type": cap.capability_type,
                    "capability_name": cap.capability_name,
                    "fitness_contribution": cap.fitness_contribution,
                }
                for cap in new_capabilities
            ],
        }

    except Exception as e:
        logger.error("detect_evolution_error", error=str(e))
        raise HTTPException(500, f"Failed to detect evolution: {e!s}") from e
