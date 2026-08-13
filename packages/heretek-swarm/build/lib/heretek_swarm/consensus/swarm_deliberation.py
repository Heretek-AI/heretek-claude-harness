"""
Swarm Deliberation Engine - Multi-round voting with argument exchange.

This module implements advanced swarm deliberation capabilities:
- Multi-round voting with argument exchange
- Confidence-weighted voting based on agent expertise
- Dissent tracking and minority report preservation
- Consensus threshold adaptation

The deliberation engine facilitates structured group decision-making
by allowing agents to exchange arguments, update their positions,
and converge toward consensus through iterative rounds.

Example:
    ```python
    from heretek_swarm.consensus.swarm_deliberation import SwarmDeliberationEngine

    # Initialize engine
    engine = SwarmDeliberationEngine(
        max_rounds=5,
        consensus_threshold=0.75,
        min_participants=3
    )

    # Start deliberation
    engine.start_deliberation(
        deliberation_id="deploy-decision",
        proposal="Deploy to production",
        participants=["agent-1", "agent-2", "agent-3"]
    )

    # Submit initial positions
    engine.submit_position(
        agent_id="agent-1",
        position="agree",
        confidence=0.8,
        argument="All tests passed"
    )

    # Run deliberation round
    round_result = engine.run_deliberation_round()

    # Get final result
    result = engine.finalize_deliberation()
    ```
"""

import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from .expertise import AgentExpertiseProfiler

logger = structlog.get_logger("SwarmDeliberationEngine")


class DeliberationState(Enum):
    """Deliberation process states."""

    INITIATED = "initiated"
    GATHERING_POSITIONS = "gathering_positions"
    DELIBERATING = "deliberating"
    FINAL_VOTING = "final_voting"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Position(Enum):
    """Agent position options."""

    STRONG_AGREE = "strong_agree"  # Confidence >= 0.9
    AGREE = "agree"  # Confidence >= 0.6
    LEAN_AGREE = "lean_agree"  # Confidence >= 0.5
    LEAN_DISAGREE = "lean_disagree"  # Confidence < 0.5
    DISAGREE = "disagree"  # Confidence >= 0.6
    STRONG_DISAGREE = "strong_disagree"  # Confidence >= 0.9


@dataclass
class Argument:
    """
    An argument submitted during deliberation.

    Attributes:
        argument_id: Unique argument identifier
        agent_id: Submitting agent
        position: Supported position
        content: Argument text
        confidence: Confidence in argument
        supports: IDs of arguments this supports
        rebuttals: IDs of arguments this rebuts
        timestamp: Submission timestamp
        expertise_weight: Weight based on agent expertise
    """

    argument_id: str
    agent_id: str
    position: Position
    content: str
    confidence: float
    supports: list[str] = field(default_factory=list)
    rebuttals: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expertise_weight: float = 1.0


@dataclass
class AgentPosition:
    """
    Agent's current position in deliberation.

    Attributes:
        agent_id: Agent identifier
        position: Current position
        confidence: Confidence level
        argument: Supporting argument
        round_submitted: Round number when submitted
        previous_positions: History of position changes
    """

    agent_id: str
    position: Position
    confidence: float
    argument: str | None = None
    round_submitted: int = 0
    previous_positions: list[tuple[Position, float]] = field(default_factory=list)

    def update_position(
        self,
        new_position: Position,
        new_confidence: float,
        round_number: int,
    ) -> None:
        """Update position and track history."""
        self.previous_positions.append((self.position, self.confidence))
        self.position = new_position
        self.confidence = new_confidence
        self.round_submitted = round_number


