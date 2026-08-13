"""
Type definitions for the Deliberation consensus engine.

The data classes and enums here are pure value objects used by
``DeliberationEngine`` (in ``deliberation.py``). They were
extracted from the engine module as part of the audit's Phase 2
god-class work — the engine itself remains a 1,000-LOC class but
its pure value-object surface is no longer interleaved with the
algorithm code.

The types module imports nothing from the engine. New code that
only needs the value objects (e.g. a UI that displays a
``DeliberationResult``) can import from here to avoid the heavier
transitive dependency on the engine and its async runtime.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any


class Position(Enum):
    """Agent's position on a deliberation topic."""

    FOR = "for"
    AGAINST = "against"
    NEUTRAL = "neutral"
    ABSTAIN = "abstain"


class DeliberationOutcome(Enum):
    """Outcome of a deliberation."""

    CONSENSUS = "consensus"
    MAJORITY = "majority"
    DEADLOCK = "deadlock"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ArgumentType(Enum):
    """Type of argument."""

    PRIMARY = "primary"
    SUPPORTING = "supporting"
    COUNTER = "counter"
    CLARIFICATION = "clarification"


class EvidenceType(Enum):
    """Types of evidence."""

    DATA = "data"
    TEST_RESULT = "test_result"
    EXPERT_OPINION = "expert_opinion"
    HISTORICAL = "historical"
    LOGICAL = "logical"
    SIMULATION = "simulation"


@dataclass
class Evidence:
    """
    Evidence submitted to support an argument.

    Attributes:
        evidence_id: Unique identifier
        evidence_type: Type of evidence
        content: Evidence content or reference
        source: Source of the evidence
        reliability_score: Reliability rating (0.0-1.0)
        timestamp: Submission timestamp
        submitted_by: Agent who submitted evidence
    """

    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    evidence_type: EvidenceType = EvidenceType.DATA
    content: str = ""
    source: str | None = None
    reliability_score: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    submitted_by: str = ""

    def calculate_quality(self) -> float:
        """
        Calculate evidence quality score.

        Returns:
            Quality score (0.0 to 1.0)
        """
        # Base quality from reliability
        base_quality = self.reliability_score

        # Type-based modifiers
        type_modifiers = {
            EvidenceType.DATA: 1.0,
            EvidenceType.TEST_RESULT: 0.95,
            EvidenceType.EXPERT_OPINION: 0.8,
            EvidenceType.HISTORICAL: 0.85,
            EvidenceType.LOGICAL: 0.9,
            EvidenceType.SIMULATION: 0.75,
        }

        type_modifier = type_modifiers.get(self.evidence_type, 0.8)

        # Source verification bonus
        source_bonus = 0.1 if self.source else 0.0

        return min(1.0, base_quality * type_modifier + source_bonus)


@dataclass
class Argument:
    """
    An argument submitted during deliberation.

    Attributes:
        argument_id: Unique identifier
        agent_id: Submitting agent
        position: Position (for/against/neutral)
        reasoning: Argument reasoning text
        evidence_refs: References to supporting evidence
        confidence: Confidence in argument (0.0-1.0)
        argument_type: Type of argument
        supports: IDs of arguments this supports
        rebuttals: IDs of arguments this rebuts
        timestamp: Submission timestamp
    """

    argument_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    position: Position = Position.NEUTRAL
    reasoning: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    argument_type: ArgumentType = ArgumentType.PRIMARY
    supports: list[str] = field(default_factory=list)
    rebuttals: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expertise_weight: float = 1.0

    def calculate_strength(self, evidence_dict: dict[str, "Evidence"]) -> float:
        """
        Calculate argument strength based on evidence and confidence.

        Args:
            evidence_dict: Dictionary of evidence by ID

        Returns:
            Strength score (0.0-1.0)
        """
        # Base strength from confidence
        base_strength = self.confidence

        # Evidence quality contribution
        evidence_scores: list[float] = []
        for ref in self.evidence_refs:
            if ref in evidence_dict:
                evidence_scores.append(evidence_dict[ref].calculate_quality())

        evidence_contribution = (
            sum(evidence_scores) / len(evidence_scores) if evidence_scores else 0.0
        )

        # Weight evidence at 40%, confidence at 60%
        strength = 0.6 * base_strength + 0.4 * evidence_contribution

        # Apply expertise weight
        strength *= self.expertise_weight

        return min(1.0, strength)


