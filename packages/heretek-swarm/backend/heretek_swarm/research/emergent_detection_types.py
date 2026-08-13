"""Emergent detection type definitions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from heretek_swarm.collective.learning import (
    ExtractedPattern,
    PatternMetadata,
    PatternSource,
    PatternType,
)

logger = structlog.get_logger(__name__)


class EmergentPatternClass(StrEnum):
    """Classification of emergent patterns."""

    COORDINATION = "coordination"
    OPTIMIZATION = "optimization"
    INNOVATION = "innovation"
    SELF_ORGANIZATION = "self_organization"
    ADAPTATION = "adaptation"
    PHASE_TRANSITION = "phase_transition"
    CASCADE = "cascade"
    RESONANCE = "resonance"


class EmergenceLevel(StrEnum):
    """Levels of emergence strength."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    CRITICAL = "critical"


class PatternProvenance(StrEnum):
    """
    Provenance classification for emergent patterns.

    Patterns are classified PROVEN or UNPROVEN based on novelty
    and validation rate weighting.
    """

    PROVEN = "proven"
    UNPROVEN = "unproven"


class EvolutionPhase(StrEnum):
    """Phases of evolutionary development."""

    INITIALIZATION = "initialization"
    EXPLORATION = "exploration"
    SELECTION = "selection"
    CONSOLIDATION = "consolidation"
    EMERGENCE = "emergence"
    MATURATION = "maturation"
    EQUILIBRIUM = "equilibrium"


@dataclass
class CapabilityRecord:
    """Record of a capability gained by an agent or the swarm."""

    capability_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    capability_type: str = ""
    capability_name: str = ""
    description: str = ""

    origin_agent_id: str | None = None
    contributing_agents: list[str] = field(default_factory=list)

    development_time_seconds: float = 0.0
    evolution_rate: float = 0.0

    fitness_contribution: float = 0.0
    selection_pressure: float = 0.0

    first_observed: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_reinforced: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    stabilization_time: str | None = None
    is_stabilized: bool = False
    is_inherited: bool = False
    inheritance_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "capability_type": self.capability_type,
            "capability_name": self.capability_name,
            "description": self.description,
            "origin_agent_id": self.origin_agent_id,
            "contributing_agents": self.contributing_agents,
            "development_time_seconds": self.development_time_seconds,
            "evolution_rate": self.evolution_rate,
            "fitness_contribution": self.fitness_contribution,
            "selection_pressure": self.selection_pressure,
            "first_observed": self.first_observed,
            "last_reinforced": self.last_reinforced,
            "stabilization_time": self.stabilization_time,
            "is_stabilized": self.is_stabilized,
            "is_inherited": self.is_inherited,
            "inheritance_count": self.inheritance_count,
            "metadata": self.metadata,
        }


@dataclass
class EvolutionMetrics:
    """Metrics tracking the evolution of the swarm."""

    evolution_rate: float = 0.0
    capabilities_per_generation: float = 0.0
    capability_diversity: float = 0.0

    fitness_landscape: float = 0.0
    fitness_variance: float = 0.0
    fitness_trend: float = 0.0

    adaptability_index: float = 0.0
    adaptation_latency: float = 0.0
    selection_fidelity: float = 0.0

    total_capabilities: int = 0
    stabilized_capabilities: int = 0
    inherited_capabilities: int = 0
    active_capabilities: int = 0

    current_phase: EvolutionPhase = EvolutionPhase.INITIALIZATION
    generations: int = 0
    generation_time_seconds: float = 0.0

    avg_fitness: float = 0.0
    max_fitness: float = 0.0
    min_fitness: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "evolution_rate": self.evolution_rate,
            "capabilities_per_generation": self.capabilities_per_generation,
            "capability_diversity": self.capability_diversity,
            "fitness_landscape": self.fitness_landscape,
            "fitness_variance": self.fitness_variance,
            "fitness_trend": self.fitness_trend,
            "adaptability_index": self.adaptability_index,
            "adaptation_latency": self.adaptation_latency,
            "selection_fidelity": self.selection_fidelity,
            "total_capabilities": self.total_capabilities,
            "stabilized_capabilities": self.stabilized_capabilities,
            "inherited_capabilities": self.inherited_capabilities,
            "active_capabilities": self.active_capabilities,
            "current_phase": self.current_phase.value,
            "generations": self.generations,
            "generation_time_seconds": self.generation_time_seconds,
            "avg_fitness": self.avg_fitness,
            "max_fitness": self.max_fitness,
            "min_fitness": self.min_fitness,
        }


@dataclass
class AgentCapabilitySnapshot:
    """Snapshot of agent capabilities at a point in time."""

    agent_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    capability_levels: dict[str, float] = field(default_factory=dict)
    fitness_score: float = 0.0
    fitness_history: list[float] = field(default_factory=list)
    behavior_diversity: float = 0.0
    behavior_innovation: float = 0.0
    success_rate: float = 0.0
    adaptation_count: int = 0
    active_capabilities: list[str] = field(default_factory=list)
    newly_acquired: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "capability_levels": self.capability_levels,
            "fitness_score": self.fitness_score,
            "fitness_history": self.fitness_history,
            "behavior_diversity": self.behavior_diversity,
            "behavior_innovation": self.behavior_innovation,
            "success_rate": self.success_rate,
            "adaptation_count": self.adaptation_count,
            "active_capabilities": self.active_capabilities,
            "newly_acquired": self.newly_acquired,
        }


