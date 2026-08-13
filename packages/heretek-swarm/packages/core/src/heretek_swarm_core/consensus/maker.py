"""
MAKER Consensus - Multi-Agent Knowledge Extraction & Reasoning.

This module implements the MAKER consensus mechanism for decision aggregation:
- First-to-ahead-by-k voting
- Red-flagging on anomalous outputs
- Reputation-weighted voting
- Decision aggregation
"""

import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("MAKERConsensus")


class ConsensusState(Enum):
    """Consensus process states."""

    GATHERING = "gathering"
    VOTING = "voting"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Vote:
    """
    A single vote from an agent.

    Attributes:
        agent_id: Agent identifier
        decision: Agent's decision
        confidence: Confidence level (0.0 to 1.0)
        timestamp: Vote timestamp
        metadata: Additional metadata
    """

    agent_id: str
    decision: str
    confidence: float
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    """
    Result of a consensus process.

    Attributes:
        decision: Final decision
        confidence: Overall confidence
        votes: All votes cast
        state: Consensus state
        timestamp: Result timestamp
        red_flags: List of red flag messages
        metadata: Additional metadata
    """

    decision: str
    confidence: float
    votes: list[Vote]
    state: ConsensusState
    timestamp: str
    red_flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class MAKERConsensus:
    """
    MAKER consensus mechanism implementation.

    The MAKER (Multi-Agent Knowledge Extraction & Reasoning) consensus
    provides robust decision aggregation with:
    - First-to-ahead-by-k voting mechanism
    - Red-flagging for anomalous outputs
    - Reputation-weighted voting
    - Statistical validation

    Example:
        ```python
        consensus = MAKERConsensus(ahead_by_k=2, min_votes=3)

        # Start consensus process
        consensus.start_consensus("decision-1")

        # Add votes
        consensus.add_vote("decision-1", "agent-1", "A", 0.9)
        consensus.add_vote("decision-1", "agent-2", "A", 0.85)
        consensus.add_vote("decision-1", "agent-3", "B", 0.7)

        # Compute result
        result = consensus.compute_consensus("decision-1")
        logger.info("maker_decision_made", decision=result.decision, confidence=result.confidence)
        ```
    """

    def __init__(
        self,
        ahead_by_k: int = 2,
        min_votes: int = 3,
        confidence_threshold: float = 0.6,
        reputation_weights: dict[str, float] | None = None,
    ) -> None:
        """
        Initialize the consensus engine.

        Args:
            ahead_by_k: Number of votes needed to be ahead to win
            min_votes: Minimum number of votes required
            confidence_threshold: Minimum confidence threshold
            reputation_weights: Optional reputation weights per agent
        """
        self.ahead_by_k = ahead_by_k
        self.min_votes = min_votes
        self.confidence_threshold = confidence_threshold
        self.reputation_weights = reputation_weights or {}

        # Active consensus processes
        self.active_processes: dict[str, list[Vote]] = {}
        self.process_states: dict[str, ConsensusState] = {}

        # Agent reputation tracking
        self.agent_reputation: dict[str, float] = {}
        self.agent_vote_history: dict[str, list[Vote]] = {}

        logger.info(
            f"MAKER Consensus initialized with ahead_by_k={ahead_by_k}, min_votes={min_votes}",
        )

    def start_consensus(self, consensus_id: str) -> None:
        """
        Start a new consensus process.

        Args:
            consensus_id: Unique identifier for the consensus process
        """
        self.active_processes[consensus_id] = []
        self.process_states[consensus_id] = ConsensusState.GATHERING
        logger.info("Started consensus process {consensus_id}")

    def add_vote(
        self,
        consensus_id: str,
        agent_id: str,
        decision: str,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a vote to a consensus process.

        Args:
            consensus_id: Consensus process identifier
            agent_id: Agent submitting the vote
            decision: Agent's decision
            confidence: Confidence level (0.0 to 1.0)
            metadata: Optional metadata
        """
        if consensus_id not in self.active_processes:
            logger.warning("Unknown consensus ID: {consensus_id}")
            return

        vote = Vote(
            agent_id=agent_id,
            decision=decision,
            confidence=confidence,
            timestamp=datetime.now(UTC).isoformat(),
            metadata=metadata or {},
        )

        self.active_processes[consensus_id].append(vote)

        # Track vote history
        if agent_id not in self.agent_vote_history:
            self.agent_vote_history[agent_id] = []
        self.agent_vote_history[agent_id].append(vote)

        logger.debug(
            f"Vote added from {agent_id}: {decision} (confidence: {confidence})",
        )

    def compute_consensus(
        self,
        consensus_id: str,
    ) -> ConsensusResult | None:
        """
        Compute consensus from collected votes.

        Args:
            consensus_id: Consensus process identifier

        Returns:
            Consensus result or None if not enough votes
        """
        if consensus_id not in self.active_processes:
            logger.warning("Unknown consensus ID: {consensus_id}")
            return None

        votes = self.active_processes[consensus_id]

        if len(votes) < self.min_votes:
            logger.info("Not enough votes: {len(votes)}/{self.min_votes}")
            return None

        self.process_states[consensus_id] = ConsensusState.AGGREGATING

        # Check for red flags
        red_flags = self._check_red_flags(votes)

        # Compute weighted votes - use enhanced weighting if available
        weighted_votes = self._apply_enhanced_vote_weights(votes, consensus_id)

        # First-to-ahead-by-k voting
        result = self._first_to_ahead_by_k(
            consensus_id,
            weighted_votes,
            red_flags,
        )

        if result:
            self.process_states[consensus_id] = ConsensusState.COMPLETED
            logger.info(
                f"Consensus reached for {consensus_id}: "
                f"{result.decision} (confidence: {result.confidence:.2f})",
            )
        else:
            self.process_states[consensus_id] = ConsensusState.FAILED
            logger.warning("Failed to reach consensus for {consensus_id}")

        return result

    def _first_to_ahead_by_k(
        self,
        consensus_id: str,
        votes: list[tuple[str, float]],
        red_flags: list[str],
    ) -> ConsensusResult | None:
        """
        First-to-ahead-by-k voting mechanism.

        Args:
            consensus_id: Consensus process identifier
            votes: List of (decision, weight) tuples
            red_flags: List of red flag messages

        Returns:
            Consensus result or None
        """
        # Count votes per decision
        vote_counts: dict[str, float] = {}
        vote_details: dict[str, list[tuple[str, float]]] = {}

        for decision, weight in votes:
            if decision not in vote_counts:
                vote_counts[decision] = 0.0
                vote_details[decision] = []
            vote_counts[decision] += weight
            vote_details[decision].append((decision, weight))

        # Sort decisions by vote count
        sorted_decisions = sorted(
            vote_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        if len(sorted_decisions) < 1:
            return None

        first_decision, first_count = sorted_decisions[0]

        # Unanimous case: only one option means everyone agrees — strongest consensus
        if len(sorted_decisions) >= 2:
            second_count = sorted_decisions[1][1]
            if first_count - second_count < self.ahead_by_k:
                return None

        total_votes = sum(vote_counts.values())
        confidence = first_count / total_votes if total_votes > 0 else 0.0

        original_votes = [
            v for v in self.active_processes.get(consensus_id, []) if v.decision == first_decision
        ]

        return ConsensusResult(
            decision=first_decision,
            confidence=confidence,
            votes=original_votes,
            state=ConsensusState.COMPLETED,
            timestamp=datetime.now(UTC).isoformat(),
            red_flags=red_flags,
        )

    def _check_red_flags(self, votes: list[Vote]) -> list[str]:
        """
        Check for red flags in votes.

        Args:
            votes: List of votes to check

        Returns:
            List of red flag messages
        """
        red_flags = []

        # Check for outlier confidence values
        confidences = [v.confidence for v in votes]
        if confidences:
            mean_confidence = statistics.mean(confidences)
            std_confidence = statistics.stdev(confidences) if len(confidences) > 1 else 0

            for vote in votes:
                if std_confidence > 0:
                    z_score = abs(vote.confidence - mean_confidence) / std_confidence
                    if z_score > 2.0:  # More than 2 standard deviations
                        red_flags.append(
                            f"Outlier confidence from {vote.agent_id}: "
                            f"{vote.confidence:.2f} (z-score: {z_score:.2f})"
                        )

        # Check for low reputation agents
        for vote in votes:
            reputation = self.agent_reputation.get(vote.agent_id, 0.5)
            if reputation < 0.3:
                red_flags.append(
                    f"Low reputation agent {vote.agent_id} participating "
                    f"(reputation: {reputation:.2f})"
                )

        # Check for unanimous disagreement
        if len(votes) >= 3:
            decisions = [v.decision for v in votes]
            unique_decisions = set(decisions)
            if len(unique_decisions) == len(votes):
                red_flags.append("Complete disagreement among agents - no consensus possible")

        if red_flags:
            logger.warning("Red flags detected: {red_flags}")

        return red_flags

    def _apply_reputation_weights(
        self,
        votes: list[Vote],
    ) -> list[tuple[str, float]]:
        """
        Apply reputation weights to votes.

        Args:
            votes: List of votes

        Returns:
            List of (decision, weight) tuples
        """
        weighted = []

        for vote in votes:
            # Get reputation weight
            reputation = self.reputation_weights.get(
                vote.agent_id,
                self.agent_reputation.get(vote.agent_id, 0.5),
            )

            # Calculate weighted vote
            weight = vote.confidence * reputation
            weighted.append((vote.decision, weight))

        return weighted

    def _apply_enhanced_vote_weights(
        self,
        votes: list[Vote],
        consensus_id: str,
    ) -> list[tuple[str, float]]:
        """
        Apply enhanced vote weights using evidence quality, expertise, confidence, and historical accuracy.  # noqa: E501

        This method is designed to be called by EnhancedMAKERConsensus which overrides
        the vote weighting logic. The base implementation falls back to reputation weighting.

        Args:
            votes: List of votes
            consensus_id: Consensus process identifier

        Returns:
            List of (decision, weight) tuples
        """
        # Base implementation falls back to reputation weighting
        # EnhancedMAKERConsensus overrides this method
        return self._apply_reputation_weights(votes)

    def update_reputation(
        self,
        agent_id: str,
        delta: float,
        min_reputation: float = 0.0,
        max_reputation: float = 1.0,
    ) -> None:
        """
        Update an agent's reputation.

        Args:
            agent_id: Agent identifier
            delta: Reputation change (can be positive or negative)
            min_reputation: Minimum reputation value
            max_reputation: Maximum reputation value
        """
        current = self.agent_reputation.get(agent_id, 0.5)
        new_reputation = max(min_reputation, min(max_reputation, current + delta))
        self.agent_reputation[agent_id] = new_reputation

        logger.info("Updated reputation for {agent_id}: {current:.2f} -> {new_reputation:.2f}")

    def get_agent_reputation(self, agent_id: str) -> float:
        """
        Get an agent's reputation.

        Args:
            agent_id: Agent identifier

        Returns:
            Reputation value
        """
        return self.agent_reputation.get(agent_id, 0.5)

    def get_process_state(self, consensus_id: str) -> ConsensusState | None:
        """
        Get the state of a consensus process.

        Args:
            consensus_id: Consensus process identifier

        Returns:
            Process state or None
        """
        return self.process_states.get(consensus_id)

    def cleanup_process(self, consensus_id: str) -> None:
        """
        Clean up a completed consensus process.

        Args:
            consensus_id: Consensus process identifier
        """
        if consensus_id in self.active_processes:
            del self.active_processes[consensus_id]
        if consensus_id in self.process_states:
            del self.process_states[consensus_id]
        logger.debug("Cleaned up process {consensus_id}")

    async def run_consensus(
        self,
        consensus_id: str,
        agents: list[str],
        decision_func: callable,
        timeout: float = 30.0,
    ) -> ConsensusResult | None:
        """
        Run a complete consensus process with timeout.

        Args:
            consensus_id: Consensus process identifier
            agents: List of agent IDs to participate
            decision_func: Async function to get agent decisions
            timeout: Timeout in seconds

        Returns:
            Consensus result or None
        """
        self.start_consensus(consensus_id)

        try:
            # Collect votes from all agents
            tasks = []
            for agent_id in agents:
                task = asyncio.create_task(
                    self._collect_agent_vote(
                        consensus_id,
                        agent_id,
                        decision_func,
                    )
                )
                tasks.append(task)

            # Wait for all votes or timeout
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )

            # Compute consensus
            return self.compute_consensus(consensus_id)

        except TimeoutError:
            logger.warning("Timeout for consensus {consensus_id}")
            self.process_states[consensus_id] = ConsensusState.FAILED
            return None
        finally:
            # Cleanup
            self.cleanup_process(consensus_id)

    async def _collect_agent_vote(
        self,
        consensus_id: str,
        agent_id: str,
        decision_func: callable,
    ) -> None:
        """
        Collect a vote from a single agent.

        Args:
            consensus_id: Consensus process identifier
            agent_id: Agent identifier
            decision_func: Function to get agent decision
        """
        try:
            decision, confidence = await decision_func(agent_id)
            self.add_vote(
                consensus_id=consensus_id,
                agent_id=agent_id,
                decision=decision,
                confidence=confidence,
            )
        except Exception:
            logger.error("Error collecting vote from {agent_id}: {e}")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get consensus engine statistics.

        Returns:
            Statistics dictionary
        """
        total_votes = sum(len(votes) for votes in self.active_processes.values())

        return {
            "active_processes": len(self.active_processes),
            "total_votes_collected": total_votes,
            "tracked_agents": len(self.agent_reputation),
            "ahead_by_k": self.ahead_by_k,
            "min_votes": self.min_votes,
            "confidence_threshold": self.confidence_threshold,
        }