@dataclass
class CounterArgument:
    """
    A counter-argument responding to another argument.

    Attributes:
        counter_id: Unique identifier
        original_argument_id: ID of argument being countered
        agent_id: Submitting agent
        counter_reasoning: Counter-argument reasoning
        evidence_refs: References to supporting evidence
        confidence: Confidence in counter-argument
        timestamp: Submission timestamp
    """

    counter_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_argument_id: str = ""
    agent_id: str = ""
    counter_reasoning: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expertise_weight: float = 1.0

    def calculate_effectiveness(self, evidence_dict: dict[str, "Evidence"]) -> float:
        """
        Calculate counter-argument effectiveness.

        Args:
            evidence_dict: Dictionary of evidence by ID

        Returns:
            Effectiveness score (0.0-1.0)
        """
        # Base effectiveness from confidence
        base_effectiveness = self.confidence

        # Evidence contribution
        evidence_scores: list[float] = []
        for ref in self.evidence_refs:
            if ref in evidence_dict:
                evidence_scores.append(evidence_dict[ref].calculate_quality())

        evidence_contribution = (
            sum(evidence_scores) / len(evidence_scores) if evidence_scores else 0.0
        )

        # Weight evidence at 40%, confidence at 60%
        effectiveness = 0.6 * base_effectiveness + 0.4 * evidence_contribution

        # Apply expertise weight
        effectiveness *= self.expertise_weight

        return min(1.0, effectiveness)


@dataclass
class DeliberationRound:
    """
    Results from a single deliberation round.

    Attributes:
        round_id: Unique round identifier
        topic: Deliberation topic
        arguments: Arguments submitted in this round
        counter_arguments: Counter-arguments submitted
        evidence_submitted: New evidence submitted
        participant_agents: Participating agents
        round_duration: Duration of the round
        outcome: Round outcome
        consensus_score: Current consensus score
        position_changes: Number of position changes
    """

    round_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    arguments: list[Argument] = field(default_factory=list)
    counter_arguments: list[CounterArgument] = field(default_factory=list)
    evidence_submitted: list[Evidence] = field(default_factory=list)
    participant_agents: list[str] = field(default_factory=list)
    round_duration: timedelta = timedelta(0)
    outcome: DeliberationOutcome = DeliberationOutcome.DEADLOCK
    consensus_score: float = 0.0
    position_changes: int = 0
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    end_time: str | None = None


@dataclass
class PositionChange:
    """
    Record of a position change during deliberation.

    Attributes:
        agent_id: Agent who changed position
        previous_position: Position before change
        new_position: Position after change
        round_number: Round when change occurred
        timestamp: When the change occurred
        reasoning: Optional reasoning for the change
    """

    agent_id: str = ""
    previous_position: Position = Position.NEUTRAL
    new_position: Position = Position.NEUTRAL
    round_number: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    reasoning: str = ""


@dataclass
class DissentRecord:
    """
    Record of dissenting opinion for minority report.

    Attributes:
        agent_id: Dissenting agent
        position: Agent's position
        confidence: Confidence in dissenting position
        reasoning: Reasoning for dissent
        key_arguments: Key arguments supporting dissent
        resolved: Whether dissent was resolved
        resolution_notes: Notes on resolution attempt
        position_changes: History of position changes for this agent
    """

    agent_id: str = ""
    position: Position = Position.NEUTRAL
    confidence: float = 0.0
    reasoning: str = ""
    key_arguments: list[str] = field(default_factory=list)
    resolved: bool = False
    resolution_notes: str | None = None
    position_changes: list[PositionChange] = field(default_factory=list)


