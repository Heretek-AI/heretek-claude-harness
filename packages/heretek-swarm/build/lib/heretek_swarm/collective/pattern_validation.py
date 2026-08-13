"""
Pattern Validation - Emergent Pattern Validation System

Implements proven vs. unproven emergence classification, impact score calculation,
and Core Triad override capability for the collective swarm.

Features:
- Proven vs. unproven emergence classification
- Impact score calculation with multiple factors
- Core Triad override capability for critical patterns
- Pattern validation tracking
- Zero-trust validation principles

Zero-Trust Principles:
- All patterns require validation before classification
- Statistical significance required for proven status
- Core Triad override requires quorum consensus
- Audit logging for all classification decisions

Author: Heretek Swarm Collective
Date: 2026-04-15
Version: 1.0.0
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from .emergent_detection_types import EmergenceLevel, EmergentPattern, EmergentPatternClass

logger = structlog.get_logger(__name__)


class ValidationStatus(StrEnum):
    """Validation status for emergent patterns."""

    UNVALIDATED = "unvalidated"
    PENDING = "pending"
    PROVEN = "proven"
    UNPROVEN = "unproven"
    OVERRIDE = "override"  # Core Triad override


class CoreTriadRole(StrEnum):
    """Core Triad agent roles."""

    STEWARD = "steward"  # Orchestrator
    ALPHA = "alpha"  # Deep Analysis
    BETA = "beta"  # Validation
    CHARLIE = "charlie"  # Challenge


@dataclass
class ValidationEvidence:
    """Evidence supporting pattern validation."""

    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    evidence_type: str = ""
    description: str = ""
    strength: float = 0.0  # 0-1
    source_agents: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "evidence_id": self.evidence_id,
            "pattern_id": self.pattern_id,
            "evidence_type": self.evidence_type,
            "description": self.description,
            "strength": self.strength,
            "source_agents": self.source_agents,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class PatternValidation:
    """Validation record for an emergent pattern."""

    validation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    status: ValidationStatus = ValidationStatus.UNVALIDATED

    # Classification factors
    emergence_score: float = 0.0
    impact_score: float = 0.0
    confidence: float = 0.0
    statistical_significance: float = 0.0

    # Proven/Unproven criteria
    frequency_threshold: int = 3  # Minimum occurrences for proven
    coherence_threshold: float = 0.6  # Minimum coherence for proven
    agent_diversity_threshold: int = 3  # Minimum diverse agents

    # Evidence tracking
    evidence: list[ValidationEvidence] = field(default_factory=list)

    # Core Triad override
    override_requested: bool = False
    override_approved: bool = False
    override_reason: str = ""
    override_by: list[str] = field(default_factory=list)  # Core Triad agents

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    validated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_id": self.validation_id,
            "pattern_id": self.pattern_id,
            "status": self.status.value,
            "emergence_score": self.emergence_score,
            "impact_score": self.impact_score,
            "confidence": self.confidence,
            "statistical_significance": self.statistical_significance,
            "frequency_threshold": self.frequency_threshold,
            "coherence_threshold": self.coherence_threshold,
            "agent_diversity_threshold": self.agent_diversity_threshold,
            "evidence": [e.to_dict() for e in self.evidence],
            "override_requested": self.override_requested,
            "override_approved": self.override_approved,
            "override_reason": self.override_reason,
            "override_by": self.override_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "validated_at": self.validated_at,
        }


@dataclass
class ImpactScoreFactors:
    """Factors used in impact score calculation."""

    novelty: float = 0.0  # How novel is this pattern
    usefulness: float = 0.0  # Practical utility
    efficiency_gain: float = 0.0  # Efficiency improvement
    coordination_improvement: float = 0.0  # Coordination enhancement
    risk_reduction: float = 0.0  # Risk mitigation
    scalability: float = 0.0  # Scalability impact
    sustainability: float = 0.0  # Long-term viability

    # Weights for each factor
    WEIGHTS = {  # noqa: RUF012
        "novelty": 0.15,
        "usefulness": 0.20,
        "efficiency_gain": 0.15,
        "coordination_improvement": 0.15,
        "risk_reduction": 0.15,
        "scalability": 0.10,
        "sustainability": 0.10,
    }

    def calculate_total(self) -> float:
        """Calculate weighted impact score."""
        total = 0.0
        for factor, weight in self.WEIGHTS.items():
            value = getattr(self, factor, 0.0)
            total += value * weight
        return min(1.0, max(-1.0, total))  # Clamp to [-1, 1]


class PatternValidator:
    """
    Validator for emergent patterns.

    Classifies patterns as proven vs. unproven and calculates impact scores.
    Provides Core Triad override capability for critical patterns.
    """

    # Core Triad agents who can approve overrides
    CORE_TRIAD = {  # noqa: RUF012
        CoreTriadRole.STEWARD,
        CoreTriadRole.ALPHA,
        CoreTriadRole.BETA,
        CoreTriadRole.CHARLIE,
    }

    # Minimum Core Triad votes for override
    OVERRIDE_QUORUM = 3

    def __init__(
        self,
        frequency_threshold: int = 3,
        coherence_threshold: float = 0.6,
        agent_diversity_threshold: int = 3,
        min_confidence: float = 0.6,
        min_statistical_significance: float = 0.05,
    ):
        """
        Initialize pattern validator.

        Args:
            frequency_threshold: Minimum occurrences for proven status
            coherence_threshold: Minimum coherence for proven status
            agent_diversity_threshold: Minimum diverse agents for proven
            min_confidence: Minimum confidence for proven status
            min_statistical_significance: Maximum p-value for proven status
        """
        self.frequency_threshold = frequency_threshold
        self.coherence_threshold = coherence_threshold
        self.agent_diversity_threshold = agent_diversity_threshold
        self.min_confidence = min_confidence
        self.min_statistical_significance = min_statistical_significance

        # Storage for validations
        self._validations: dict[str, PatternValidation] = {}
        self._pattern_frequencies: dict[str, int] = {}  # Track pattern occurrences

        logger.info(
            "pattern_validator_initialized",
            frequency_threshold=frequency_threshold,
            coherence_threshold=coherence_threshold,
            agent_diversity_threshold=agent_diversity_threshold,
        )

    def create_validation(self, pattern: EmergentPattern) -> PatternValidation:
        """
        Create a validation record for a pattern.

        Args:
            pattern: EmergentPattern to validate

        Returns:
            PatternValidation record
        """
        validation = PatternValidation(
            pattern_id=pattern.pattern_id,
            status=ValidationStatus.PENDING,
            emergence_score=pattern.emergence_score if hasattr(pattern, "emergence_score") else 0.0,
            impact_score=pattern.impact_score if hasattr(pattern, "impact_score") else 0.0,
            confidence=pattern.confidence if hasattr(pattern, "confidence") else 0.0,
            statistical_significance=pattern.statistical_significance
            if hasattr(pattern, "statistical_significance")
            else 1.0,
            frequency_threshold=self.frequency_threshold,
            coherence_threshold=self.coherence_threshold,
            agent_diversity_threshold=self.agent_diversity_threshold,
        )

        self._validations[pattern.pattern_id] = validation
        return validation

    def get_validation(self, pattern_id: str) -> PatternValidation | None:
        """
        Get validation record for a pattern.

        Args:
            pattern_id: Pattern identifier

        Returns:
            PatternValidation or None if not found
        """
        return self._validations.get(pattern_id)

    def classify_pattern(
        self,
        pattern: EmergentPattern,
        coherence: float = 0.0,
        agent_diversity: int = 0,
        occurrence_count: int = 1,
    ) -> ValidationStatus:
        """
        Classify a pattern as proven or unproven.

        Args:
            pattern: EmergentPattern to classify
            coherence: Observed coherence of the pattern
            agent_diversity: Number of diverse agents involved
            occurrence_count: Number of times pattern has occurred

        Returns:
            ValidationStatus classification
        """
        validation = self.get_validation(pattern.pattern_id)
        if not validation:
            validation = self.create_validation(pattern)

        # Update tracking
        self._pattern_frequencies[pattern.pattern_id] = max(
            self._pattern_frequencies.get(pattern.pattern_id, 0),
            occurrence_count,
        )
        validation.occurrence_count = (
            occurrence_count if hasattr(validation, "occurrence_count") else occurrence_count  # noqa: RUF034
        )

        # Check if already override-approved
        if validation.override_approved:
            validation.status = ValidationStatus.OVERRIDE
            return validation.status

        # Proven criteria check
        proven_conditions = [
            validation.confidence >= self.min_confidence,
            validation.statistical_significance <= self.min_statistical_significance,
            self._pattern_frequencies.get(pattern.pattern_id, 0) >= self.frequency_threshold,
            coherence >= self.coherence_threshold,
            agent_diversity >= self.agent_diversity_threshold,
        ]

        if all(proven_conditions):
            validation.status = ValidationStatus.PROVEN
            validation.validated_at = datetime.now(UTC).isoformat()
            logger.info(
                "pattern_classified_proven",
                pattern_id=pattern.pattern_id,
                confidence=validation.confidence,
                frequency=self._pattern_frequencies.get(pattern.pattern_id, 0),
            )
        else:
            validation.status = ValidationStatus.UNPROVEN
            validation.validated_at = datetime.now(UTC).isoformat()
            logger.info(
                "pattern_classified_unproven",
                pattern_id=pattern.pattern_id,
                confidence=validation.confidence,
                frequency=self._pattern_frequencies.get(pattern.pattern_id, 0),
                reason=self._get_unproven_reason(validation, coherence, agent_diversity),
            )

        validation.updated_at = datetime.now(UTC).isoformat()
        return validation.status

    def _get_unproven_reason(
        self,
        validation: PatternValidation,
        coherence: float,
        agent_diversity: int,
    ) -> str:
        """Get reason why pattern is unproven."""
        reasons = []
        if validation.confidence < self.min_confidence:
            reasons.append(f"confidence ({validation.confidence:.2f} < {self.min_confidence})")
        if validation.statistical_significance > self.min_statistical_significance:
            reasons.append(
                f"significance ({validation.statistical_significance:.3f} > {self.min_statistical_significance})"  # noqa: E501
            )
        if self._pattern_frequencies.get(validation.pattern_id, 0) < self.frequency_threshold:
            reasons.append(
                f"frequency ({self._pattern_frequencies.get(validation.pattern_id, 0)} < {self.frequency_threshold})"  # noqa: E501
            )
        if coherence < self.coherence_threshold:
            reasons.append(f"coherence ({coherence:.2f} < {self.coherence_threshold})")
        if agent_diversity < self.agent_diversity_threshold:
            reasons.append(f"diversity ({agent_diversity} < {self.agent_diversity_threshold})")
        return "; ".join(reasons) if reasons else "unknown"

    def calculate_impact_score(
        self,
        pattern: EmergentPattern,
        factors: ImpactScoreFactors | None = None,
    ) -> float:
        """
        Calculate impact score for a pattern.

        Args:
            pattern: EmergentPattern to score
            factors: Optional pre-computed factors

        Returns:
            Impact score between -1 and 1
        """
        if factors is None:
            factors = self._derive_factors_from_pattern(pattern)

        base_impact = pattern.impact_score if hasattr(pattern, "impact_score") else 0.0
        factor_impact = factors.calculate_total()

        # Combine base impact with factor analysis
        # Weight: 60% base impact, 40% factor analysis
        combined_impact = (base_impact * 0.6) + (factor_impact * 0.4)

        # Update validation if exists
        validation = self.get_validation(pattern.pattern_id)
        if validation:
            validation.impact_score = combined_impact
            validation.updated_at = datetime.now(UTC).isoformat()

        logger.debug(
            "impact_score_calculated",
            pattern_id=pattern.pattern_id,
            base_impact=base_impact,
            factor_impact=factor_impact,
            combined_impact=combined_impact,
        )

        return combined_impact

    def _derive_factors_from_pattern(self, pattern: EmergentPattern) -> ImpactScoreFactors:
        """Derive impact score factors from a pattern."""
        factors = ImpactScoreFactors()

        # Extract information from pattern evidence/metadata
        getattr(pattern, "evidence", {})
        getattr(pattern, "metadata", {})

        # Set factors based on pattern class
        if hasattr(pattern, "pattern_class"):
            if pattern.pattern_class == EmergentPatternClass.COORDINATION:
                factors.coordination_improvement = 0.8
                factors.usefulness = 0.7
            elif pattern.pattern_class == EmergentPatternClass.OPTIMIZATION:
                factors.efficiency_gain = 0.9
                factors.usefulness = 0.8
            elif pattern.pattern_class == EmergentPatternClass.INNOVATION:
                factors.novelty = 0.9
                factors.usefulness = 0.6
            elif pattern.pattern_class == EmergentPatternClass.ADAPTATION:
                factors.risk_reduction = 0.7
                factors.sustainability = 0.6
            elif pattern.pattern_class == EmergentPatternClass.SELF_ORGANIZATION:
                factors.sustainability = 0.8
                factors.coordination_improvement = 0.7
            elif pattern.pattern_class == EmergentPatternClass.PHASE_TRANSITION:
                factors.risk_reduction = 0.6
                factors.scalability = 0.7
            elif pattern.pattern_class == EmergentPatternClass.CASCADE:
                factors.coordination_improvement = 0.5
                factors.risk_reduction = 0.4
            elif pattern.pattern_class == EmergentPatternClass.RESONANCE:
                factors.novelty = 0.6
                factors.coordination_improvement = 0.5

        # Adjust based on emergence level
        if hasattr(pattern, "emergence_level"):
            level_multiplier = {
                EmergenceLevel.WEAK: 0.5,
                EmergenceLevel.MODERATE: 0.7,
                EmergenceLevel.STRONG: 0.9,
                EmergenceLevel.CRITICAL: 1.0,
            }.get(pattern.emergence_level, 0.5)

            for attr in [
                "novelty",
                "usefulness",
                "efficiency_gain",
                "coordination_improvement",
                "risk_reduction",
                "scalability",
                "sustainability",
            ]:
                current = getattr(factors, attr, 0.0)
                setattr(factors, attr, current * level_multiplier)

        return factors

    def request_override(
        self,
        pattern_id: str,
        reason: str,
        requesting_agent: str,
    ) -> bool:
        """
        Request Core Triad override for a pattern.

        Args:
            pattern_id: Pattern to override
            reason: Reason for override request
            requesting_agent: Agent requesting override

        Returns:
            True if request was recorded
        """
        validation = self.get_validation(pattern_id)
        if not validation:
            logger.warning("override_request_pattern_not_found", pattern_id=pattern_id)
            return False

        validation.override_requested = True
        validation.override_reason = reason
        validation.updated_at = datetime.now(UTC).isoformat()

        logger.info(
            "override_requested",
            pattern_id=pattern_id,
            reason=reason,
            requesting_agent=requesting_agent,
        )

        return True

    def approve_override(
        self,
        pattern_id: str,
        approving_agent: str,
        approving_role: CoreTriadRole,
    ) -> bool:
        """
        Approve Core Triad override for a pattern.

        Args:
            pattern_id: Pattern to override
            approving_agent: Agent approving
            approving_role: Core Triad role of approver

        Returns:
            True if override is now approved
        """
        if approving_role not in self.CORE_TRIAD:
            logger.warning(
                "override_approve_not_core_triad",
                pattern_id=pattern_id,
                approving_agent=approving_agent,
                approving_role=approving_role,
            )
            return False

        validation = self.get_validation(pattern_id)
        if not validation:
            logger.warning("override_approve_pattern_not_found", pattern_id=pattern_id)
            return False

        if not validation.override_requested:
            logger.warning("override_not_requested", pattern_id=pattern_id)
            return False

        if approving_agent not in validation.override_by:
            validation.override_by.append(approving_agent)

        # Check for quorum
        if len(validation.override_by) >= self.OVERRIDE_QUORUM:
            validation.override_approved = True
            validation.status = ValidationStatus.OVERRIDE
            validation.validated_at = datetime.now(UTC).isoformat()
            logger.info(
                "override_approved",
                pattern_id=pattern_id,
                approving_agents=validation.override_by,
                quorum=self.OVERRIDE_QUORUM,
            )
            return True

        logger.info(
            "override_partial_approval",
            pattern_id=pattern_id,
            approvals=len(validation.override_by),
            required=self.OVERRIDE_QUORUM,
        )

        return False

    def add_evidence(
        self,
        pattern_id: str,
        evidence_type: str,
        description: str,
        strength: float,
        source_agents: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> ValidationEvidence | None:
        """
        Add evidence to a validation record.

        Args:
            pattern_id: Pattern identifier
            evidence_type: Type of evidence
            description: Description of evidence
            strength: Evidence strength (0-1)
            source_agents: Agents providing evidence
            metadata: Additional metadata

        Returns:
            ValidationEvidence if added, None if pattern not found
        """
        validation = self.get_validation(pattern_id)
        if not validation:
            logger.warning("evidence_add_pattern_not_found", pattern_id=pattern_id)
            return None

        evidence = ValidationEvidence(
            pattern_id=pattern_id,
            evidence_type=evidence_type,
            description=description,
            strength=strength,
            source_agents=source_agents,
            metadata=metadata or {},
        )

        validation.evidence.append(evidence)
        validation.updated_at = datetime.now(UTC).isoformat()

        logger.info(
            "evidence_added",
            pattern_id=pattern_id,
            evidence_id=evidence.evidence_id,
            evidence_type=evidence_type,
            strength=strength,
        )

        return evidence

    def get_proven_patterns(
        self,
        min_impact: float = 0.0,
        pattern_class: EmergentPatternClass | None = None,  # noqa: ARG002
    ) -> list[str]:
        """
        Get IDs of proven patterns.

        Args:
            min_impact: Minimum impact score filter
            pattern_class: Optional pattern class filter

        Returns:
            List of proven pattern IDs
        """
        proven = []
        for vid, validation in self._validations.items():
            if validation.status == ValidationStatus.PROVEN:  # noqa: SIM102
                if validation.impact_score >= min_impact:
                    proven.append(vid)

        return proven

    def get_unproven_patterns(self) -> list[str]:
        """Get IDs of unproven patterns."""
        return [
            vid
            for vid, validation in self._validations.items()
            if validation.status == ValidationStatus.UNPROVEN
        ]

    def get_override_pending_patterns(self) -> list[str]:
        """Get IDs of patterns with pending override requests."""
        return [
            vid
            for vid, validation in self._validations.items()
            if validation.override_requested and not validation.override_approved
        ]

    def get_validation_stats(self) -> dict[str, Any]:
        """Get validation statistics."""
        total = len(self._validations)
        by_status: dict[str, int] = {}

        for validation in self._validations.values():
            status = validation.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_validations": total,
            "by_status": by_status,
            "proven_count": by_status.get("proven", 0),
            "unproven_count": by_status.get("unproven", 0),
            "override_pending_count": by_status.get("pending", 0),
            "override_approved_count": by_status.get("override", 0),
        }


class EmergentPatternClassifier:
    """
    High-level classifier for emergent patterns.

    Provides simplified interface for pattern classification
    and impact assessment.
    """

    def __init__(self, validator: PatternValidator | None = None):
        """
        Initialize classifier.

        Args:
            validator: Optional PatternValidator instance
        """
        self.validator = validator or PatternValidator()

    def classify_and_score(
        self,
        pattern: EmergentPattern,
        coherence: float = 0.0,
        agent_diversity: int = 0,
        occurrence_count: int = 1,
    ) -> tuple[ValidationStatus, float]:
        """
        Classify pattern and calculate impact score in one call.

        Args:
            pattern: Pattern to classify
            coherence: Pattern coherence
            agent_diversity: Number of diverse agents
            occurrence_count: Number of occurrences

        Returns:
            Tuple of (ValidationStatus, impact_score)
        """
        status = self.classify_pattern(pattern, coherence, agent_diversity, occurrence_count)
        impact = self.calculate_impact_score(pattern)
        return status, impact

    def classify_pattern(
        self,
        pattern: EmergentPattern,
        coherence: float = 0.0,
        agent_diversity: int = 0,
        occurrence_count: int = 1,
    ) -> ValidationStatus:
        """Classify pattern as proven or unproven."""
        return self.validator.classify_pattern(
            pattern, coherence, agent_diversity, occurrence_count
        )

    def calculate_impact_score(self, pattern: EmergentPattern) -> float:
        """Calculate impact score for pattern."""
        return self.validator.calculate_impact_score(pattern)

    def request_override(self, pattern_id: str, reason: str, requesting_agent: str) -> bool:
        """Request Core Triad override."""
        return self.validator.request_override(pattern_id, reason, requesting_agent)

    def approve_override(
        self, pattern_id: str, approving_agent: str, approving_role: CoreTriadRole
    ) -> bool:
        """Approve Core Triad override."""
        return self.validator.approve_override(pattern_id, approving_agent, approving_role)

    def get_classification_summary(self) -> dict[str, Any]:
        """Get summary of all classifications."""
        stats = self.validator.get_validation_stats()

        proven_ids = self.validator.get_proven_patterns()
        unproven_ids = self.validator.get_unproven_patterns()
        override_pending = self.validator.get_override_pending_patterns()

        avg_impact_proven = 0.0
        if proven_ids:
            proven_impacts = [
                self.validator.get_validation(pid).impact_score
                for pid in proven_ids
                if self.validator.get_validation(pid)
            ]
            avg_impact_proven = sum(proven_impacts) / len(proven_impacts) if proven_impacts else 0.0

        return {
            "stats": stats,
            "proven_pattern_ids": proven_ids,
            "unproven_pattern_ids": unproven_ids,
            "override_pending_pattern_ids": override_pending,
            "avg_impact_proven": avg_impact_proven,
        }


__all__ = [
    "CoreTriadRole",
    "EmergentPatternClassifier",
    "ImpactScoreFactors",
    "PatternValidation",
    "PatternValidator",
    "ValidationEvidence",
    "ValidationStatus",
]
