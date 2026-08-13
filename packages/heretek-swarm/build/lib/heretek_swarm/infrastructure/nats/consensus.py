"""
NATS Consensus Voting System.

Provides distributed consensus voting for agent decisions using NATS pub/sub.
Supports vote submission, collection, quorum detection, and decision finalization.

Example:
    ```python
    from heretek_swarm.infrastructure.nats.consensus import ConsensusVoting
    from heretek_swarm.consensus.swarm_deliberation import Position

    voting = ConsensusVoting()
    await voting.initialize()

    # Submit a vote
    await voting.submit_vote(
        agent_id="agent-1",
        decision_id="deploy-123",
        position=Position.AGREE,
        rationale="All tests passed"
    )

    # Collect votes with timeout
    votes = await voting.collect_votes("deploy-123", timeout=10.0)

    # Finalize decision with quorum check
    result = await voting.finalize_decision("deploy-123")
    ```
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from heretek_swarm.consensus.swarm_deliberation import Position
from heretek_swarm.infrastructure.nats.client import NATSClient, get_nats_client

logger = structlog.get_logger("nats.consensus")


class VoteStatus(Enum):
    """Status of a vote."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class QuorumState(Enum):
    """Quorum state for decision finalization."""

    PENDING = "pending"
    QUORUM_REACHED = "quorum_reached"
    QUORUM_NOT_REACHED = "quorum_not_reached"
    TIMEOUT = "timeout"


@dataclass
class Vote:
    """Represents a single vote in a decision."""

    vote_id: str
    agent_id: str
    decision_id: str
    position: Position
    rationale: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: VoteStatus = VoteStatus.SUBMITTED
    weight: float = 1.0