@dataclass
class ConsensusConfidence:
    """
    Consensus confidence scoring.

    Attributes:
        overall_confidence: Overall confidence in consensus
        evidence_quality_avg: Average evidence quality
        agreement_level: Level of agreement
        dissent_count: Number of dissenting agents
        dissent_severity: Severity of dissent
        stability_score: How stable the consensus is
    """

    overall_confidence: float = 0.0
    evidence_quality_avg: float = 0.0
    agreement_level: float = 0.0
    dissent_count: int = 0
    dissent_severity: float = 0.0
    stability_score: float = 0.0

    def calculate(
        self,
        for_weight: float,
        against_weight: float,
        total_weight: float,
        evidence_scores: list[float],
        dissent_records: list[DissentRecord],
    ) -> None:
        """
        Calculate consensus confidence.

        Args:
            for_weight: Total weight of 'for' positions
            against_weight: Total weight of 'against' positions
            total_weight: Total weight of all positions
            evidence_scores: List of evidence quality scores
            dissent_records: List of dissent records
        """
        # Agreement level (0.5-1.0)
        if total_weight > 0:
            majority_weight = max(for_weight, against_weight)
            self.agreement_level = majority_weight / total_weight
        else:
            self.agreement_level = 0.5

        # Evidence quality
        self.evidence_quality_avg = (
            sum(evidence_scores) / len(evidence_scores) if evidence_scores else 0.0
        )

        # Dissent metrics
        self.dissent_count = len(dissent_records)
        if dissent_records:
            self.dissent_severity = sum(d.confidence for d in dissent_records) / len(
                dissent_records
            )
        else:
            self.dissent_severity = 0.0

        # Stability based on position changes in recent rounds
        self.stability_score = (
            1.0 - (self.dissent_severity * 0.3) - ((1 - self.agreement_level) * 0.3)
        )

        # Overall confidence
        self.overall_confidence = (
            0.35 * self.agreement_level
            + 0.25 * self.evidence_quality_avg
            + 0.20 * self.stability_score
            + 0.20 * (1.0 - self.dissent_severity)
        )


@dataclass
class DeliberationResult:
    """
    Final result of a deliberation.

    Attributes:
        deliberation_id: Deliberation identifier
        topic: Deliberation topic
        outcome: Final outcome
        final_position: Final agreed position
        consensus_score: Final consensus score
        confidence: Consensus confidence
        dissenting_agents: Agents who dissented
        minority_report: Summary of minority opinions
        rounds_completed: Number of rounds run
        total_arguments: Total arguments submitted
        total_evidence: Total evidence pieces
        decision_hash: Immutable hash of decision
        timestamp: Result timestamp
    """

    deliberation_id: str = ""
    topic: str = ""
    outcome: DeliberationOutcome = DeliberationOutcome.DEADLOCK
    final_position: Position = Position.NEUTRAL
    consensus_score: float = 0.0
    confidence: ConsensusConfidence = field(default_factory=ConsensusConfidence)
    dissenting_agents: list[str] = field(default_factory=list)
    minority_report: list[DissentRecord] = field(default_factory=list)
    rounds_completed: int = 0
    total_arguments: int = 0
    total_evidence: int = 0
    decision_hash: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DeliberationConfig:
    """
    Configuration for deliberation engine.

    Attributes:
        max_rounds: Maximum deliberation rounds
        consensus_threshold: Threshold for consensus
        min_participants: Minimum required participants
        round_timeout_seconds: Timeout per round
        evidence_weight: Weight for evidence in scoring
        expertise_weight: Weight for expertise in scoring
        dissent_tracking: Enable dissent tracking
    """

    max_rounds: int = 5
    consensus_threshold: float = 0.75
    min_participants: int = 3
    round_timeout_seconds: float = 300.0
    evidence_weight: float = 0.35
    expertise_weight: float = 0.30
    dissent_tracking: bool = True


__all__ = [
    "Argument",
    "ArgumentType",
    "ConsensusConfidence",
    "CounterArgument",
    "DeliberationConfig",
    "DeliberationOutcome",
    "DeliberationResult",
    "DeliberationRound",
    "DissentRecord",
    "Evidence",
    "EvidenceType",
    "Position",
    "PositionChange",
]
