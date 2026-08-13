"""
Type definitions for the Enhanced MAKER consensus engine.

The data classes and enum here are pure value objects used by
``EnhancedMAKERConsensus`` (in ``maker_enhanced.py``). They were
extracted from the engine module as part of the audit's Phase 2
god-class work — the engine itself remains a 1,200-LOC class but
its pure value-object surface is no longer interleaved with the
algorithm code.

This module re-exports nothing from the engine. Importing it
does not pull in the NATS publisher, expertise profiler, or the
algorithm itself; new code that only needs the types (e.g. UI
code that displays a ``DecisionProvenance``) can import from here
to avoid the heavier transitive dependency.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from heretek_swarm_core.consensus.maker import Vote


class ReasoningChainStatus(Enum):
    """Status of reasoning chain validation."""

    VALID = "valid"
    INVALID = "invalid"
    INCOMPLETE = "incomplete"
    CIRCULAR = "circular"
    UNVERIFIED = "unverified"


@dataclass
class ReasoningStep:
    """
    Single step in a reasoning chain.

    Attributes:
        step_number: Step sequence number
        step_type: Type of step (observation, inference, conclusion)
        content: Step content
        confidence: Confidence in this step
        sources: Optional source references
        validates: IDs of steps this validates
    """

    step_number: int
    step_type: str  # "observation", "inference", "conclusion"
    content: str
    confidence: float
    sources: list[str] = field(default_factory=list)
    validates: list[str] = field(default_factory=list)


@dataclass
class ReasoningChain:
    """
    Complete reasoning chain for a decision.

    Attributes:
        chain_id: Unique chain identifier
        agent_id: Agent who created the chain
        steps: Ordered list of reasoning steps
        status: Validation status
        validation_errors: List of validation errors
        created_at: Creation timestamp
        pattern_references: List of pattern IDs referenced in this chain
    """

    chain_id: str
    agent_id: str
    steps: list[ReasoningStep]
    status: ReasoningChainStatus = ReasoningChainStatus.UNVERIFIED
    validation_errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    pattern_references: list[str] = field(default_factory=list)

    def add_step(
        self,
        step_type: str,
        content: str,
        confidence: float,
        sources: list[str] | None = None,
    ) -> ReasoningStep:
        """Add a step to the reasoning chain."""
        step = ReasoningStep(
            step_number=len(self.steps) + 1,
            step_type=step_type,
            content=content,
            confidence=confidence,
            sources=sources or [],
        )
        self.steps.append(step)
        return step

    def validate_chain(self) -> bool:
        """
        Validate the reasoning chain for logical consistency.

        Returns:
            True if chain is valid
        """
        errors: list[str] = []

        if not self.steps:
            errors.append("Empty reasoning chain")
            self.status = ReasoningChainStatus.INVALID
            return False

        # Check for required conclusion step
        has_conclusion = any(s.step_type == "conclusion" for s in self.steps)
        if not has_conclusion:
            errors.append("Missing conclusion step")

        # Check chain flow: observation -> inference -> conclusion
        step_types = [s.step_type for s in self.steps]
        if "observation" not in step_types:
            errors.append("Missing observation step")

        # Check for circular reasoning
        errors.extend(self._check_circular_reasoning())

        # Check confidence consistency
        errors.extend(self._check_confidence_consistency())

        if errors:
            self.validation_errors = errors
            self.status = ReasoningChainStatus.INVALID
            return False

        self.status = ReasoningChainStatus.VALID
        return True

    def _check_circular_reasoning(self) -> list[str]:
        """Check for circular reasoning in the chain."""
        errors: list[str] = []
        for step in self.steps:
            if step.step_type != "observation":
                continue
            for _validates_id in step.validates:
                validating_step = next((s for s in self.steps if id(s) == id(step)), None)
                if not validating_step or validating_step.step_type != "conclusion":
                    continue
                errors.append("Circular reasoning detected")
                self.status = ReasoningChainStatus.CIRCULAR
                return errors
        return errors

    def _check_confidence_consistency(self) -> list[str]:
        """Check for confidence consistency across steps."""
        errors: list[str] = []
        confidences = [s.confidence for s in self.steps]
        if confidences:
            statistics.mean(confidences)
            low_confidence_steps = [s for s in self.steps if s.confidence < 0.5]
            if len(low_confidence_steps) > len(self.steps) / 2:
                errors.append("Majority of steps have low confidence")
        return errors


@dataclass
class EvidenceQuality:
    """
    Evidence quality metrics for vote weighting.

    Attributes:
        source_count: Number of evidence sources
        source_reliability: Average reliability of sources (0.0 to 1.0)
        completeness: How complete the evidence is (0.0 to 1.0)
        consistency: Internal consistency of evidence (0.0 to 1.0)
        recency_score: How recent the evidence is (0.0 to 1.0)
    """

    source_count: int = 0
    source_reliability: float = 0.5
    completeness: float = 0.5
    consistency: float = 0.5
    recency_score: float = 0.5

    def calculate_quality_score(self) -> float:
        """
        Calculate overall evidence quality score.

        Returns:
            Quality score (0.0 to 1.0)
        """
        if self.source_count == 0:
            return 0.5  # Default for no evidence

        # Weight factors for quality calculation
        weights = {
            "reliability": 0.35,
            "completeness": 0.25,
            "consistency": 0.25,
            "recency": 0.15,
        }

        score = (
            self.source_reliability * weights["reliability"]
            + self.completeness * weights["completeness"]
            + self.consistency * weights["consistency"]
            + self.recency_score * weights["recency"]
        )

        # Bonus for multiple sources (diminishing returns)
        source_bonus = min(0.1, self.source_count * 0.02)

        return max(0.0, min(1.0, score + source_bonus))


@dataclass
class EnhancedVote:
    """
    Enhanced vote with reasoning chain and pattern integration.

    Attributes:
        vote: Base vote object
        reasoning_chain: Optional reasoning chain
        pattern_references: References to patterns from pattern library
        cross_validated: Whether vote has been cross-validated
        validation_score: Score from cross-validation
        evidence_quality: Evidence quality metrics
        vote_weight: Calculated vote weight
    """

    vote: "Vote"
    reasoning_chain: ReasoningChain | None = None
    pattern_references: list[str] = field(default_factory=list)
    cross_validated: bool = False
    validation_score: float = 0.0
    evidence_quality: EvidenceQuality | None = None
    vote_weight: float = 1.0

    @property
    def agent_id(self) -> str:
        return self.vote.agent_id

    @property
    def decision(self) -> str:
        return self.vote.decision

    @property
    def confidence(self) -> float:
        return self.vote.confidence


@dataclass
class DecisionProvenance:
    """
    Complete provenance tracking for a decision.

    Attributes:
        decision_id: Decision identifier
        proposal: Original proposal
        start_time: Consensus start time
        end_time: Consensus end time
        participating_agents: List of participating agents
        votes_cast: Total votes cast
        reasoning_chains: All reasoning chains submitted
        patterns_used: Patterns referenced during deliberation
        validation_results: Cross-validation results
        rollback_available: Whether rollback is possible
        rollback_checkpoint: Checkpoint data for rollback
    """

    decision_id: str
    proposal: str
    start_time: str
    end_time: str | None = None
    participating_agents: list[str] = field(default_factory=list)
    votes_cast: int = 0
    reasoning_chains: list[ReasoningChain] = field(default_factory=list)
    patterns_used: list[str] = field(default_factory=list)
    validation_results: dict[str, Any] = field(default_factory=dict)
    rollback_available: bool = False
    rollback_checkpoint: dict[str, Any] | None = None


@dataclass
class RollbackResult:
    """
    Result of a rollback operation.

    Attributes:
        success: Whether rollback succeeded
        message: Result message
        previous_state: State rolled back to
        timestamp: Rollback timestamp
    """

    success: bool
    message: str
    previous_state: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


__all__ = [
    "DecisionProvenance",
    "EnhancedVote",
    "EvidenceQuality",
    "ReasoningChain",
    "ReasoningChainStatus",
    "ReasoningStep",
    "RollbackResult",
]