@dataclass
class AgentBehaviorSnapshot:
    """Snapshot of an agent's behavior at a point in time."""

    agent_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    state: str = ""
    active_strategies: list[str] = field(default_factory=list)
    decision_history: list[dict[str, Any]] = field(default_factory=list)
    interaction_count: int = 0
    success_rate: float = 0.0
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "state": self.state,
            "active_strategies": self.active_strategies,
            "decision_history": self.decision_history,
            "interaction_count": self.interaction_count,
            "success_rate": self.success_rate,
            "metrics": self.metrics,
        }


@dataclass
class CollectiveBehavior:
    """Represents a collective behavior observed in the swarm."""

    behavior_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    behavior_type: str = ""
    participating_agents: list[str] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    end_time: str | None = None
    duration_seconds: float = 0.0
    intensity: float = 0.0
    coherence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "behavior_id": self.behavior_id,
            "behavior_type": self.behavior_type,
            "participating_agents": self.participating_agents,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "intensity": self.intensity,
            "coherence": self.coherence,
            "metadata": self.metadata,
        }


@dataclass
class EmergentPattern:
    """An emergent pattern detected in swarm behavior."""

    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_class: EmergentPatternClass = EmergentPatternClass.COORDINATION
    emergence_level: EmergenceLevel = EmergenceLevel.WEAK

    emergence_score: float = 0.0  # Core emergence metric used by validation
    participating_agents: list[str] = field(default_factory=list)  # Alias for involved_agents
    involved_agents: list[str] = field(default_factory=list)

    impact_score: float = 0.0
    novelty_score: float = 0.0  # How novel this pattern is compared to history
    provenance: PatternProvenance = PatternProvenance.UNPROVEN  # PROVEN or UNPROVEN
    validation_rate: float = 0.0  # Fraction of validations that passed

    solution_novelty: float = 0.0  # Novelty of the solution/outcome (vs pattern novelty)
    solution_provenance: PatternProvenance = PatternProvenance.UNPROVEN  # Provenance of solution

    statistical_significance: float = 0.0  # Calculated during validation
    emergence_ratio: float = 0.0  # Used by calculate_confidence
    frequency: int = 1  # How many times this pattern has been observed
    first_detected: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    confidence: float = 0.0
    is_validated: bool = False  # Set during _validate_and_store_pattern

    description: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    detected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    validated: bool = False
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_class": self.pattern_class.value,
            "emergence_level": self.emergence_level.value,
            "emergence_score": self.emergence_score,
            "participating_agents": self.participating_agents,
            "involved_agents": self.involved_agents,
            "impact_score": self.impact_score,
            "novelty_score": self.novelty_score,
            "provenance": self.provenance.value,
            "validation_rate": self.validation_rate,
            "solution_novelty": self.solution_novelty,
            "solution_provenance": self.solution_provenance.value,
            "statistical_significance": self.statistical_significance,
            "emergence_ratio": self.emergence_ratio,
            "frequency": self.frequency,
            "first_detected": self.first_detected,
            "confidence": self.confidence,
            "is_validated": self.is_validated,
            "description": self.description,
            "evidence": self.evidence,
            "detected_at": self.detected_at,
            "validated": self.validated,
            "accepted": self.accepted,
        }

    def to_extracted_pattern(self) -> ExtractedPattern:
        """Convert to collective learning ExtractedPattern."""
        return ExtractedPattern(
            pattern_id=self.pattern_id,
            pattern_type=PatternType(self.pattern_class.value),
            content={
                "description": self.description,
                "evidence": self.evidence,
            },
            confidence=self.confidence,
            source=PatternSource.EMERGENT,
            metadata=PatternMetadata(
                agent_ids=self.involved_agents,
                impact_score=self.impact_score,
            ),
        )


@dataclass
class DetectionEvent:
    """Record of an emergence detection event."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""

    # Fields expected by _validate_and_store_pattern
    pattern: EmergentPattern | None = None
    detection_method: str = ""
    raw_score: float = 0.0
    threshold: float = 0.0
    passed_validation: bool = False
    validation_details: dict[str, Any] = field(default_factory=dict)

    event_type: str = ""
    agents_involved: list[str] = field(default_factory=list)

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "pattern_id": self.pattern_id,
            "detection_method": self.detection_method,
            "raw_score": self.raw_score,
            "threshold": self.threshold,
            "passed_validation": self.passed_validation,
            "validation_details": self.validation_details,
            "event_type": self.event_type,
            "agents_involved": self.agents_involved,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class EmergenceDetectionConfig:
    """Configuration for emergent pattern detection."""

    min_emergence_score: float = 0.3
    min_participating_agents: int = 3
    min_coherence: float = 0.5
    statistical_threshold: float = 0.05

    analysis_window_seconds: float = 300.0
    baseline_window_seconds: float = 600.0

    validation_required: bool = True
    min_confidence: float = 0.6

    enable_coordination_detection: bool = True
    enable_optimization_detection: bool = True
    enable_innovation_detection: bool = True
    enable_phase_transition_detection: bool = True

    max_detections_per_window: int = 10
