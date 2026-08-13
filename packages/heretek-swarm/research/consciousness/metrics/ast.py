"""
AST Metrics - Adaptive Systems Theory Implementation.

This module implements metrics for measuring adaptive system properties
including complexity, emergence, self-organization, and resilience
in agent swarms.

Key Concepts (from Adaptive Systems Theory):
- Complexity: Amount of information in the system's organization
- Emergence: Novel properties arising from interactions
- Self-Organization: Spontaneous order from local rules
- Resilience: Ability to recover from perturbations
- Adaptation: Learning and evolving over time

References:
- Holland, J.H. (1995). Hidden Order: How Adaptation Builds Complexity
- Kauffman, S. (1993). The Origins of Order: Self-Organization and Selection

Author: Heretek Swarm Collective
Date: 2026-04-11
Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("ASTMetrics")


class EmergenceLevel(Enum):
    """Levels of emergence in adaptive systems."""

    NONE = "none"  # No emergent properties
    WEAK = "weak"  # Simple emergent properties
    MODERATE = "moderate"  # Moderate emergence
    STRONG = "strong"  # Strong emergence
    CRITICAL = "critical"  # Near-critical transition


@dataclass
class AdaptiveMetrics:
    """
    Comprehensive adaptive system metrics for an agent or swarm.

    Attributes:
        entity_id: Identifier for measured entity (agent or swarm)
        entity_type: "agent" or "swarm"
        complexity: System complexity score (0-1)
        emergence_level: Level of emergent behavior
        emergence_score: Quantitative emergence measure (0-1)
        self_organization: Self-organization coefficient (0-1)
        resilience: Resilience score (0-1)
        adaptation_rate: Rate of adaptation (0-1)
        entropy: System entropy (0-1, higher = more disorder)
        coupling: Inter-component coupling (0-1)
        timestamp: Measurement timestamp
    """

    entity_id: str
    entity_type: str = "agent"
    complexity: float = 0.0
    emergence_level: EmergenceLevel = EmergenceLevel.NONE
    emergence_score: float = 0.0
    self_organization: float = 0.0
    resilience: float = 0.0
    adaptation_rate: float = 0.0
    entropy: float = 0.5
    coupling: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "complexity": self.complexity,
            "emergence_level": self.emergence_level.value,
            "emergence_score": self.emergence_score,
            "self_organization": self.self_organization,
            "resilience": self.resilience,
            "adaptation_rate": self.adaptation_rate,
            "entropy": self.entropy,
            "coupling": self.coupling,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdaptiveMetrics":
        """Create from dictionary."""
        emergence_level = data.get("emergence_level", "none")
        if isinstance(emergence_level, str):
            emergence_level = EmergenceLevel(emergence_level)
        return cls(
            entity_id=data["entity_id"],
            entity_type=data.get("entity_type", "agent"),
            complexity=data.get("complexity", 0.0),
            emergence_level=emergence_level,
            emergence_score=data.get("emergence_score", 0.0),
            self_organization=data.get("self_organization", 0.0),
            resilience=data.get("resilience", 0.0),
            adaptation_rate=data.get("adaptation_rate", 0.0),
            entropy=data.get("entropy", 0.5),
            coupling=data.get("coupling", 0.0),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
        )


def _classify_emergence(score: float) -> EmergenceLevel:
    """Classify emergence level based on score."""
    if score < 0.1:
        return EmergenceLevel.NONE
    if score < 0.3:
        return EmergenceLevel.WEAK
    if score < 0.5:
        return EmergenceLevel.MODERATE
    if score < 0.7:
        return EmergenceLevel.STRONG
    return EmergenceLevel.CRITICAL


def measure_complexity(
    state_components: list[str],
    connections: list[tuple[str, str]],
) -> float:
    """
    Measure system complexity based on components and connections.

    Uses a simplified measure based on:
    - Number of unique components
    - Connection density
    - Information content

    Args:
        state_components: List of component identifiers
        connections: List of (source, target) connection tuples

    Returns:
        Complexity score (0-1)
    """
    n = len(state_components)
    if n == 0:
        return 0.0
    if n == 1:
        return 0.1

    # Maximum possible connections for n nodes
    max_connections = n * (n - 1) / 2

    # Connection density
    density = len(connections) / max_connections if max_connections > 0 else 0.0

    # Component diversity (simplified entropy)
    diversity = min(1.0, n / 23.0)  # Normalize to typical swarm size

    # Complexity is combination of density and diversity
    complexity = (density * 0.6) + (diversity * 0.4)

    return min(1.0, complexity)


def measure_emergence(
    micro_states: list[dict[str, Any]],
    macro_properties: list[str],
) -> tuple[float, EmergenceLevel]:
    """
    Measure emergence in a system.

    Emergence is quantified by how well macro properties
    can be predicted from micro states alone.

    Args:
        micro_states: List of individual agent states
        macro_properties: Properties observed at system level

    Returns:
        Tuple of (emergence_score, emergence_level)
    """
    if not micro_states or not macro_properties:
        return 0.0, EmergenceLevel.NONE

    # Simplified emergence based on:
    # 1. Number of agents with unique states
    unique_states = len({str(s) for s in micro_states})
    state_variety = unique_states / len(micro_states) if micro_states else 0.0

    # 2. Difference between micro and macro descriptions
    micro_info = len(micro_states) / 23.0  # Normalize
    macro_info = len(macro_properties) / 10.0  # Normalize

    # 3. Emergence score: high when macro ≠ simple sum of micro
    emergence = state_variety * (1.0 - abs(micro_info - macro_info))

    emergence_score = min(1.0, emergence * 2.0)
    emergence_level = _classify_emergence(emergence_score)

    return emergence_score, emergence_level


def measure_self_organization(
    local_rules: int,
    global_patterns: int,
    interaction_strength: float,
) -> float:
    """
    Measure self-organization coefficient.

    Self-organization occurs when local interactions produce
    global patterns without external direction.

    Args:
        local_rules: Number of local interaction rules
        global_patterns: Number of observed global patterns
        interaction_strength: Average interaction strength (0-1)

    Returns:
        Self-organization score (0-1)
    """
    # Self-org increases with local rules and global patterns
    rule_contribution = min(1.0, local_rules / 10.0) * 0.3
    pattern_contribution = min(1.0, global_patterns / 5.0) * 0.4
    interaction_contribution = interaction_strength * 0.3

    self_org = rule_contribution + pattern_contribution + interaction_contribution

    return min(1.0, self_org)


def measure_resilience(
    successful_recoveries: int,
    total_perturbations: int,
    recovery_time: float,
    max_recovery_time: float = 60.0,
) -> float:
    """
    Measure system resilience.

    Resilience is the ability to recover from perturbations.

    Args:
        successful_recoveries: Number of successful recovery events
        total_perturbations: Total perturbation events
        recovery_time: Average time to recover (seconds)
        max_recovery_time: Maximum acceptable recovery time (seconds)

    Returns:
        Resilience score (0-1)
    """
    if total_perturbations == 0:
        return 0.5  # Neutral if no perturbations observed

    # Recovery rate
    recovery_rate = successful_recoveries / total_perturbations

    # Speed of recovery (normalized)
    speed = 1.0 - (recovery_time / max_recovery_time) if recovery_time > 0 else 1.0
    speed = max(0.0, min(1.0, speed))

    # Resilience combines rate and speed
    resilience = (recovery_rate * 0.7) + (speed * 0.3)

    return min(1.0, resilience)


def measure_adaptive_metrics(entity_state: dict[str, Any]) -> AdaptiveMetrics:
    """
    Measure comprehensive adaptive system metrics.

    Args:
        entity_state: Entity state containing:
            For agents:
            - internal_components: List of component identifiers
            - internal_connections: Number of internal connections
            - behavioral_variety: Number of unique behaviors
            - recovery_events: Successful recovery count
            - perturbation_count: Total perturbations
            - avg_recovery_time: Average recovery time (seconds)

            For swarms:
            - agent_count: Number of agents
            - inter_agent_connections: Connections between agents
            - observed_patterns: Global patterns observed
            - emergence_events: Detected emergence events
            - consensus_achievements: Successful consensus events
            - local_rules: Number of local rules
            - interaction_strength: Average interaction strength

    Returns:
        AdaptiveMetrics for the entity
    """
    try:
        entity_id = entity_state.get("entity_id", "unknown")
        entity_type = entity_state.get("entity_type", "agent")

        if entity_type == "agent":
            # Agent-level metrics
            components = entity_state.get("internal_components", [])
            connections = entity_state.get("internal_connections", 0)
            behavioral_variety = entity_state.get("behavioral_variety", 0)

            complexity = measure_complexity(
                components,
                [
                    (f"c{i}", f"c{j}")
                    for i in range(len(components))
                    for j in range(i + 1, min(len(components), connections))
                ],
            )

            emergence_score, emergence_level = measure_emergence(
                [{"behavior": b} for b in range(behavioral_variety)],
                ["adaptation", "learning"] if behavioral_variety > 1 else [],
            )

            self_org = min(1.0, (len(components) / 10.0) * 0.5 + (connections / 20.0) * 0.5)

            resilience = measure_resilience(
                entity_state.get("recovery_events", 0),
                entity_state.get("perturbation_count", 0),
                entity_state.get("avg_recovery_time", 0.0),
            )

            adaptation_rate = min(1.0, behavioral_variety / 20.0)

            entropy = 1.0 - complexity  # Inverse of complexity

        else:
            # Swarm-level metrics
            agent_count = entity_state.get("agent_count", 0)
            connections = entity_state.get("inter_agent_connections", 0)
            patterns = entity_state.get("observed_patterns", 0)

            components = [f"agent_{i}" for i in range(min(agent_count, 100))]
            complexity = measure_complexity(
                components,
                [
                    (f"agent_{i}", f"agent_{j}")
                    for i in range(min(agent_count, 50))
                    for j in range(i + 1, min(agent_count, 50))
                    if (i + j) % 3 == 0
                ],
            )

            emergence_score, emergence_level = measure_emergence(
                [{"agent": i} for i in range(agent_count)],
                ["swarm_behavior", "collective_intelligence"] if patterns > 0 else [],
            )

            self_org = measure_self_organization(
                entity_state.get("local_rules", 0),
                patterns,
                entity_state.get("interaction_strength", 0.0),
            )

            resilience = measure_resilience(
                entity_state.get("consensus_achievements", 0),
                entity_state.get("failed_consensus", 0),
                entity_state.get("avg_consensus_time", 0.0),
            )

            adaptation_rate = min(1.0, patterns / 10.0)
            entropy = 0.5 - (complexity * 0.2)  # Lower entropy in organized swarms

        coupling = (
            min(1.0, connections / 100.0)
            if entity_type == "agent"
            else min(1.0, entity_state.get("inter_agent_connections", 0) / (agent_count * 10))
        )

        return AdaptiveMetrics(
            entity_id=entity_id,
            entity_type=entity_type,
            complexity=complexity,
            emergence_level=emergence_level,
            emergence_score=emergence_score,
            self_organization=self_org,
            resilience=resilience,
            adaptation_rate=adaptation_rate,
            entropy=entropy,
            coupling=coupling,
        )

    except Exception as e:
        logger.warning("adaptive_metrics_measurement_failed", error=str(e))
        return AdaptiveMetrics(entity_id="unknown")


# Registry for tracking entity metrics
_entity_metrics_registry: dict[str, AdaptiveMetrics] = {}


def update_entity_metrics(entity_id: str, metrics: AdaptiveMetrics) -> None:
    """Update metrics for an entity."""
    _entity_metrics_registry[entity_id] = metrics


def get_entity_metrics(entity_id: str) -> AdaptiveMetrics | None:
    """Get metrics for an entity."""
    return _entity_metrics_registry.get(entity_id)


def get_all_adaptive_metrics() -> dict[str, AdaptiveMetrics]:
    """Get all tracked entity metrics."""
    return _entity_metrics_registry.copy()