@dataclass
class DeliberationRound:
    """
    Results from a single deliberation round.

    Attributes:
        round_number: Round number
        positions: All positions in this round
        arguments: All arguments submitted
        consensus_score: Current consensus score
        position_changes: Number of position changes
        summary: Round summary
    """

    round_number: int
    positions: dict[str, AgentPosition]
    arguments: list[Argument]
    consensus_score: float
    position_changes: int
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DeliberationResult:
    """
    Final result of a deliberation.

    Attributes:
        deliberation_id: Deliberation identifier
        proposal: Original proposal
        final_position: Final agreed position
        consensus_score: Final consensus score
        participation_rate: Rate of agent participation
        rounds_completed: Number of rounds run
        minority_report: Dissenting opinions
        arguments_summary: Summary of key arguments
        decision_provenance: Complete decision history
    """

    deliberation_id: str
    proposal: str
    final_position: Position
    consensus_score: float
    participation_rate: float
    rounds_completed: int
    minority_report: list[str]
    arguments_summary: dict[str, Any]
    decision_provenance: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class SwarmDeliberationEngine:
    """
    Swarm Deliberation Engine for multi-round consensus.

    Facilitates structured group decision-making through:
    - Multi-round voting with argument exchange
    - Confidence-weighted voting based on expertise
    - Dissent tracking and minority report preservation
    - Dynamic consensus threshold adaptation

    The engine manages the full deliberation lifecycle from initiation
    through final consensus, tracking all position changes and arguments.

    Attributes:
        max_rounds: Maximum deliberation rounds
        consensus_threshold: Threshold for consensus
        min_participants: Minimum required participants
        expertise_profiler: Optional expertise profiler for weighting
    """

    def __init__(
        self,
        max_rounds: int = 5,
        consensus_threshold: float = 0.75,
        min_participants: int = 3,
        expertise_profiler: AgentExpertiseProfiler | None = None,
        argument_timeout: float = 30.0,
    ) -> None:
        """
        Initialize the deliberation engine.

        Args:
            max_rounds: Maximum number of deliberation rounds
            consensus_threshold: Consensus threshold (0.0 to 1.0)
            min_participants: Minimum required participants
            expertise_profiler: Optional expertise profiler
            argument_timeout: Timeout for argument submission in seconds
        """
        self.max_rounds = max_rounds
        self.consensus_threshold = consensus_threshold
        self.min_participants = min_participants
        self.expertise_profiler = expertise_profiler
        self.argument_timeout = argument_timeout

        # Active deliberations
        self.active_deliberations: dict[str, dict[str, Any]] = {}
        self.deliberation_states: dict[str, DeliberationState] = {}

        # Round tracking
        self.current_rounds: dict[str, int] = {}
        self.round_results: dict[str, list[DeliberationRound]] = {}

        logger.info(
            f"SwarmDeliberationEngine initialized with max_rounds={max_rounds}, "  # noqa: G004
            f"consensus_threshold={consensus_threshold:.2f}"
        )

    def start_deliberation(
        self,
        deliberation_id: str,
        proposal: str,
        participants: list[str],
        domain: str | None = None,
    ) -> None:
        """
        Start a new deliberation process.

        Args:
            deliberation_id: Unique deliberation identifier
            proposal: Proposal to deliberate
            participants: List of participating agent IDs
            domain: Optional domain for expertise weighting
        """
        if len(participants) < self.min_participants:
            logger.warning(
                f"Insufficient participants: {len(participants)} < {self.min_participants}"  # noqa: G004
            )

        self.active_deliberations[deliberation_id] = {
            "proposal": proposal,
            "participants": set(participants),
            "domain": domain,
            "positions": {},
            "arguments": [],
            "start_time": datetime.now(UTC).isoformat(),
            "provenance": {
                "initiated": datetime.now(UTC).isoformat(),
                "position_changes": [],
                "arguments_submitted": [],
                "rounds": [],
            },
        }

        self.deliberation_states[deliberation_id] = DeliberationState.GATHERING_POSITIONS
        self.current_rounds[deliberation_id] = 0
        self.round_results[deliberation_id] = []

        logger.info(
            f"Started deliberation {deliberation_id}: '{proposal}' "  # noqa: G004
            f"with {len(participants)} participants"
        )

    def submit_position(
        self,
        deliberation_id: str,
        agent_id: str,
        position: Position,
        confidence: float,
        argument: str | None = None,
    ) -> bool:
        """
        Submit an agent's position in the deliberation.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Agent submitting position
            position: Agent's position
            confidence: Confidence level (0.0 to 1.0)
            argument: Optional supporting argument

        Returns:
            True if position accepted, False otherwise
        """
        if deliberation_id not in self.active_deliberations:
            logger.warning("Unknown deliberation: {deliberation_id}")
            return False

        if agent_id not in self.active_deliberations[deliberation_id]["participants"]:
            logger.warning("Agent {agent_id} not a participant")
            return False

        state = self.deliberation_states.get(deliberation_id)
        if state not in [
            DeliberationState.GATHERING_POSITIONS,
            DeliberationState.DELIBERATING,
        ]:
            logger.warning("Deliberation not accepting positions: {state}")
            return False

        # Create or update position
        positions = self.active_deliberations[deliberation_id]["positions"]
        current_round = self.current_rounds[deliberation_id]

        if agent_id in positions:
            # Track position change
            old_position = positions[agent_id].position
            if old_position != position:
                self.active_deliberations[deliberation_id]["provenance"]["position_changes"].append(
                    {
                        "agent_id": agent_id,
                        "from": old_position.value,
                        "to": position.value,
                        "round": current_round,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            positions[agent_id].update_position(position, confidence, current_round)
        else:
            positions[agent_id] = AgentPosition(
                agent_id=agent_id,
                position=position,
                confidence=confidence,
                argument=argument,
                round_submitted=current_round,
            )

        # Add argument if provided
        if argument:
            self.submit_argument(
                deliberation_id=deliberation_id,
                agent_id=agent_id,
                position=position,
                content=argument,
                confidence=confidence,
            )

        logger.debug(
            f"Position submitted by {agent_id} in {deliberation_id}: "  # noqa: G004
            f"{position.value} (confidence: {confidence:.2f})"
        )
        return True

    def submit_argument(
        self,
        deliberation_id: str,
        agent_id: str,
        position: Position,
        content: str,
        confidence: float,
        supports: list[str] | None = None,
        rebuttals: list[str] | None = None,
    ) -> str | None:
        """
        Submit an argument to support a position.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Agent submitting argument
            position: Position being supported
            content: Argument content
            confidence: Confidence in argument
            supports: IDs of arguments this supports
            rebuttals: IDs of arguments this rebuts

        Returns:
            Argument ID if accepted, None otherwise
        """
        if deliberation_id not in self.active_deliberations:
            return None

        # Calculate expertise weight
        expertise_weight = 1.0
        domain = self.active_deliberations[deliberation_id].get("domain")
        if self.expertise_profiler and domain:
            expertise_weight = self.expertise_profiler.get_expertise_score(agent_id, domain)

        argument_id = f"arg-{deliberation_id}-{len(self.active_deliberations[deliberation_id]['arguments']) + 1}"  # noqa: E501
        argument = Argument(
            argument_id=argument_id,
            agent_id=agent_id,
            position=position,
            content=content,
            confidence=confidence,
            supports=supports or [],
            rebuttals=rebuttals or [],
            expertise_weight=expertise_weight,
        )

        self.active_deliberations[deliberation_id]["arguments"].append(argument)
        self.active_deliberations[deliberation_id]["provenance"]["arguments_submitted"].append(
            {
                "argument_id": argument_id,
                "agent_id": agent_id,
                "position": position.value,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        logger.debug(
            f"Argument submitted in {deliberation_id}: {argument_id} "  # noqa: G004
            f"by {agent_id} ({position.value})"
        )
        return argument_id

    def run_deliberation_round(self, deliberation_id: str) -> DeliberationRound | None:
        """
        Run a single round of deliberation.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Round results or None if deliberation not active
        """
        if deliberation_id not in self.active_deliberations:
            logger.warning("Unknown deliberation: {deliberation_id}")
            return None

        state = self.deliberation_states.get(deliberation_id)
        if state not in [
            DeliberationState.GATHERING_POSITIONS,
            DeliberationState.DELIBERATING,
        ]:
            logger.warning("Deliberation not active: {state}")
            return None

        # Increment round
        self.current_rounds[deliberation_id] += 1
        current_round = self.current_rounds[deliberation_id]

        # Update state
        self.deliberation_states[deliberation_id] = DeliberationState.DELIBERATING

        # Get current positions
        positions = self.active_deliberations[deliberation_id]["positions"].copy()
        arguments = self.active_deliberations[deliberation_id]["arguments"].copy()

        # Calculate consensus score
        consensus_score = self._calculate_consensus_score(deliberation_id)

        # Count position changes
        position_changes = sum(
            1
            for pos in positions.values()
            if len(pos.previous_positions) > 0 and pos.previous_positions[-1][0] != pos.position
        )

        # Generate summary
        summary = self._generate_round_summary(
            deliberation_id, current_round, consensus_score, position_changes
        )

        # Create round result
        round_result = DeliberationRound(
            round_number=current_round,
            positions=positions,
            arguments=arguments,
            consensus_score=consensus_score,
            position_changes=position_changes,
            summary=summary,
        )

        self.round_results[deliberation_id].append(round_result)
        self.active_deliberations[deliberation_id]["provenance"]["rounds"].append(
            {
                "round": current_round,
                "consensus_score": consensus_score,
                "position_changes": position_changes,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        logger.info(
            f"Round {current_round} complete for {deliberation_id}: "  # noqa: G004
            f"consensus={consensus_score:.2f}, changes={position_changes}"
        )

        # Check if consensus reached
        if consensus_score >= self.consensus_threshold:
            self.deliberation_states[deliberation_id] = DeliberationState.FINAL_VOTING
            logger.info("Consensus threshold reached for {deliberation_id}: {consensus_score:.2f}")
        elif current_round >= self.max_rounds:
            self.deliberation_states[deliberation_id] = DeliberationState.COMPLETED
            logger.info("Max rounds reached for {deliberation_id}")

        return round_result

    def _calculate_consensus_score(self, deliberation_id: str) -> float:
        """
        Calculate current consensus score.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Consensus score (0.0 to 1.0)
        """
        positions = self.active_deliberations[deliberation_id]["positions"]

        if not positions:
            return 0.0

        # Count weighted positions
        position_weights: dict[Position, float] = {}

        for agent_id, agent_pos in positions.items():
            # Get weight from expertise profiler if available
            weight = 1.0
            domain = self.active_deliberations[deliberation_id].get("domain")
            if self.expertise_profiler and domain:
                weight = self.expertise_profiler.get_weighted_confidence(
                    agent_id, domain, agent_pos.confidence
                )

            if agent_pos.position not in position_weights:
                position_weights[agent_pos.position] = 0.0
            position_weights[agent_pos.position] += weight

        # Calculate agreement ratio
        agree_positions = [
            Position.STRONG_AGREE,
            Position.AGREE,
            Position.LEAN_AGREE,
        ]
        disagree_positions = [
            Position.LEAN_DISAGREE,
            Position.DISAGREE,
            Position.STRONG_DISAGREE,
        ]

        agree_weight = sum(position_weights.get(p, 0.0) for p in agree_positions)
        disagree_weight = sum(position_weights.get(p, 0.0) for p in disagree_positions)
        total_weight = agree_weight + disagree_weight

        if total_weight == 0:
            return 0.5

        # Consensus is higher when one side dominates
        majority_ratio = max(agree_weight, disagree_weight) / total_weight

        # Adjust for participation
        participation = len(positions) / len(
            self.active_deliberations[deliberation_id]["participants"]
        )

        return majority_ratio * participation

    def _generate_round_summary(
        self,
        deliberation_id: str,
        round_number: int,
        consensus_score: float,
        position_changes: int,
    ) -> str:
        """
        Generate summary of deliberation round.

        Args:
            deliberation_id: Deliberation identifier
            round_number: Current round number
            consensus_score: Current consensus score
            position_changes: Number of position changes

        Returns:
            Summary string
        """
        positions = self.active_deliberations[deliberation_id]["positions"]

        # Count positions
        position_counts: dict[Position, int] = {}
        for pos in positions.values():
            position_counts[pos.position] = position_counts.get(pos.position, 0) + 1

        counts_str = ", ".join(
            f"{p.value}: {c}" for p, c in sorted(position_counts.items(), key=lambda x: x[0].value)
        )

        return (
            f"Round {round_number}: {counts_str} | "
            f"Consensus: {consensus_score:.2f} | "
            f"Changes: {position_changes}"
        )

    def get_position_distribution(
        self,
        deliberation_id: str,
    ) -> dict[str, float]:
        """
        Get distribution of positions as percentages.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Dictionary of position percentages
        """
        if deliberation_id not in self.active_deliberations:
            return {}

        positions = self.active_deliberations[deliberation_id]["positions"]
        total = len(positions)

        if total == 0:
            return {}

        distribution: dict[str, int] = {}
        for pos in positions.values():
            key = pos.position.value
            distribution[key] = distribution.get(key, 0) + 1

        return {k: v / total for k, v in distribution.items()}

    def get_minority_opinions(
        self,
        deliberation_id: str,
        min_confidence: float = 0.6,
    ) -> list[dict[str, Any]]:
        """
        Get minority opinions (dissenting views).

        Args:
            deliberation_id: Deliberation identifier
            min_confidence: Minimum confidence threshold

        Returns:
            List of minority opinion records
        """
        if deliberation_id not in self.active_deliberations:
            return []

        positions = self.active_deliberations[deliberation_id]["positions"]
        distribution = self.get_position_distribution(deliberation_id)

        if not distribution:
            return []

        # Find majority position
        majority_position = max(distribution.items(), key=lambda x: x[1])[0]

        # Collect minority opinions
        minority_opinions = []
        for agent_id, pos in positions.items():
            pos_key = pos.position.value
            if pos_key != majority_position and pos.confidence >= min_confidence:
                minority_opinions.append(
                    {
                        "agent_id": agent_id,
                        "position": pos.position.value,
                        "confidence": pos.confidence,
                        "argument": pos.argument,
                    }
                )

        return minority_opinions

    def finalize_deliberation(
        self,
        deliberation_id: str,
    ) -> DeliberationResult | None:
        """
        Finalize deliberation and return result.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Deliberation result or None
        """
        if deliberation_id not in self.active_deliberations:
            logger.warning("Unknown deliberation: {deliberation_id}")
            return None

        self.deliberation_states[deliberation_id] = DeliberationState.COMPLETED

        # Calculate final consensus
        consensus_score = self._calculate_consensus_score(deliberation_id)

        # Determine final position
        final_position = self._determine_final_position(deliberation_id)

        # Get participation rate
        positions = self.active_deliberations[deliberation_id]["positions"]
        participants = self.active_deliberations[deliberation_id]["participants"]
        participation_rate = len(positions) / len(participants) if participants else 0.0

        # Get minority report
        minority_report = [
            f"{op['agent_id']}: {op['position']} (confidence: {op['confidence']:.2f})"
            for op in self.get_minority_opinions(deliberation_id)
        ]

        # Build arguments summary
        arguments = self.active_deliberations[deliberation_id]["arguments"]
        arguments_summary = {
            "total_arguments": len(arguments),
            "supporting": len(
                [
                    a
                    for a in arguments
                    if a.position in [Position.STRONG_AGREE, Position.AGREE, Position.LEAN_AGREE]
                ]
            ),
            "opposing": len(
                [
                    a
                    for a in arguments
                    if a.position
                    in [Position.LEAN_DISAGREE, Position.DISAGREE, Position.STRONG_DISAGREE]
                ]
            ),
            "avg_expertise_weight": (
                statistics.mean([a.expertise_weight for a in arguments]) if arguments else 0.0
            ),
        }

        # Build decision provenance
        provenance = self.active_deliberations[deliberation_id]["provenance"]
        decision_provenance = {
            "deliberation_id": deliberation_id,
            "proposal": self.active_deliberations[deliberation_id]["proposal"],
            "start_time": provenance["initiated"],
            "end_time": datetime.now(UTC).isoformat(),
            "rounds_completed": self.current_rounds[deliberation_id],
            "position_changes": len(provenance["position_changes"]),
            "total_arguments": len(provenance["arguments_submitted"]),
            "participants": list(participants),
            "final_consensus_score": consensus_score,
        }

        result = DeliberationResult(
            deliberation_id=deliberation_id,
            proposal=self.active_deliberations[deliberation_id]["proposal"],
            final_position=final_position,
            consensus_score=consensus_score,
            participation_rate=participation_rate,
            rounds_completed=self.current_rounds[deliberation_id],
            minority_report=minority_report,
            arguments_summary=arguments_summary,
            decision_provenance=decision_provenance,
        )

        logger.info(
            f"Deliberation {deliberation_id} finalized: "  # noqa: G004
            f"{final_position.value} (consensus: {consensus_score:.2f})"
        )

        return result

    def _determine_final_position(self, deliberation_id: str) -> Position:
        """
        Determine final position from deliberation.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Final position enum value
        """
        positions = self.active_deliberations[deliberation_id]["positions"]

        if not positions:
            return Position.LEAN_AGREE  # Default

        # Weighted vote by position strength
        position_values = {
            Position.STRONG_AGREE: 3,
            Position.AGREE: 2,
            Position.LEAN_AGREE: 1,
            Position.LEAN_DISAGREE: -1,
            Position.DISAGREE: -2,
            Position.STRONG_DISAGREE: -3,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for agent_id, pos in positions.items():
            # Apply expertise weight
            weight = pos.confidence
            domain = self.active_deliberations[deliberation_id].get("domain")
            if self.expertise_profiler and domain:
                weight = self.expertise_profiler.get_weighted_confidence(
                    agent_id, domain, pos.confidence
                )

            weighted_sum += position_values[pos.position] * weight
            total_weight += weight

        if total_weight == 0:
            return Position.LEAN_AGREE

        average_score = weighted_sum / total_weight

        if average_score >= 2.5:
            return Position.STRONG_AGREE
        if average_score >= 1.5:
            return Position.AGREE
        if average_score >= 0.5:
            return Position.LEAN_AGREE
        if average_score >= -0.5:
            return Position.LEAN_DISAGREE
        if average_score >= -1.5:
            return Position.DISAGREE
        return Position.STRONG_DISAGREE

    def get_deliberation_state(
        self,
        deliberation_id: str,
    ) -> DeliberationState | None:
        """
        Get current state of a deliberation.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Current state or None
        """
        return self.deliberation_states.get(deliberation_id)

    def get_round_history(
        self,
        deliberation_id: str,
    ) -> list[DeliberationRound]:
        """
        Get complete round history for a deliberation.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            List of round results
        """
        return self.round_results.get(deliberation_id, [])

    def cleanup_deliberation(self, deliberation_id: str) -> None:
        """
        Clean up a completed deliberation.

        Args:
            deliberation_id: Deliberation identifier
        """
        if deliberation_id in self.active_deliberations:
            del self.active_deliberations[deliberation_id]
        if deliberation_id in self.deliberation_states:
            del self.deliberation_states[deliberation_id]
        if deliberation_id in self.current_rounds:
            del self.current_rounds[deliberation_id]
        if deliberation_id in self.round_results:
            del self.round_results[deliberation_id]

        logger.debug("Cleaned up deliberation {deliberation_id}")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get deliberation engine statistics.

        Returns:
            Statistics dictionary
        """
        active_count = len(self.active_deliberations)
        completed_count = sum(
            1 for s in self.deliberation_states.values() if s == DeliberationState.COMPLETED
        )

        return {
            "active_deliberations": active_count,
            "completed_deliberations": completed_count,
            "max_rounds": self.max_rounds,
            "consensus_threshold": self.consensus_threshold,
            "min_participants": self.min_participants,
        }

    async def run_deliberation_with_timeout(
        self,
        deliberation_id: str,
        round_interval: float = 10.0,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> DeliberationResult | None:
        """
        Run deliberation with automatic round progression and timeout.

        Args:
            deliberation_id: Deliberation identifier
            round_interval: Seconds between rounds
            timeout: Optional overall timeout in seconds

        Returns:
            Final deliberation result or None
        """
        start_time = datetime.now(UTC)

        try:
            while True:
                # Check timeout
                if timeout:
                    elapsed = (datetime.now(UTC) - start_time).total_seconds()
                    if elapsed >= timeout:
                        self.deliberation_states[deliberation_id] = DeliberationState.TIMEOUT
                        logger.warning("Deliberation {deliberation_id} timed out after {elapsed}s")
                        break

                # Check if deliberation is complete
                state = self.deliberation_states.get(deliberation_id)
                if state in [
                    DeliberationState.COMPLETED,
                    DeliberationState.FAILED,
                    DeliberationState.FINAL_VOTING,
                ]:
                    break

                # Run deliberation round
                self.run_deliberation_round(deliberation_id)

                # Check if we should continue
                current_round = self.current_rounds[deliberation_id]
                if current_round >= self.max_rounds:
                    break

                # Wait before next round
                await asyncio.sleep(round_interval)

            # Finalize and return result
            return self.finalize_deliberation(deliberation_id)

        except Exception:
            logger.error("Deliberation error: {e}")
            self.deliberation_states[deliberation_id] = DeliberationState.FAILED
            return None
