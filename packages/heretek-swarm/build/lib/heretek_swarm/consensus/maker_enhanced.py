"""
Enhanced MAKER Protocol - Multi-Agent Knowledge Extraction & Reasoning with advanced features.

This module extends the base MAKER consensus with:
- Extended knowledge extraction with pattern library integration
- Cross-validation of reasoning chains
- Decision provenance tracking
- Rollback capability for failed decisions

The enhanced protocol builds upon the base MAKER algorithm to provide
more robust decision-making with full audit trails and recovery mechanisms.

Example:
    ```python
    from heretek_swarm.consensus.maker_enhanced import EnhancedMAKERConsensus

    # Initialize enhanced consensus
    consensus = EnhancedMAKERConsensus(
        ahead_by_k=2,
        min_votes=3,
        enable_pattern_library=True,
        enable_rollback=True
    )

    # Start consensus with pattern integration
    consensus.start_consensus("deploy-decision", domain="deployment")

    # Add votes with reasoning chains
    consensus.add_vote_with_reasoning(
        consensus_id="deploy-decision",
        agent_id="agent-1",
        decision="deploy",
        confidence=0.9,
        reasoning_chain=[
            {"step": 1, "observation": "All tests passed"},
            {"step": 2, "conclusion": "Safe to deploy"}
        ]
    )

    # Compute consensus with cross-validation
    result = consensus.compute_consensus_with_validation("deploy-decision")

    # Access decision provenance
    provenance = consensus.get_decision_provenance("deploy-decision")
    ```
"""

import hashlib
import json
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from heretek_swarm.consensus.expertise import AgentExpertiseProfiler
from heretek_swarm.consensus.maker import ConsensusResult, ConsensusState, MAKERConsensus, Vote
from heretek_swarm.infrastructure.nats.publisher import (
    NATSPublisher,
    get_nats_publisher,
)

logger = structlog.get_logger("EnhancedMAKERConsensus")


# Evidence quality thresholds
EVIDENCE_QUALITY_WEIGHT = 0.35  # Weight for evidence quality
EXPERTISE_WEIGHT = 0.30  # Weight for agent expertise
CONFIDENCE_WEIGHT = 0.20  # Weight for confidence level
HISTORICAL_WEIGHT = 0.15  # Weight for historical accuracy


# Cache for the publisher instance
_maker_publisher: NATSPublisher | None = None


async def _get_maker_publisher() -> NATSPublisher | None:
    """Get or create the NATS publisher with caching."""
    global _maker_publisher
    if _maker_publisher is None:
        try:
            _maker_publisher = await get_nats_publisher()
        except Exception:
            logger.warning("Failed to get NATS publisher in MAKER: {e}")
            return None
    return _maker_publisher


async def _emit_consensus_result(result: ConsensusResult, consensus_id: str) -> None:
    """
    Emit consensus result event to NATS (fire-and-forget).

    Does not block the consensus process on NATS unavailability.
    """
    try:
        publisher = await _get_maker_publisher()
        if publisher:
            # Use a fire-and-forget task
            import asyncio

            asyncio.create_task(  # noqa: RUF006
                publisher.emit_agent_event(
                    agent_id="maker",
                    event_type="consensus.result",
                    data={
                        "consensus_id": consensus_id,
                        "decision": result.decision,
                        "confidence": result.confidence,
                        "voter_counts": result.votes if isinstance(result.votes, dict) else {},
                    },
                )
            )
    except Exception as e:
        logger.debug("Consensus result emission failed: %s", e)


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
        errors = []

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
        errors = []
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

    vote: Vote
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


