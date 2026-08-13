"""
AST Self-Modeling - Attention Schema Theory Implementation.

This module implements the Attention Schema Theory (AST) for self-modeling
in agent swarms. AST provides a mechanistic account of how agents construct
internal models of their own attention processes.

Key Concepts:
- Attention Schema: Internal model of attention state
- Complexity Metrics: Measures of system complexity
- Emergence Scoring: Quantification of emergent behaviors
- Self-Organization: Spontaneous order from local interactions
- Resilience Scoring: Ability to recover from perturbations

References:
- Graziano, M.S.A. (2013). Consciousness and the Social Brain
- Graziano, M.S.A. & Kastner, S. (2011). Human consciousness and its defects

Author: Heretek Swarm Collective
Date: 2026-04-15
Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("ASTSelfModel")


class EmergenceLevel(Enum):
    """Levels of emergence in adaptive systems."""

    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    CRITICAL = "critical"


class SelfOrganizationLevel(Enum):
    """Levels of self-organization."""

    DISORGANIZED = "disorganized"
    FORMING = "forming"
    ORGANIZED = "organized"
    HIGHLY_ORGANIZED = "highly_organized"


class ResilienceLevel(Enum):
    """Levels of resilience."""

    FRAGILE = "fragile"
    ROBUST = "robust"
    RESILIENT = "resilient"
    ADAPTIVE = "adaptive"


@dataclass
class ComplexityMetrics:
    """
    Complexity metrics for AST self-modeling.

    Attributes:
        entity_id: Identifier for the measured entity
        component_count: Number of internal components
        connection_density: Density of inter-component connections
        hierarchical_depth: Depth of hierarchical organization
        information_content: Amount of information in system
        complexity_score: Overall complexity score (0-1)
        timestamp: Measurement timestamp
    """

    entity_id: str
    component_count: int = 0
    connection_density: float = 0.0
    hierarchical_depth: int = 0
    information_content: float = 0.0
    complexity_score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "component_count": self.component_count,
            "connection_density": self.connection_density,
            "hierarchical_depth": self.hierarchical_depth,
            "information_content": self.information_content,
            "complexity_score": self.complexity_score,
            "timestamp": self.timestamp,
        }


@dataclass
class EmergenceScore:
    """
    Emergence scoring for detecting emergent behaviors.

    Attributes:
        entity_id: Identifier for the measured entity
        micro_diversity: Diversity at micro (agent) level
        macro_diversity: Diversity at macro (system) level
        emergence_ratio: Ratio of macro to micro diversity
        novelty_score: How novel are the emergent properties
        emergence_score: Overall emergence score (0-1)
        emergence_level: Classification of emergence level
        timestamp: Measurement timestamp
    """

    entity_id: str
    micro_diversity: float = 0.0
    macro_diversity: float = 0.0
    emergence_ratio: float = 0.0
    novelty_score: float = 0.0
    emergence_score: float = 0.0
    emergence_level: EmergenceLevel = EmergenceLevel.NONE
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "micro_diversity": self.micro_diversity,
            "macro_diversity": self.macro_diversity,
            "emergence_ratio": self.emergence_ratio,
            "novelty_score": self.novelty_score,
            "emergence_score": self.emergence_score,
            "emergence_level": self.emergence_level.value,
            "timestamp": self.timestamp,
        }


@dataclass
class SelfOrganizationMetrics:
    """
    Self-organization tracking metrics.

    Attributes:
        entity_id: Identifier for the measured entity
        local_rule_count: Number of local interaction rules
        global_pattern_count: Number of observed global patterns
        interaction_strength: Average interaction strength (0-1)
        order_parameter: Order parameter measuring organization
        self_organization_score: Overall self-organization score (0-1)
        organization_level: Classification of organization level
        timestamp: Measurement timestamp
    """

    entity_id: str
    local_rule_count: int = 0
    global_pattern_count: int = 0
    interaction_strength: float = 0.0
    order_parameter: float = 0.0
    self_organization_score: float = 0.0
    organization_level: SelfOrganizationLevel = SelfOrganizationLevel.DISORGANIZED
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "local_rule_count": self.local_rule_count,
            "global_pattern_count": self.global_pattern_count,
            "interaction_strength": self.interaction_strength,
            "order_parameter": self.order_parameter,
            "self_organization_score": self.self_organization_score,
            "organization_level": self.organization_level.value,
            "timestamp": self.timestamp,
        }


@dataclass
class ResilienceScore:
    """
    Resilience scoring for system recovery ability.

    Attributes:
        entity_id: Identifier for the measured entity
        successful_recoveries: Number of successful recovery events
        total_perturbations: Total perturbation events
        avg_recovery_time: Average recovery time (seconds)
        recovery_rate: Rate of successful recovery
        recovery_speed: Speed of recovery (normalized)
        resilience_score: Overall resilience score (0-1)
        resilience_level: Classification of resilience level
        timestamp: Measurement timestamp
    """

    entity_id: str
    successful_recoveries: int = 0
    total_perturbations: int = 0
    avg_recovery_time: float = 0.0
    recovery_rate: float = 0.0
    recovery_speed: float = 0.0
    resilience_score: float = 0.0
    resilience_level: ResilienceLevel = ResilienceLevel.FRAGILE
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "successful_recoveries": self.successful_recoveries,
            "total_perturbations": self.total_perturbations,
            "avg_recovery_time": self.avg_recovery_time,
            "recovery_rate": self.recovery_rate,
            "recovery_speed": self.recovery_speed,
            "resilience_score": self.resilience_score,
            "resilience_level": self.resilience_level.value,
            "timestamp": self.timestamp,
        }


@dataclass
class ASTSelfModel:
    """
    Complete AST self-model for an agent or swarm.

    Attributes:
        entity_id: Unique identifier
        entity_type: "agent" or "swarm"
        attention_state: Current attention state
        complexity: Complexity metrics
        emergence: Emergence scoring
        self_organization: Self-organization metrics
        resilience: Resilience scoring
        awareness_level: Self-awareness level (0-1)
        timestamp: Last update timestamp
    """

    entity_id: str
    entity_type: str = "agent"
    attention_state: dict[str, float] = field(default_factory=dict)
    complexity: ComplexityMetrics | None = None
    emergence: EmergenceScore | None = None
    self_organization: SelfOrganizationMetrics | None = None
    resilience: ResilienceScore | None = None
    awareness_level: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "attention_state": self.attention_state,
            "complexity": self.complexity.to_dict() if self.complexity else None,
            "emergence": self.emergence.to_dict() if self.emergence else None,
            "self_organization": self.self_organization.to_dict()
            if self.self_organization
            else None,
            "resilience": self.resilience.to_dict() if self.resilience else None,
            "awareness_level": self.awareness_level,
            "timestamp": self.timestamp,
        }


def calculate_complexity_metrics(
    entity_id: str,
    state_components: list[str],
    connections: list[tuple[str, str]],
    hierarchical_depth: int = 1,
) -> ComplexityMetrics:
    """
    Calculate complexity metrics for an entity.

    Args:
        entity_id: Entity identifier
        state_components: List of component identifiers
        connections: List of (source, target) connection tuples
        hierarchical_depth: Depth of hierarchical structure

    Returns:
        ComplexityMetrics for the entity
    """
    n = len(state_components)
    if n == 0:
        return ComplexityMetrics(entity_id=entity_id)

    # Maximum possible connections
    max_connections = n * (n - 1) / 2
    connection_density = len(connections) / max_connections if max_connections > 0 else 0.0

    # Component diversity normalized to typical swarm size
    component_diversity = min(1.0, n / 23.0)

    # Information content based on connections and diversity
    info_content = connection_density * component_diversity

    # Hierarchical contribution
    hierarchy_factor = min(1.0, hierarchical_depth / 5.0) * 0.2

    # Overall complexity
    complexity_score = connection_density * 0.4 + component_diversity * 0.4 + hierarchy_factor
    complexity_score = min(1.0, complexity_score)

    return ComplexityMetrics(
        entity_id=entity_id,
        component_count=n,
        connection_density=connection_density,
        hierarchical_depth=hierarchical_depth,
        information_content=info_content,
        complexity_score=complexity_score,
    )


def calculate_emergence_score(
    entity_id: str,
    micro_states: list[dict[str, Any]],
    macro_properties: list[str],
    previous_emergence: EmergenceScore | None = None,
) -> EmergenceScore:
    """
    Calculate emergence score for detecting emergent behaviors.

    Args:
        entity_id: Entity identifier
        micro_states: List of individual agent states
        macro_properties: Properties observed at system level
        previous_emergence: Previous emergence score for novelty calculation

    Returns:
        EmergenceScore for the entity
    """
    if not micro_states:
        return EmergenceScore(entity_id=entity_id)

    # Micro diversity: variety at agent level
    unique_states = len({str(s) for s in micro_states})
    micro_diversity = unique_states / len(micro_states) if micro_states else 0.0

    # Macro diversity: diversity of system-level properties
    macro_diversity = len(macro_properties) / 10.0 if macro_properties else 0.0

    # Emergence ratio: macro to micro diversity
    emergence_ratio = macro_diversity / (micro_diversity + 0.01)

    # Novelty: how different is this from previous emergence
    novelty_score = 0.0
    if previous_emergence:
        novelty_score = (
            abs(
                micro_diversity
                - previous_emergence.micro_diversity
                + macro_diversity
                - previous_emergence.macro_diversity
            )
            / 2.0
        )

    # Overall emergence score
    emergence_score = micro_diversity * (1.0 + emergence_ratio) * (1.0 + novelty_score)
    emergence_score = min(1.0, emergence_score / 3.0)

    # Classify emergence level
    emergence_level = EmergenceLevel.NONE
    if emergence_score >= 0.7:
        emergence_level = EmergenceLevel.CRITICAL
    elif emergence_score >= 0.5:
        emergence_level = EmergenceLevel.STRONG
    elif emergence_score >= 0.3:
        emergence_level = EmergenceLevel.MODERATE
    elif emergence_score >= 0.1:
        emergence_level = EmergenceLevel.WEAK

    return EmergenceScore(
        entity_id=entity_id,
        micro_diversity=micro_diversity,
        macro_diversity=macro_diversity,
        emergence_ratio=emergence_ratio,
        novelty_score=novelty_score,
        emergence_score=emergence_score,
        emergence_level=emergence_level,
    )


def calculate_self_organization(
    entity_id: str,
    local_rules: int,
    global_patterns: int,
    interaction_strength: float,
) -> SelfOrganizationMetrics:
    """
    Calculate self-organization metrics.

    Args:
        entity_id: Entity identifier
        local_rules: Number of local interaction rules
        global_patterns: Number of observed global patterns
        interaction_strength: Average interaction strength (0-1)

    Returns:
        SelfOrganizationMetrics for the entity
    """
    # Rule contribution to self-organization
    rule_contribution = min(1.0, local_rules / 10.0) * 0.3

    # Pattern contribution
    pattern_contribution = min(1.0, global_patterns / 5.0) * 0.4

    # Interaction strength contribution
    interaction_contribution = interaction_strength * 0.3

    # Order parameter (simplified)
    order_parameter = (rule_contribution + pattern_contribution) * interaction_strength

    # Overall self-organization score
    self_org_score = rule_contribution + pattern_contribution + interaction_contribution
    self_org_score = min(1.0, self_org_score)

    # Classify organization level
    org_level = SelfOrganizationLevel.DISORGANIZED
    if self_org_score >= 0.75:
        org_level = SelfOrganizationLevel.HIGHLY_ORGANIZED
    elif self_org_score >= 0.5:
        org_level = SelfOrganizationLevel.ORGANIZED
    elif self_org_score >= 0.25:
        org_level = SelfOrganizationLevel.FORMING

    return SelfOrganizationMetrics(
        entity_id=entity_id,
        local_rule_count=local_rules,
        global_pattern_count=global_patterns,
        interaction_strength=interaction_strength,
        order_parameter=order_parameter,
        self_organization_score=self_org_score,
        organization_level=org_level,
    )


def calculate_resilience_score(
    entity_id: str,
    successful_recoveries: int,
    total_perturbations: int,
    recovery_time: float,
    max_recovery_time: float = 60.0,
) -> ResilienceScore:
    """
    Calculate resilience score for system recovery ability.

    Args:
        entity_id: Entity identifier
        successful_recoveries: Number of successful recovery events
        total_perturbations: Total perturbation events
        recovery_time: Average time to recover (seconds)
        max_recovery_time: Maximum acceptable recovery time (seconds)

    Returns:
        ResilienceScore for the entity
    """
    if total_perturbations == 0:
        return ResilienceScore(entity_id=entity_id)

    # Recovery rate
    recovery_rate = successful_recoveries / total_perturbations

    # Speed of recovery (normalized)
    recovery_speed = 1.0 - (recovery_time / max_recovery_time) if recovery_time > 0 else 1.0
    recovery_speed = max(0.0, min(1.0, recovery_speed))

    # Overall resilience
    resilience_score = (recovery_rate * 0.7) + (recovery_speed * 0.3)
    resilience_score = min(1.0, resilience_score)

    # Classify resilience level
    res_level = ResilienceLevel.FRAGILE
    if resilience_score >= 0.75:
        res_level = ResilienceLevel.ADAPTIVE
    elif resilience_score >= 0.5:
        res_level = ResilienceLevel.RESILIENT
    elif resilience_score >= 0.25:
        res_level = ResilienceLevel.ROBUST

    return ResilienceScore(
        entity_id=entity_id,
        successful_recoveries=successful_recoveries,
        total_perturbations=total_perturbations,
        avg_recovery_time=recovery_time,
        recovery_rate=recovery_rate,
        recovery_speed=recovery_speed,
        resilience_score=resilience_score,
        resilience_level=res_level,
    )


def create_ast_self_model(
    entity_id: str,
    entity_type: str,
    agent_state: dict[str, Any],
) -> ASTSelfModel:
    """
    Create a complete AST self-model for an entity.

    Args:
        entity_id: Unique entity identifier
        entity_type: "agent" or "swarm"
        agent_state: Entity state containing metrics data

    Returns:
        Complete ASTSelfModel for the entity
    """
    # Extract attention state
    attention_state = agent_state.get(
        "attention_state",
        {
            "focus": 0.5,
            "vigilance": 0.5,
            "access": 0.5,
        },
    )

    if entity_type == "agent":
        # Agent-level metrics
        components = agent_state.get("internal_components", [])
        connections = agent_state.get("internal_connections", 0)
        complexity = calculate_complexity_metrics(
            entity_id,
            components,
            [
                (f"c{i}", f"c{j}")
                for i in range(len(components))
                for j in range(i + 1, min(len(components), connections))
            ],
        )

        emergence = calculate_emergence_score(
            entity_id,
            [{"behavior": b} for b in range(agent_state.get("behavioral_variety", 0))],
            ["adaptation", "learning"],
        )

        self_org = calculate_self_organization(
            entity_id,
            len(components),
            agent_state.get("observed_patterns", 0),
            agent_state.get("interaction_strength", 0.0),
        )

        resilience = calculate_resilience_score(
            entity_id,
            agent_state.get("recovery_events", 0),
            agent_state.get("perturbation_count", 0),
            agent_state.get("avg_recovery_time", 0.0),
        )

    else:
        # Swarm-level metrics
        agent_count = agent_state.get("agent_count", 0)
        components = [f"agent_{i}" for i in range(min(agent_count, 100))]
        connections = [
            (f"agent_{i}", f"agent_{j}")
            for i in range(min(agent_count, 50))
            for j in range(i + 1, min(agent_count, 50))
        ]

        complexity = calculate_complexity_metrics(
            entity_id,
            components,
            connections,
            hierarchical_depth=agent_state.get("hierarchy_depth", 1),
        )

        emergence = calculate_emergence_score(
            entity_id,
            [{"agent": i} for i in range(agent_count)],
            ["swarm_behavior", "collective_intelligence"]
            if agent_state.get("observed_patterns", 0) > 0
            else [],
        )

        self_org = calculate_self_organization(
            entity_id,
            agent_state.get("local_rules", 0),
            agent_state.get("observed_patterns", 0),
            agent_state.get("interaction_strength", 0.0),
        )

        resilience = calculate_resilience_score(
            entity_id,
            agent_state.get("consensus_achievements", 0),
            agent_state.get("failed_consensus", 0) + agent_state.get("consensus_achievements", 0),
            agent_state.get("avg_consensus_time", 0.0),
        )

    # Calculate awareness level from all metrics
    awareness_level = (
        complexity.complexity_score * 0.25
        + emergence.emergence_score * 0.25
        + self_org.self_organization_score * 0.25
        + resilience.resilience_score * 0.25
    )

    return ASTSelfModel(
        entity_id=entity_id,
        entity_type=entity_type,
        attention_state=attention_state,
        complexity=complexity,
        emergence=emergence,
        self_organization=self_org,
        resilience=resilience,
        awareness_level=awareness_level,
    )


# Registry for tracking entity self-models
_entity_self_models: dict[str, ASTSelfModel] = {}
_previous_emergence: dict[str, EmergenceScore] = {}


def update_self_model(entity_id: str, self_model: ASTSelfModel) -> None:
    """Update the self-model for an entity."""
    # Store previous emergence for novelty calculation
    if _entity_self_models.get(entity_id):
        _previous_emergence[entity_id] = _entity_self_models[entity_id].emergence
    _entity_self_models[entity_id] = self_model


def get_self_model(entity_id: str) -> ASTSelfModel | None:
    """Get the self-model for an entity."""
    return _entity_self_models.get(entity_id)


def get_all_self_models() -> dict[str, ASTSelfModel]:
    """Get all tracked entity self-models."""
    return _entity_self_models.copy()


class ASTSelfModelTracker:
    """
    Tracker for AST self-modeling with history and analysis.

    Provides methods for tracking, updating, and analyzing
    self-models over time.
    """

    def __init__(self):
        self._models: dict[str, list[ASTSelfModel]] = {}
        self._history_limit = 100

    def track(
        self,
        entity_id: str,
        entity_type: str,
        agent_state: dict[str, Any],
    ) -> ASTSelfModel:
        """
        Track a new self-model for an entity.

        Args:
            entity_id: Entity identifier
            entity_type: "agent" or "swarm"
            agent_state: Current entity state

        Returns:
            Updated ASTSelfModel
        """
        self_model = create_ast_self_model(entity_id, entity_type, agent_state)

        # Store in history
        if entity_id not in self._models:
            self._models[entity_id] = []
        self._models[entity_id].append(self_model)

        # Limit history size
        if len(self._models[entity_id]) > self._history_limit:
            self._models[entity_id] = self._models[entity_id][-self._history_limit :]

        # Update global registry
        update_self_model(entity_id, self_model)

        return self_model

    def get_history(self, entity_id: str) -> list[ASTSelfModel]:
        """Get self-model history for an entity."""
        return self._models.get(entity_id, [])

    def get_trend(
        self,
        entity_id: str,
        metric: str,
    ) -> list[float]:
        """
        Get trend for a specific metric.

        Args:
            entity_id: Entity identifier
            metric: Metric name (complexity, emergence, self_organization, resilience, awareness)

        Returns:
            List of metric values over time
        """
        history = self._models.get(entity_id, [])
        trend = []

        for model in history:
            if metric == "complexity":
                trend.append(model.complexity.complexity_score if model.complexity else 0.0)
            elif metric == "emergence":
                trend.append(model.emergence.emergence_score if model.emergence else 0.0)
            elif metric == "self_organization":
                trend.append(
                    model.self_organization.self_organization_score
                    if model.self_organization
                    else 0.0
                )
            elif metric == "resilience":
                trend.append(model.resilience.resilience_score if model.resilience else 0.0)
            elif metric == "awareness":
                trend.append(model.awareness_level)

        return trend

    def get_statistics(self, entity_id: str) -> dict[str, Any]:
        """Get statistics for an entity's self-model history."""
        history = self._models.get(entity_id, [])
        if not history:
            return {}

        metrics = {
            "complexity": [],
            "emergence": [],
            "self_organization": [],
            "resilience": [],
            "awareness": [],
        }

        for model in history:
            if model.complexity:
                metrics["complexity"].append(model.complexity.complexity_score)
            if model.emergence:
                metrics["emergence"].append(model.emergence.emergence_score)
            if model.self_organization:
                metrics["self_organization"].append(model.self_organization.self_organization_score)
            if model.resilience:
                metrics["resilience"].append(model.resilience.resilience_score)
            metrics["awareness"].append(model.awareness_level)

        stats = {}
        for name, values in metrics.items():
            if values:
                stats[name] = {
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "current": values[-1],
                }

        return stats