@dataclass
class VoteResult:
    """Result of vote collection."""

    decision_id: str
    votes: list[Vote]
    quorum_met: bool
    consensus_score: float
    dissenting_agents: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DecisionFinalization:
    """Result of decision finalization."""

    decision_id: str
    finalized: bool
    final_position: Position | None
    quorum_state: QuorumState
    vote_count: int
    participating_agents: list[str]
    minority_report: list[str]
    consensus_score: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ConsensusVoting:
    """
    NATS-based consensus voting for agent decisions.

    Provides:
    - Vote submission via NATS pub/sub
    - Vote collection with timeout
    - Quorum detection for decision finalization
    - Integration with SwarmDeliberationEngine

    Uses NATS subjects:
    - consensus.votes.{decision_id} - Vote submissions
    - consensus.decisions.{decision_id} - Decision outcomes
    """

    def __init__(
        self,
        quorum_threshold: float = 0.66,
        vote_timeout: float = 30.0,
        min_participants: int = 3,
    ) -> None:
        """
        Initialize consensus voting.

        Args:
            quorum_threshold: Threshold for quorum (0.0 to 1.0)
            vote_timeout: Timeout for vote collection in seconds
            min_participants: Minimum participants required for valid decision
        """
        self.quorum_threshold = quorum_threshold
        self.vote_timeout = vote_timeout
        self.min_participants = min_participants

        self._client: NATSClient | None = None
        self._votes: dict[str, list[Vote]] = {}
        self._subscriptions: dict[str, str] = {}
        self._pending_decisions: set[str] = set()
        self._vote_events: dict[str, asyncio.Event] = {}

    async def initialize(self) -> None:
        """Initialize NATS client connection."""
        self._client = await get_nats_client()
        if not self._client.is_connected:
            await self._client.connect()
        logger.info(
            "consensus_voting_initialized",
            quorum_threshold=self.quorum_threshold,
            vote_timeout=self.vote_timeout,
        )

    async def submit_vote(
        self,
        agent_id: str,
        decision_id: str,
        position: Position,
        rationale: str = "",
        weight: float = 1.0,
    ) -> bool:
        """
        Submit a vote for a decision.

        Args:
            agent_id: ID of the agent voting
            decision_id: ID of the decision being voted on
            position: Agent's position (from Position enum)
            rationale: Optional reasoning for the vote
            weight: Optional weight for expertise-based voting

        Returns:
            True if vote submitted successfully
        """
        if not self._client or not self._client.is_connected:
            logger.warning("nats_client_not_connected")
            return False

        vote = Vote(
            vote_id=f"{agent_id}:{decision_id}:{datetime.now(UTC).timestamp()}",
            agent_id=agent_id,
            decision_id=decision_id,
            position=position,
            rationale=rationale,
            weight=weight,
            status=VoteStatus.SUBMITTED,
        )

        if decision_id not in self._votes:
            self._votes[decision_id] = []
        self._votes[decision_id].append(vote)

        vote_payload = {
            "vote_id": vote.vote_id,
            "agent_id": agent_id,
            "decision_id": decision_id,
            "position": position.value,
            "rationale": rationale,
            "weight": weight,
            "timestamp": vote.timestamp,
            "status": vote.status.value,
        }

        subject = f"consensus.votes.{decision_id}"
        success = await self._client.publish(subject, vote_payload)

        if success:
            logger.info(
                "vote_submitted",
                agent_id=agent_id,
                decision_id=decision_id,
                position=position.value,
            )
        else:
            logger.error(
                "vote_submission_failed",
                agent_id=agent_id,
                decision_id=decision_id,
            )

        return success

    async def collect_votes(
        self,
        decision_id: str,
        timeout_sec: float | None = None,
    ) -> VoteResult:
        """
        Collect all votes for a decision.

        Args:
            decision_id: ID of the decision
            timeout: Optional timeout in seconds (uses default if not provided)

        Returns:
            VoteResult with all collected votes and quorum status
        """
        timeout = timeout_sec or self.vote_timeout
        votes = self._votes.get(decision_id, [])

        vote_event = asyncio.Event()
        self._vote_events[decision_id] = vote_event

        try:
            start_time = datetime.now(UTC)
            while (datetime.now(UTC) - start_time).total_seconds() < timeout:
                if len(votes) >= self.min_participants:
                    break
                try:
                    await asyncio.wait_for(vote_event.wait(), timeout=1.0)
                    vote_event.clear()
                    votes = self._votes.get(decision_id, [])
                except TimeoutError:
                    votes = self._votes.get(decision_id, [])
                    continue
        finally:
            self._vote_events.pop(decision_id, None)

        consensus_score = self._calculate_consensus(votes)
        quorum_met = len(votes) >= self.min_participants
        dissenting_agents = self._identify_dissent(votes, consensus_score)

        result = VoteResult(
            decision_id=decision_id,
            votes=votes,
            quorum_met=quorum_met,
            consensus_score=consensus_score,
            dissenting_agents=dissenting_agents,
        )

        logger.info(
            "votes_collected",
            decision_id=decision_id,
            vote_count=len(votes),
            quorum_met=quorum_met,
            consensus_score=consensus_score,
        )

        return result

    async def finalize_decision(
        self,
        decision_id: str,
        force: bool = False,
    ) -> DecisionFinalization:
        """
        Finalize a decision after vote collection.

        Args:
            decision_id: ID of the decision to finalize
            force: Force finalization even if quorum not met

        Returns:
            DecisionFinalization with the final result
        """
        votes = self._votes.get(decision_id, [])

        if not votes:
            logger.warning("finalize_no_votes", decision_id=decision_id)
            return DecisionFinalization(
                decision_id=decision_id,
                finalized=False,
                final_position=None,
                quorum_state=QuorumState.PENDING,
                vote_count=0,
                participating_agents=[],
                minority_report=[],
                consensus_score=0.0,
            )

        consensus_score = self._calculate_consensus(votes)
        participating_agents = [v.agent_id for v in votes]

        if len(votes) < self.min_participants:
            quorum_state = QuorumState.QUORUM_NOT_REACHED
            if not force:
                logger.warning(
                    "quorum_not_reached",
                    decision_id=decision_id,
                    votes=len(votes),
                    required=self.min_participants,
                )
                return DecisionFinalization(
                    decision_id=decision_id,
                    finalized=False,
                    final_position=None,
                    quorum_state=quorum_state,
                    vote_count=len(votes),
                    participating_agents=participating_agents,
                    minority_report=[],
                    consensus_score=consensus_score,
                )

        final_position = self._calculate_final_position(votes)
        dissenting = self._identify_dissent(votes, consensus_score)

        if self._client and self._client.is_connected:
            finalization_payload = {
                "decision_id": decision_id,
                "finalized": True,
                "final_position": final_position.value if final_position else None,
                "quorum_state": quorum_state.value,
                "vote_count": len(votes),
                "participating_agents": participating_agents,
                "consensus_score": consensus_score,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            subject = f"consensus.decisions.{decision_id}"
            await self._client.publish(subject, finalization_payload)

        logger.info(
            "decision_finalized",
            decision_id=decision_id,
            final_position=final_position.value if final_position else None,
            quorum_state=quorum_state.value,
            vote_count=len(votes),
            consensus_score=consensus_score,
        )

        return DecisionFinalization(
            decision_id=decision_id,
            finalized=True,
            final_position=final_position,
            quorum_state=(
                QuorumState.QUORUM_REACHED
                if quorum_state == QuorumState.QUORUM_NOT_REACHED and force
                else quorum_state
            ),
            vote_count=len(votes),
            participating_agents=participating_agents,
            minority_report=dissenting,
            consensus_score=consensus_score,
        )

    def _calculate_consensus(self, votes: list[Vote]) -> float:
        """Calculate consensus score based on vote agreement."""
        if not votes:
            return 0.0

        if len(votes) == 1:
            return 1.0

        position_counts: dict[str, int] = {}
        total_weight = 0.0

        for vote in votes:
            pos_key = vote.position.value
            position_counts[pos_key] = position_counts.get(pos_key, 0) + 1
            total_weight += vote.weight

        if total_weight == 0:
            return 0.0

        max_count = max(position_counts.values())
        return max_count / len(votes)

    def _calculate_final_position(self, votes: list[Vote]) -> Position | None:
        """Calculate final position using weighted voting."""
        if not votes:
            return None

        position_scores: dict[Position, float] = dict.fromkeys(Position, 0.0)

        for vote in votes:
            position_scores[vote.position] += vote.weight

        return max(position_scores, key=position_scores.get)  # type: ignore

    def _identify_dissent(self, votes: list[Vote], consensus_score: float) -> list[str]:
        """Identify agents that dissented from consensus."""
        if not votes or consensus_score >= self.quorum_threshold:
            return []

        position_counts: dict[str, int] = {}
        for vote in votes:
            pos_key = vote.position.value
            position_counts[pos_key] = position_counts.get(pos_key, 0) + 1

        if not position_counts:
            return []

        majority_position = max(position_counts, key=position_counts.get)
        return [vote.agent_id for vote in votes if vote.position.value != majority_position]

    async def register_decision(self, decision_id: str, participant_count: int) -> None:
        """
        Register a decision for tracking.

        Args:
            decision_id: ID of the decision
            participant_count: Expected number of participants
        """
        self._pending_decisions.add(decision_id)
        if decision_id not in self._votes:
            self._votes[decision_id] = []

        logger.info(
            "decision_registered",
            decision_id=decision_id,
            expected_participants=participant_count,
        )

    async def unregister_decision(self, decision_id: str) -> None:
        """
        Unregister a decision and clean up resources.

        Args:
            decision_id: ID of the decision
        """
        self._pending_decisions.discard(decision_id)
        self._votes.pop(decision_id, None)
        self._vote_events.pop(decision_id, None)

        if decision_id in self._subscriptions:
            sub_id = self._subscriptions.pop(decision_id)
            if self._client:
                await self._client.unsubscribe(sub_id)

        logger.info("decision_unregistered", decision_id=decision_id)

    async def subscribe_to_votes(
        self,
        decision_id: str,
        callback: Any,
    ) -> str | None:
        """
        Subscribe to vote events for a decision.

        Args:
            decision_id: ID of the decision
            callback: Async callback for vote events

        Returns:
            Subscription ID or None
        """
        if not self._client:
            return None

        subject = f"consensus.votes.{decision_id}"

        def wrapped_callback(msg):
            """Wrapper that parses vote and calls callback."""
            try:
                payload = json.loads(msg.data.decode()) if isinstance(msg.data, bytes) else msg.data
                asyncio.create_task(callback(payload))  # noqa: RUF006
            except Exception as e:
                logger.error("vote_callback_error", error=str(e))

        sub_id = await self._client.subscribe(subject, wrapped_callback)
        self._subscriptions[decision_id] = sub_id

        return sub_id

    def get_votes(self, decision_id: str) -> list[Vote]:
        """
        Get all votes for a decision.

        Args:
            decision_id: ID of the decision

        Returns:
            List of votes
        """
        return self._votes.get(decision_id, [])

    def get_participants(self, decision_id: str) -> list[str]:
        """
        Get all agents who have voted on a decision.

        Args:
            decision_id: ID of the decision

        Returns:
            List of agent IDs
        """
        votes = self._votes.get(decision_id, [])
        return list({v.agent_id for v in votes})