class EnhancedMAKERConsensus(MAKERConsensus):
    """
    Enhanced MAKER Consensus with advanced features.

    Extends the base MAKER consensus with:
    - Extended knowledge extraction with pattern library integration
    - Cross-validation of reasoning chains
    - Decision provenance tracking
    - Rollback capability for failed decisions

    The enhanced protocol maintains full audit trails and enables
    recovery from failed decisions through checkpoint-based rollback.

    Attributes:
        enable_pattern_library: Enable pattern library integration
        enable_rollback: Enable rollback capability
        enable_cross_validation: Enable cross-validation of reasoning
        expertise_profiler: Optional expertise profiler
    """

    def __init__(
        self,
        ahead_by_k: int = 2,
        min_votes: int = 3,
        confidence_threshold: float = 0.6,
        reputation_weights: dict[str, float] | None = None,
        enable_pattern_library: bool = True,
        enable_rollback: bool = True,
        enable_cross_validation: bool = True,
        expertise_profiler: AgentExpertiseProfiler | None = None,
        max_reasoning_depth: int = 10,
    ) -> None:
        """
        Initialize the enhanced consensus engine.

        Args:
            ahead_by_k: Number of votes needed to be ahead to win
            min_votes: Minimum number of votes required
            confidence_threshold: Minimum confidence threshold
            reputation_weights: Optional reputation weights per agent
            enable_pattern_library: Enable pattern library integration
            enable_rollback: Enable rollback capability
            enable_cross_validation: Enable cross-validation
            expertise_profiler: Optional expertise profiler
            max_reasoning_depth: Maximum reasoning chain depth
        """
        super().__init__(
            ahead_by_k=ahead_by_k,
            min_votes=min_votes,
            confidence_threshold=confidence_threshold,
            reputation_weights=reputation_weights,
        )

        self.enable_pattern_library = enable_pattern_library
        self.enable_rollback = enable_rollback
        self.enable_cross_validation = enable_cross_validation
        self.max_reasoning_depth = max_reasoning_depth

        # Initialize expertise profiler if not provided
        self.expertise_profiler = expertise_profiler or AgentExpertiseProfiler()

        # Enhanced vote storage
        self.enhanced_votes: dict[str, list[EnhancedVote]] = {}

        # Reasoning chains
        self.reasoning_chains: dict[str, list[ReasoningChain]] = {}

        # Decision provenance tracking
        self.decision_provenance: dict[str, DecisionProvenance] = {}

        # Rollback checkpoints
        self.rollback_checkpoints: dict[str, dict[str, Any]] = {}

        # Pattern library integration (simplified - would integrate with actual pattern library)
        self.pattern_library: dict[str, Any] = {}

        # Historical accuracy tracking per agent per consensus
        self.agent_accuracy_history: dict[str, dict[str, list[bool]]] = {}

        # Evidence quality cache
        self.evidence_cache: dict[str, EvidenceQuality] = {}

        logger.info(
            f"EnhancedMAKERConsensus initialized with "  # noqa: G004
            f"pattern_library={enable_pattern_library}, "
            f"rollback={enable_rollback}, "
            f"cross_validation={enable_cross_validation}"
        )

    def start_consensus(
        self,
        consensus_id: str,
        proposal: str | None = None,
        domain: str | None = None,
    ) -> None:
        """
        Start a new enhanced consensus process.

        Args:
            consensus_id: Unique identifier for the consensus process
            proposal: Optional proposal description
            domain: Optional domain for expertise weighting
        """
        # Call base implementation
        super().start_consensus(consensus_id)

        # Initialize enhanced structures
        self.enhanced_votes[consensus_id] = []
        self.reasoning_chains[consensus_id] = []
        self.agent_accuracy_history[consensus_id] = {}

        # Create decision provenance
        self.decision_provenance[consensus_id] = DecisionProvenance(
            decision_id=consensus_id,
            proposal=proposal or consensus_id,
            start_time=datetime.now(UTC).isoformat(),
        )

        # Store domain for expertise weighting
        if domain:
            self.decision_provenance[consensus_id].participating_agents.append(f"_domain:{domain}")

        # Create rollback checkpoint if enabled
        if self.enable_rollback:
            self.rollback_checkpoints[consensus_id] = {
                "state": "initiated",
                "timestamp": datetime.now(UTC).isoformat(),
                "votes": [],
                "reasoning_chains": [],
                "domain": domain,
            }

        logger.info(
            f"Enhanced consensus started: {consensus_id} "  # noqa: G004
            f"(proposal: {proposal or 'none'}, domain: {domain or 'general'})"
        )

    def add_vote(
        self,
        consensus_id: str,
        agent_id: str,
        decision: str,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a vote to a consensus process (base implementation).

        Args:
            consensus_id: Consensus process identifier
            agent_id: Agent submitting the vote
            decision: Agent's decision
            confidence: Confidence level (0.0 to 1.0)
            metadata: Optional metadata
        """
        # Call base implementation
        super().add_vote(consensus_id, agent_id, decision, confidence, metadata)

        # Update provenance
        if consensus_id in self.decision_provenance:
            self.decision_provenance[consensus_id].participating_agents = list(
                {*self.decision_provenance[consensus_id].participating_agents, agent_id}
            )
            self.decision_provenance[consensus_id].votes_cast += 1

    def add_vote_with_reasoning(
        self,
        consensus_id: str,
        agent_id: str,
        decision: str,
        confidence: float,
        reasoning_chain: list[dict[str, Any]],
        pattern_references: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Add a vote with full reasoning chain.

        Args:
            consensus_id: Consensus process identifier
            agent_id: Agent submitting the vote
            decision: Agent's decision
            confidence: Confidence level (0.0 to 1.0)
            reasoning_chain: List of reasoning steps
            pattern_references: Optional pattern library references
            metadata: Optional metadata

        Returns:
            Chain ID if successful, None otherwise
        """
        # Create base vote
        vote = Vote(
            agent_id=agent_id,
            decision=decision,
            confidence=confidence,
            timestamp=datetime.now(UTC).isoformat(),
            metadata=metadata or {},
        )

        # Build reasoning chain
        chain = ReasoningChain(
            chain_id=f"chain-{consensus_id}-{agent_id}", agent_id=agent_id, steps=[]
        )

        for step_data in reasoning_chain:
            chain.add_step(
                step_type=step_data.get("type", "inference"),
                content=step_data.get("content", ""),
                confidence=step_data.get("confidence", 0.5),
                sources=step_data.get("sources", []),
            )

        # Validate the chain
        chain.validate_chain()

        # Create enhanced vote
        enhanced_vote = EnhancedVote(
            vote=vote,
            reasoning_chain=chain,
            pattern_references=pattern_references or [],
        )

        # Store enhanced vote
        if consensus_id in self.enhanced_votes:
            self.enhanced_votes[consensus_id].append(enhanced_vote)
            self.reasoning_chains[consensus_id].append(chain)

            # Update provenance
            if pattern_references:
                self.decision_provenance[consensus_id].patterns_used.extend(pattern_references)
            self.decision_provenance[consensus_id].reasoning_chains.append(chain)

            # Update rollback checkpoint
            if self.enable_rollback and consensus_id in self.rollback_checkpoints:
                self.rollback_checkpoints[consensus_id]["votes"].append(
                    {
                        "agent_id": agent_id,
                        "decision": decision,
                        "confidence": confidence,
                        "chain_id": chain.chain_id,
                    }
                )

            logger.info(
                f"Vote with reasoning added: {agent_id} -> {decision} "  # noqa: G004
                f"(chain: {chain.chain_id}, status: {chain.status.value})"
            )

            return chain.chain_id

        return None

    def calculate_vote_weight(
        self,
        consensus_id: str,
        enhanced_vote: EnhancedVote,
        domain: str | None = None,
    ) -> float:
        """
        Calculate vote weight based on evidence quality, expertise, confidence, and historical accuracy.  # noqa: E501

        This is the core weighting method that was previously returning constant 1.0.

        Args:
            consensus_id: Consensus process identifier
            enhanced_vote: Enhanced vote to weight
            domain: Optional domain for expertise weighting

        Returns:
            Vote weight (0.0 to 2.0, where 1.0 is baseline)
        """
        agent_id = enhanced_vote.agent_id

        # 1. Evidence Quality Score (35% weight)
        evidence_score = self._calculate_evidence_quality_score(enhanced_vote)

        # 2. Agent Expertise Score (30% weight)
        expertise_score = self._calculate_expertise_score(agent_id, domain)

        # 3. Confidence Score (20% weight)
        confidence_score = enhanced_vote.confidence

        # 4. Historical Accuracy Score (15% weight)
        historical_score = self._calculate_historical_accuracy_score(consensus_id, agent_id)

        # Calculate weighted combination
        weighted_score = (
            evidence_score * EVIDENCE_QUALITY_WEIGHT
            + expertise_score * EXPERTISE_WEIGHT
            + confidence_score * CONFIDENCE_WEIGHT
            + historical_score * HISTORICAL_WEIGHT
        )

        # Apply expertise multiplier from profiler
        if domain and self.expertise_profiler:
            domain_expertise = self.expertise_profiler.get_expertise_for_domain(agent_id, domain)
            if domain_expertise:
                expertise_multiplier = domain_expertise.get_expertise_multiplier()
                # Scale multiplier to have moderate effect (0.8 to 1.2 range)
                scaled_multiplier = 0.8 + (expertise_multiplier - 0.5) * 0.4
                weighted_score *= scaled_multiplier

        # Normalize to 0.0-2.0 range (1.0 is baseline)
        vote_weight = max(0.0, min(2.0, weighted_score * 2.0))

        # Cache the weight
        enhanced_vote.vote_weight = vote_weight

        logger.debug(
            f"Vote weight calculated for {agent_id}: "  # noqa: G004
            f"evidence={evidence_score:.2f}, expertise={expertise_score:.2f}, "
            f"confidence={confidence_score:.2f}, historical={historical_score:.2f} "
            f"-> weight={vote_weight:.2f}"
        )

        return vote_weight

    def _apply_enhanced_vote_weights(
        self,
        votes: list[Vote],
        consensus_id: str,
    ) -> list[tuple[str, float]]:
        """
        Apply enhanced vote weights using evidence quality, expertise, confidence, and historical accuracy.  # noqa: E501

        This method overrides the base implementation to use the enhanced weighting system.

        Args:
            votes: List of base votes
            consensus_id: Consensus process identifier

        Returns:
            List of (decision, weight) tuples
        """
        weighted = []

        # Get domain for expertise weighting
        domain = None
        if consensus_id in self.decision_provenance:
            domain_agents = [
                a
                for a in self.decision_provenance[consensus_id].participating_agents
                if a.startswith("_domain:")
            ]
            if domain_agents:
                domain = domain_agents[0].replace("_domain:", "")

        # Find matching enhanced votes and apply weights
        for vote in votes:
            # Look for matching enhanced vote
            enhanced_vote = None
            if consensus_id in self.enhanced_votes:
                for ev in self.enhanced_votes[consensus_id]:
                    if ev.vote.agent_id == vote.agent_id and ev.vote.decision == vote.decision:
                        enhanced_vote = ev
                        break

            if enhanced_vote:
                # Use pre-calculated vote weight
                weight = enhanced_vote.vote_weight
            else:
                # Create temporary enhanced vote for weighting
                temp_enhanced = EnhancedVote(vote=vote)
                weight = self.calculate_vote_weight(consensus_id, temp_enhanced, domain)

            weighted.append((vote.decision, weight))

        return weighted

    def _calculate_evidence_quality_score(self, enhanced_vote: EnhancedVote) -> float:
        """
        Calculate evidence quality score from reasoning chain.

        Args:
            enhanced_vote: Enhanced vote with reasoning chain

        Returns:
            Evidence quality score (0.0 to 1.0)
        """
        if enhanced_vote.evidence_quality:
            return enhanced_vote.evidence_quality.calculate_quality_score()

        # Extract evidence quality from reasoning chain
        reasoning_chain = enhanced_vote.reasoning_chain
        if not reasoning_chain:
            return 0.5  # Default for no evidence

        # Count sources from reasoning steps
        total_sources = sum(len(step.sources) for step in reasoning_chain.steps)

        # Calculate source reliability based on validation status
        reliability_map = {
            ReasoningChainStatus.VALID: 0.9,
            ReasoningChainStatus.INCOMPLETE: 0.5,
            ReasoningChainStatus.INVALID: 0.2,
            ReasoningChainStatus.CIRCULAR: 0.1,
            ReasoningChainStatus.UNVERIFIED: 0.5,
        }
        source_reliability = reliability_map.get(reasoning_chain.status, 0.5)

        # Calculate completeness based on step types present
        step_types = {step.step_type for step in reasoning_chain.steps}
        required_types = {"observation", "inference", "conclusion"}
        completeness = len(step_types & required_types) / len(required_types)

        # Calculate consistency based on confidence variance
        confidences = [step.confidence for step in reasoning_chain.steps]
        if len(confidences) > 1:
            confidence_variance = statistics.variance(confidences)
            consistency = max(0.0, 1.0 - confidence_variance)
        else:
            consistency = 0.7  # Default for single step

        # Recency based on chain creation time
        try:
            created_at = datetime.fromisoformat(reasoning_chain.created_at.replace("Z", "+00:00"))
            age_hours = (datetime.now(UTC) - created_at).total_seconds() / 3600
            # Decay over 24 hours
            recency_score = max(0.0, 1.0 - (age_hours / 24.0))
        except (ValueError, TypeError):
            recency_score = 0.5

        # Create and cache evidence quality
        evidence_quality = EvidenceQuality(
            source_count=total_sources,
            source_reliability=source_reliability,
            completeness=completeness,
            consistency=consistency,
            recency_score=recency_score,
        )
        enhanced_vote.evidence_quality = evidence_quality

        return evidence_quality.calculate_quality_score()

    def _calculate_expertise_score(self, agent_id: str, domain: str | None = None) -> float:
        """
        Calculate agent expertise score.

        Args:
            agent_id: Agent identifier
            domain: Optional domain for expertise

        Returns:
            Expertise score (0.0 to 1.0)
        """
        if not self.expertise_profiler:
            return 0.5  # Default if no profiler

        if domain:
            return self.expertise_profiler.get_expertise_score(agent_id, domain)
        return self.expertise_profiler.get_expertise_score(agent_id)

    def _calculate_historical_accuracy_score(self, consensus_id: str, agent_id: str) -> float:
        """
        Calculate historical accuracy score for an agent.

        Args:
            consensus_id: Consensus process identifier
            agent_id: Agent identifier

        Returns:
            Historical accuracy score (0.0 to 1.0)
        """
        # Check if we have accuracy history for this agent
        if (
            consensus_id in self.agent_accuracy_history
            and agent_id in self.agent_accuracy_history[consensus_id]
        ):
            outcomes = self.agent_accuracy_history[consensus_id][agent_id]
            if outcomes:
                return sum(outcomes) / len(outcomes)

        # Fall back to expertise profiler's historical data
        if self.expertise_profiler:
            profile = self.expertise_profiler.get_profile(agent_id)
            if profile:
                # Use overall reputation as proxy for historical accuracy
                return profile.overall_reputation

        return 0.5  # Default for unknown agents

    def record_decision_outcome(
        self,
        consensus_id: str,
        agent_id: str,
        was_correct: bool,
    ) -> None:
        """
        Record the outcome of a decision for historical accuracy tracking.

        Args:
            consensus_id: Consensus process identifier
            agent_id: Agent identifier
            was_correct: Whether the agent's vote was correct
        """
        if consensus_id not in self.agent_accuracy_history:
            self.agent_accuracy_history[consensus_id] = {}

        if agent_id not in self.agent_accuracy_history[consensus_id]:
            self.agent_accuracy_history[consensus_id][agent_id] = []

        self.agent_accuracy_history[consensus_id][agent_id].append(was_correct)

        # Also record in expertise profiler
        domain = None
        if consensus_id in self.decision_provenance:
            domain_agents = [
                a
                for a in self.decision_provenance[consensus_id].participating_agents
                if a.startswith("_domain:")
            ]
            if domain_agents:
                domain = domain_agents[0].replace("_domain:", "")

        if domain and self.expertise_profiler:
            self.expertise_profiler.record_outcome(
                agent_id=agent_id,
                domain=domain,
                was_correct=was_correct,
                confidence=0.5,  # Placeholder
            )

        logger.debug("Recorded decision outcome for {agent_id}: correct={was_correct}")

    def compute_consensus(
        self,
        consensus_id: str,
    ) -> ConsensusResult | None:
        """
        Compute consensus with enhanced validation.

        Args:
            consensus_id: Consensus process identifier

        Returns:
            Consensus result or None
        """
        # Perform cross-validation if enabled
        if self.enable_cross_validation:
            self._cross_validate_reasoning(consensus_id)

        # Call base implementation
        result = super().compute_consensus(consensus_id)

        if result:
            # Update provenance
            if consensus_id in self.decision_provenance:
                self.decision_provenance[consensus_id].end_time = datetime.now(UTC).isoformat()
                self.decision_provenance[
                    consensus_id
                ].validation_results = self._get_validation_results(consensus_id)
                self.decision_provenance[consensus_id].rollback_available = self.enable_rollback
                if self.enable_rollback:
                    self.decision_provenance[
                        consensus_id
                    ].rollback_checkpoint = self.rollback_checkpoints.get(consensus_id)

            # Update rollback checkpoint state
            if self.enable_rollback and consensus_id in self.rollback_checkpoints:
                self.rollback_checkpoints[consensus_id]["state"] = "completed"
                self.rollback_checkpoints[consensus_id]["result"] = {
                    "decision": result.decision,
                    "confidence": result.confidence,
                }

            # Emit consensus result event (fire-and-forget)
            import asyncio

            asyncio.create_task(_emit_consensus_result(result, consensus_id))  # noqa: RUF006

        return result

    def compute_consensus_with_validation(
        self,
        consensus_id: str,
        min_validation_score: float = 0.6,
    ) -> ConsensusResult | None:
        """
        Compute consensus with validation score threshold.

        Args:
            consensus_id: Consensus process identifier
            min_validation_score: Minimum validation score required

        Returns:
            Consensus result or None if validation fails
        """
        # Perform cross-validation
        self._cross_validate_reasoning(consensus_id)

        # Check if validation passes threshold
        avg_validation_score = (
            statistics.mean(
                v.validation_score
                for v in self.enhanced_votes.get(consensus_id, [])
                if v.cross_validated
            )
            if self.enhanced_votes.get(consensus_id)
            else 0.0
        )

        if avg_validation_score < min_validation_score:
            logger.warning(
                f"Validation score {avg_validation_score:.2f} below threshold "  # noqa: G004
                f"{min_validation_score:.2f} for {consensus_id}"
            )
            self.process_states[consensus_id] = ConsensusState.FAILED
            return None

        # Compute consensus
        return self.compute_consensus(consensus_id)

    def _cross_validate_reasoning(
        self,
        consensus_id: str,
    ) -> dict[str, Any]:
        """
        Cross-validate reasoning chains across all votes.

        Args:
            consensus_id: Consensus process identifier

        Returns:
            Validation results dictionary
        """
        if not self.enable_cross_validation:
            return {"status": "disabled"}

        enhanced_votes = self.enhanced_votes.get(consensus_id, [])
        chains = self.reasoning_chains.get(consensus_id, [])

        validation_results = {
            "total_chains": len(chains),
            "valid_chains": 0,
            "invalid_chains": 0,
            "cross_validations": [],
        }

        # Count valid/invalid chains
        for chain in chains:
            if chain.status == ReasoningChainStatus.VALID:
                validation_results["valid_chains"] += 1
            else:
                validation_results["invalid_chains"] += 1

        # Check for contradictory patterns between chains
        validation_results["cross_validations"] = self._check_chain_contradictions(
            chains, enhanced_votes
        )

        # Calculate validation scores and vote weights
        domain = self._extract_domain(consensus_id)
        self._calculate_validation_scores(enhanced_votes, domain, consensus_id)

        validation_results["average_validation_score"] = (
            statistics.mean(ev.validation_score for ev in enhanced_votes if ev.cross_validated)
            if enhanced_votes
            else 0.0
        )

        # Store validation results in provenance
        if consensus_id in self.decision_provenance:
            self.decision_provenance[consensus_id].validation_results = validation_results

        logger.info(
            f"Cross-validation complete for {consensus_id}: "  # noqa: G004
            f"{validation_results['valid_chains']}/{validation_results['total_chains']} "
            f"valid chains"
        )

        return validation_results

    @staticmethod
    def _build_contradiction_entry(
        chain1: ReasoningChain, chain2: ReasoningChain, common_patterns: set[str]
    ) -> dict[str, Any]:
        """Build a contradiction entry for cross-validation."""
        return {
            "chain1": chain1.chain_id,
            "chain2": chain2.chain_id,
            "issue": "contradictory_conclusions",
            "shared_patterns": list(common_patterns),
        }

    def _check_chain_contradictions(
        self,
        chains: list[ReasoningChain],
        enhanced_votes: list[EnhancedVote],
    ) -> list[dict[str, Any]]:
        """
        Check for contradictory reasoning between chains.

        Args:
            chains: List of reasoning chains
            enhanced_votes: List of enhanced votes

        Returns:
            List of cross-validation issues found
        """
        contradictions: list[dict[str, Any]] = []

        if not self.enable_pattern_library:
            return contradictions

        # Build decisions map
        decisions_by_chain: dict[str, str] = {}
        for ev in enhanced_votes:
            if ev.reasoning_chain:
                decisions_by_chain[ev.reasoning_chain.chain_id] = ev.decision

        # Check for contradictory reasoning supporting same decision
        for i, chain1 in enumerate(chains):
            for chain2 in chains[i + 1:]:
                if chain1.status != ReasoningChainStatus.VALID:
                    continue
                if chain2.status != ReasoningChainStatus.VALID:
                    continue
                common_patterns = set(chain1.pattern_references) & set(chain2.pattern_references)
                if not common_patterns:
                    continue
                decision1 = decisions_by_chain.get(chain1.chain_id)
                decision2 = decisions_by_chain.get(chain2.chain_id)
                if decision1 != decision2:
                    contradictions.append(
                        self._build_contradiction_entry(chain1, chain2, common_patterns)
                    )

        return contradictions

    def _calculate_validation_scores(
        self,
        enhanced_votes: list[EnhancedVote],
        domain: str | None,
        consensus_id: str,
    ) -> None:
        """
        Calculate validation scores for enhanced votes.

        Args:
            enhanced_votes: List of enhanced votes
            domain: Domain for expertise weighting
            consensus_id: Consensus process identifier
        """
        for ev in enhanced_votes:
            if ev.reasoning_chain:
                if ev.reasoning_chain.status == ReasoningChainStatus.VALID:
                    ev.validation_score = 0.8 + (0.2 * ev.confidence)
                else:
                    ev.validation_score = 0.3
                ev.cross_validated = True

            # Calculate vote weight using the new weighting system
            self.calculate_vote_weight(consensus_id, ev, domain)

    def _extract_domain(self, consensus_id: str) -> str | None:
        """
        Extract domain from decision provenance.

        Args:
            consensus_id: Consensus process identifier

        Returns:
            Domain string or None
        """
        if consensus_id not in self.decision_provenance:
            return None

        domain_agents = [
            a
            for a in self.decision_provenance[consensus_id].participating_agents
            if a.startswith("_domain:")
        ]
        if domain_agents:
            return domain_agents[0].replace("_domain:", "")
        return None

    def _get_validation_results(
        self,
        consensus_id: str,
    ) -> dict[str, Any]:
        """
        Get validation results for a consensus.

        Args:
            consensus_id: Consensus identifier

        Returns:
            Validation results dictionary
        """
        if consensus_id in self.decision_provenance:
            return self.decision_provenance[consensus_id].validation_results
        return {}

    def get_decision_provenance(
        self,
        consensus_id: str,
    ) -> DecisionProvenance | None:
        """
        Get complete provenance for a decision.

        Args:
            consensus_id: Consensus identifier

        Returns:
            Decision provenance or None
        """
        return self.decision_provenance.get(consensus_id)

    def get_reasoning_chains(
        self,
        consensus_id: str,
    ) -> list[ReasoningChain]:
        """
        Get all reasoning chains for a consensus.

        Args:
            consensus_id: Consensus identifier

        Returns:
            List of reasoning chains
        """
        return self.reasoning_chains.get(consensus_id, [])

    def rollback_decision(
        self,
        consensus_id: str,
        reason: str | None = None,
    ) -> RollbackResult:
        """
        Rollback a decision to its pre-consensus state.

        Args:
            consensus_id: Consensus identifier
            reason: Optional reason for rollback

        Returns:
            Rollback result
        """
        if not self.enable_rollback:
            return RollbackResult(
                success=False,
                message="Rollback is not enabled",
            )

        if consensus_id not in self.rollback_checkpoints:
            return RollbackResult(
                success=False,
                message=f"No rollback checkpoint found for {consensus_id}",
            )

        checkpoint = self.rollback_checkpoints[consensus_id]

        if checkpoint.get("state") != "completed":
            return RollbackResult(
                success=False,
                message=f"Decision not in completed state: {checkpoint.get('state')}",
            )

        # Perform rollback
        try:
            # Clear votes and reset state
            if consensus_id in self.active_processes:
                self.active_processes[consensus_id] = []
            if consensus_id in self.process_states:
                self.process_states[consensus_id] = ConsensusState.GATHERING

            # Update provenance
            if consensus_id in self.decision_provenance:
                self.decision_provenance[consensus_id].rollback_available = False

            # Clear checkpoint
            del self.rollback_checkpoints[consensus_id]

            logger.info("Rollback completed for {consensus_id}: {reason or 'no reason provided'}")

            return RollbackResult(
                success=True,
                message=f"Decision rolled back: {reason or 'no reason provided'}",
                previous_state=checkpoint,
            )

        except Exception as e:
            logger.error("Rollback failed: {e}")
            return RollbackResult(
                success=False,
                message=f"Rollback failed: {e!s}",
            )

    def export_provenance(
        self,
        consensus_id: str,
    ) -> dict[str, Any] | None:
        """
        Export decision provenance for external audit.

        Args:
            consensus_id: Consensus identifier

        Returns:
            Serializable provenance dictionary or None
        """
        provenance = self.decision_provenance.get(consensus_id)
        if not provenance:
            return None

        return {
            "decision_id": provenance.decision_id,
            "proposal": provenance.proposal,
            "start_time": provenance.start_time,
            "end_time": provenance.end_time,
            "participating_agents": provenance.participating_agents,
            "votes_cast": provenance.votes_cast,
            "reasoning_chains": [
                {
                    "chain_id": chain.chain_id,
                    "agent_id": chain.agent_id,
                    "status": chain.status.value,
                    "steps": [
                        {
                            "step_number": step.step_number,
                            "step_type": step.step_type,
                            "content": step.content,
                            "confidence": step.confidence,
                        }
                        for step in chain.steps
                    ],
                    "validation_errors": chain.validation_errors,
                }
                for chain in provenance.reasoning_chains
            ],
            "patterns_used": provenance.patterns_used,
            "validation_results": provenance.validation_results,
            "rollback_available": provenance.rollback_available,
        }

    def get_enhanced_statistics(self) -> dict[str, Any]:
        """
        Get enhanced consensus statistics.

        Returns:
            Statistics dictionary
        """
        base_stats = self.get_statistics()

        total_chains = sum(len(chains) for chains in self.reasoning_chains.values())
        valid_chains = sum(
            sum(1 for c in chains if c.status == ReasoningChainStatus.VALID)
            for chains in self.reasoning_chains.values()
        )

        return {
            **base_stats,
            "total_reasoning_chains": total_chains,
            "valid_reasoning_chains": valid_chains,
            "chain_validity_rate": (valid_chains / total_chains if total_chains > 0 else 0.0),
            "provenance_tracked": len(self.decision_provenance),
            "rollbacks_available": sum(
                1 for p in self.decision_provenance.values() if p.rollback_available
            ),
        }

    def register_pattern(
        self,
        pattern_id: str,
        pattern_data: dict[str, Any],
    ) -> None:
        """
        Register a pattern in the pattern library.

        Args:
            pattern_id: Pattern identifier
            pattern_data: Pattern data
        """
        self.pattern_library[pattern_id] = pattern_data
        logger.debug("Registered pattern: {pattern_id}")

    def get_pattern(
        self,
        pattern_id: str,
    ) -> dict[str, Any] | None:
        """
        Get pattern from the pattern library.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Pattern data or None
        """
        return self.pattern_library.get(pattern_id)

    def generate_decision_hash(
        self,
        consensus_id: str,
    ) -> str | None:
        """
        Generate cryptographic hash of decision for integrity verification.

        Args:
            consensus_id: Consensus identifier

        Returns:
            SHA-256 hash or None
        """
        provenance = self.decision_provenance.get(consensus_id)
        if not provenance or not provenance.end_time:
            return None

        # Create hashable data
        data = {
            "decision_id": provenance.decision_id,
            "proposal": provenance.proposal,
            "start_time": provenance.start_time,
            "end_time": provenance.end_time,
            "participating_agents": sorted(provenance.participating_agents),
            "votes_cast": provenance.votes_cast,
        }

        # Generate hash
        data_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_json.encode()).hexdigest()

    def export_accuracy_history(self) -> dict[str, Any]:
        """
        Export accuracy history for persistence.

        Returns:
            Serializable dictionary of accuracy history
        """
        return {
            "agent_accuracy_history": self.agent_accuracy_history,
            "evidence_cache": {
                key: {
                    "source_count": eq.source_count,
                    "source_reliability": eq.source_reliability,
                    "completeness": eq.completeness,
                    "consistency": eq.consistency,
                    "recency_score": eq.recency_score,
                }
                for key, eq in self.evidence_cache.items()
            },
        }

    def import_accuracy_history(self, data: dict[str, Any]) -> None:
        """
        Import accuracy history from persisted data.

        Args:
            data: Dictionary containing exported accuracy history
        """
        if "agent_accuracy_history" in data:
            self.agent_accuracy_history = data["agent_accuracy_history"]

        if "evidence_cache" in data:
            for key, eq_data in data["evidence_cache"].items():
                self.evidence_cache[key] = EvidenceQuality(
                    source_count=eq_data.get("source_count", 0),
                    source_reliability=eq_data.get("source_reliability", 0.5),
                    completeness=eq_data.get("completeness", 0.5),
                    consistency=eq_data.get("consistency", 0.5),
                    recency_score=eq_data.get("recency_score", 0.5),
                )

        logger.info("Imported accuracy history")

    def save_state(self, filepath: str) -> None:
        """
        Save complete consensus state to a JSON file.

        Args:
            filepath: Path to save file
        """
        state = {
            "expertise_profiler": self.expertise_profiler.export_profiles(),
            "accuracy_history": self.export_accuracy_history(),
            "decision_provenance": {
                cid: self.export_provenance(cid) for cid in self.decision_provenance
            },
        }
        with open(filepath, "w") as f:  # noqa: PTH123
            json.dump(state, f, indent=2)
        logger.info("Saved consensus state to {filepath}")

    def load_state(self, filepath: str) -> None:
        """
        Load complete consensus state from a JSON file.

        Args:
            filepath: Path to load file
        """
        with open(filepath) as f:  # noqa: PTH123
            state = json.load(f)

        if "expertise_profiler" in state:
            self.expertise_profiler.import_profiles(state["expertise_profiler"])

        if "accuracy_history" in state:
            self.import_accuracy_history(state["accuracy_history"])

        if "decision_provenance" in state:
            # Note: Provenance is read-only after loading
            logger.info("Loaded {len(state['decision_provenance'])} provenance records")

        logger.info("Loaded consensus state from {filepath}")
