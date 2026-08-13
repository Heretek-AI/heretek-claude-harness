"""
Enhanced MAKER Consensus Deliberation Module.

This module implements multi-round deliberation with:
- Argument/counter-argument structure
- Evidence quality weighting
- Consensus confidence scoring
- Dissent tracking and resolution

The deliberation system facilitates structured group decision-making
by allowing agents to exchange arguments, evaluate evidence quality,
and converge toward consensus through iterative rounds.

Example:
    ```python
    from heretek_swarm_core.consensus.deliberation import (
        DeliberationEngine,
        DeliberationConfig,
        Argument,
        CounterArgument,
        Evidence,
    )

    # Initialize engine
    config = DeliberationConfig(max_rounds=5, consensus_threshold=0.75)
    engine = DeliberationEngine(config)

    # Start deliberation
    engine.start_deliberation(
        topic="Deploy to production",
        participants=["agent-1", "agent-2", "agent-3"]
    )

    # Submit argument with evidence
    engine.submit_argument(
        agent_id="agent-1",
        position="for",
        reasoning="All tests passed",
        evidence_refs=["test-report-001"],
        confidence=0.9
    )

    # Run deliberation
    result = await engine.run_deliberation()
    ```
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm_core.consensus.deliberation_types import (
    Argument,
    ArgumentType,
    ConsensusConfidence,
    CounterArgument,
    DeliberationConfig,
    DeliberationOutcome,
    DeliberationResult,
    DeliberationRound,
    DissentRecord,
    Evidence,
    EvidenceType,
    Position,
    PositionChange,
)

logger = structlog.get_logger("DeliberationEngine")


class DeliberationEngine:
    """
    Enhanced Deliberation Engine for multi-round consensus.

    This engine implements:
    - Multi-round deliberation with argument exchange
    - Evidence quality weighting
    - Consensus confidence scoring
    - Dissent tracking and minority reports

    Attributes:
        config: Deliberation configuration
        expertise_profiler: Optional expertise profiler
    """

    def __init__(
        self,
        config: DeliberationConfig | None = None,
        expertise_profiler=None,  # AgentExpertiseProfiler type
    ) -> None:
        """
        Initialize deliberation engine.

        Args:
            config: Deliberation configuration
            expertise_profiler: Optional expertise profiler for weighting
        """
        self.config = config or DeliberationConfig()
        self.expertise_profiler = expertise_profiler

        # Active deliberations
        self.active_deliberations: dict[str, dict[str, Any]] = {}
        self.deliberation_states: dict[str, str] = {}

        # Evidence storage
        self.evidence_store: dict[str, dict[str, Evidence]] = {}

        # Round tracking
        self.current_rounds: dict[str, int] = {}
        self.round_results: dict[str, list[DeliberationRound]] = {}

        # Dissent tracking
        self.dissent_records: dict[str, list[DissentRecord]] = {}

        # Position change tracking
        self.position_change_history: dict[str, list[PositionChange]] = {}

        # Tiebreaker tracking
        self._tiebreaker_invocations: dict[str, int] = {}

        logger.info(
            f"DeliberationEngine initialized with max_rounds={self.config.max_rounds}, "
            f"consensus_threshold={self.config.consensus_threshold:.2f}"
        )

    def start_deliberation(
        self,
        topic: str,
        participants: list[str],
        deliberation_id: str | None = None,
        domain: str | None = None,
    ) -> str:
        """
        Start a new deliberation process.

        Args:
            topic: Topic to deliberate
            participants: List of participating agent IDs
            deliberation_id: Optional custom ID
            domain: Optional domain for expertise weighting

        Returns:
            Deliberation ID
        """
        if deliberation_id is None:
            deliberation_id = str(uuid.uuid4())

        if len(participants) < self.config.min_participants:
            logger.warning(
                f"Insufficient participants: {len(participants)} < {self.config.min_participants}"
            )

        self.active_deliberations[deliberation_id] = {
            "topic": topic,
            "participants": set(participants),
            "domain": domain,
            "arguments": [],
            "counter_arguments": [],
            "evidence": {},
            "positions": {},
            "start_time": datetime.now(UTC).isoformat(),
        }

        self.deliberation_states[deliberation_id] = "gathering_positions"
        self.current_rounds[deliberation_id] = 0
        self.round_results[deliberation_id] = []
        self.evidence_store[deliberation_id] = {}
        self.dissent_records[deliberation_id] = []
        self.position_change_history[deliberation_id] = []

        logger.info(
            f"Started deliberation {deliberation_id}: '{topic}' "
            f"with {len(participants)} participants"
        )

        return deliberation_id

    def submit_argument(
        self,
        deliberation_id: str,
        agent_id: str,
        position: Position,
        reasoning: str,
        evidence_refs: list[str] | None = None,
        confidence: float = 0.5,
        argument_type: ArgumentType = ArgumentType.PRIMARY,
        supports: list[str] | None = None,
        rebuttals: list[str] | None = None,
    ) -> str | None:
        """
        Submit an argument to the deliberation.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Agent submitting argument
            position: Position (for/against/neutral)
            reasoning: Argument reasoning
            evidence_refs: References to supporting evidence
            confidence: Confidence in argument
            argument_type: Type of argument
            supports: IDs of arguments this supports
            rebuttals: IDs of arguments this rebuts

        Returns:
            Argument ID if accepted, None otherwise
        """
        if deliberation_id not in self.active_deliberations:
            logger.warning("Unknown deliberation: {deliberation_id}")
            return None

        if agent_id not in self.active_deliberations[deliberation_id]["participants"]:
            logger.warning("Agent {agent_id} not a participant")
            return None

        # Calculate expertise weight
        expertise_weight = 1.0
        domain = self.active_deliberations[deliberation_id].get("domain")
        if self.expertise_profiler and domain:
            expertise_weight = self.expertise_profiler.get_expertise_score(agent_id, domain)

        argument = Argument(
            argument_id=f"arg-{deliberation_id}-{len(self.active_deliberations[deliberation_id]['arguments']) + 1}",
            agent_id=agent_id,
            position=position,
            reasoning=reasoning,
            evidence_refs=evidence_refs or [],
            confidence=confidence,
            argument_type=argument_type,
            supports=supports or [],
            rebuttals=rebuttals or [],
            expertise_weight=expertise_weight,
        )

        self.active_deliberations[deliberation_id]["arguments"].append(argument)

        # Track position change if agent already has a position
        current_positions = self.active_deliberations[deliberation_id].get("positions", {})
        if agent_id in current_positions:
            previous_pos = current_positions[agent_id].get("position")
            if previous_pos is not None and previous_pos != position:
                self.record_position_change(
                    deliberation_id=deliberation_id,
                    agent_id=agent_id,
                    previous_position=previous_pos,
                    new_position=position,
                    reasoning=reasoning[:200] if reasoning else "",
                )

        # Update agent position
        self.active_deliberations[deliberation_id]["positions"][agent_id] = {
            "position": position,
            "confidence": confidence,
            "last_argument": argument.argument_id,
        }

        logger.debug(
            f"Argument submitted in {deliberation_id}: {argument.argument_id} "
            f"by {agent_id} ({position.value})"
        )

        return argument.argument_id

    def submit_counter_argument(
        self,
        deliberation_id: str,
        agent_id: str,
        original_argument_id: str,
        counter_reasoning: str,
        evidence_refs: list[str] | None = None,
        confidence: float = 0.5,
    ) -> str | None:
        """
        Submit a counter-argument.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Agent submitting counter-argument
            original_argument_id: ID of argument being countered
            counter_reasoning: Counter-argument reasoning
            evidence_refs: References to supporting evidence
            confidence: Confidence in counter-argument

        Returns:
            Counter-argument ID if accepted, None otherwise
        """
        if deliberation_id not in self.active_deliberations:
            return None

        # Calculate expertise weight
        expertise_weight = 1.0
        domain = self.active_deliberations[deliberation_id].get("domain")
        if self.expertise_profiler and domain:
            expertise_weight = self.expertise_profiler.get_expertise_score(agent_id, domain)

        counter = CounterArgument(
            counter_id=f"counter-{deliberation_id}-{len(self.active_deliberations[deliberation_id]['counter_arguments']) + 1}",
            original_argument_id=original_argument_id,
            agent_id=agent_id,
            counter_reasoning=counter_reasoning,
            evidence_refs=evidence_refs or [],
            confidence=confidence,
            expertise_weight=expertise_weight,
        )

        self.active_deliberations[deliberation_id]["counter_arguments"].append(counter)

        logger.debug(
            f"Counter-argument submitted in {deliberation_id}: {counter.counter_id} by {agent_id}"
        )

        return counter.counter_id

    def submit_evidence(
        self,
        deliberation_id: str,
        evidence_type: EvidenceType,
        content: str,
        source: str | None = None,
        reliability_score: float = 0.5,
        submitted_by: str = "",
    ) -> str | None:
        """
        Submit evidence to support arguments.

        Args:
            deliberation_id: Deliberation identifier
            evidence_type: Type of evidence
            content: Evidence content
            source: Evidence source
            reliability_score: Reliability rating
            submitted_by: Agent submitting evidence

        Returns:
            Evidence ID if accepted, None otherwise
        """
        if deliberation_id not in self.active_deliberations:
            return None

        evidence = Evidence(
            evidence_type=evidence_type,
            content=content,
            source=source,
            reliability_score=reliability_score,
            submitted_by=submitted_by,
        )

        self.active_deliberations[deliberation_id]["evidence"][evidence.evidence_id] = evidence
        self.evidence_store[deliberation_id][evidence.evidence_id] = evidence

        logger.debug(
            f"Evidence submitted in {deliberation_id}: {evidence.evidence_id} "
            f"(type: {evidence_type.value}, reliability: {reliability_score:.2f})"
        )

        return evidence.evidence_id

    def run_deliberation_round(self, deliberation_id: str) -> DeliberationRound | None:
        """
        Run a single round of deliberation.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Round results or None if deliberation not active
        """
        if deliberation_id not in self.active_deliberations:
            return None

        start_time = datetime.now(UTC)
        self.current_rounds[deliberation_id] += 1
        current_round = self.current_rounds[deliberation_id]

        # Get current state
        data = self.active_deliberations[deliberation_id]
        arguments = data["arguments"].copy()
        counter_arguments = data["counter_arguments"].copy()
        evidence = list(data["evidence"].values())

        # Calculate consensus score
        consensus_score = self._calculate_consensus_score(deliberation_id)

        # Count position changes
        position_changes = self._count_position_changes(deliberation_id)

        # Determine round outcome
        if consensus_score >= self.config.consensus_threshold:
            outcome = DeliberationOutcome.CONSENSUS
        elif current_round >= self.config.max_rounds:
            outcome = (
                DeliberationOutcome.MAJORITY
                if consensus_score > 0.5
                else DeliberationOutcome.DEADLOCK
            )
        else:
            outcome = DeliberationOutcome.DEADLOCK

        end_time = datetime.now(UTC)
        round_result = DeliberationRound(
            topic=data["topic"],
            arguments=arguments,
            counter_arguments=counter_arguments,
            evidence_submitted=evidence,
            participant_agents=list(data["participants"]),
            round_duration=end_time - start_time,
            outcome=outcome,
            consensus_score=consensus_score,
            position_changes=position_changes,
            end_time=end_time.isoformat(),
        )

        self.round_results[deliberation_id].append(round_result)

        # Update state
        if outcome == DeliberationOutcome.CONSENSUS or current_round >= self.config.max_rounds:
            self.deliberation_states[deliberation_id] = "completed"

        logger.info(
            f"Round {current_round} complete for {deliberation_id}: "
            f"consensus={consensus_score:.2f}, outcome={outcome.value}"
        )

        return round_result

    def _calculate_consensus_score(self, deliberation_id: str) -> float:
        """
        Calculate current consensus score.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Consensus score (0.0-1.0)
        """
        data = self.active_deliberations[deliberation_id]
        positions = data.get("positions", {})
        arguments = data.get("arguments", [])
        evidence = data.get("evidence", {})

        if not positions:
            return 0.0

        # Calculate weighted positions
        for_weight = 0.0
        against_weight = 0.0
        neutral_weight = 0.0

        for agent_id, pos_data in positions.items():
            weight = 1.0
            if self.expertise_profiler and data.get("domain"):
                weight = self.expertise_profiler.get_expertise_score(agent_id, data["domain"])

            # Apply argument strength
            agent_args = [a for a in arguments if a.agent_id == agent_id]
            if agent_args:
                arg_strength = max(a.calculate_strength(evidence) for a in agent_args)
                weight *= arg_strength

            if pos_data["position"] == Position.FOR:
                for_weight += weight * pos_data["confidence"]
            elif pos_data["position"] == Position.AGAINST:
                against_weight += weight * pos_data["confidence"]
            else:
                neutral_weight += weight * pos_data["confidence"]

        total_weight = for_weight + against_weight + neutral_weight

        if total_weight == 0:
            return 0.0

        # Consensus is higher when one side dominates
        majority_weight = max(for_weight, against_weight)
        return majority_weight / total_weight

    def _count_position_changes(self, deliberation_id: str) -> int:
        """Count position changes across rounds."""
        rounds = self.round_results.get(deliberation_id, [])
        if len(rounds) < 2:
            return 0

        changes = 0
        prev_positions: dict[str, str] = {}

        for round_result in rounds:
            for arg in round_result.arguments:
                agent_id = arg.agent_id
                if agent_id in prev_positions and prev_positions[agent_id] != arg.position:
                    changes += 1
                prev_positions[agent_id] = arg.position

        return changes

    def track_dissent(
        self,
        deliberation_id: str,
        agent_id: str,
        reasoning: str = "",
    ) -> None:
        """
        Track dissenting opinion for minority report.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Dissenting agent
            reasoning: Reasoning for dissent
        """
        if deliberation_id not in self.active_deliberations:
            return

        positions = self.active_deliberations[deliberation_id].get("positions", {})
        if agent_id not in positions:
            return

        pos_data = positions[agent_id]

        # Get agent's key arguments
        arguments = self.active_deliberations[deliberation_id].get("arguments", [])
        agent_args = [a.argument_id for a in arguments if a.agent_id == agent_id]

        dissent = DissentRecord(
            agent_id=agent_id,
            position=pos_data["position"],
            confidence=pos_data["confidence"],
            reasoning=reasoning,
            key_arguments=agent_args,
        )

        self.dissent_records[deliberation_id].append(dissent)

        logger.info("Dissent tracked for agent {agent_id} in {deliberation_id}")

    def calculate_consensus_confidence(
        self,
        deliberation_id: str,
    ) -> ConsensusConfidence:
        """
        Calculate consensus confidence for a deliberation.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Consensus confidence
        """
        data = self.active_deliberations[deliberation_id]
        evidence = data.get("evidence", {})

        # Calculate weights
        for_weight, against_weight, total_weight = self._calculate_position_weights(deliberation_id)

        # Get evidence scores
        evidence_scores = [e.calculate_quality() for e in evidence.values()]

        # Get dissent records
        dissent_records = self.dissent_records.get(deliberation_id, [])

        confidence = ConsensusConfidence()
        confidence.calculate(
            for_weight, against_weight, total_weight, evidence_scores, dissent_records
        )

        return confidence

    def record_position_change(
        self,
        deliberation_id: str,
        agent_id: str,
        previous_position: Position,
        new_position: Position,
        round_number: int | None = None,
        reasoning: str = "",
    ) -> None:
        """
        Record a position change during deliberation.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Agent who changed position
            previous_position: Position before change
            new_position: Position after change
            round_number: Round when change occurred
            reasoning: Optional reasoning for the change
        """
        if deliberation_id not in self.position_change_history:
            self.position_change_history[deliberation_id] = []

        if round_number is None:
            round_number = self.current_rounds.get(deliberation_id, 0)

        change = PositionChange(
            agent_id=agent_id,
            previous_position=previous_position,
            new_position=new_position,
            round_number=round_number,
            reasoning=reasoning,
        )

        self.position_change_history[deliberation_id].append(change)

        logger.debug(
            f"Position change recorded for {agent_id} in {deliberation_id}: "
            f"{previous_position.value} -> {new_position.value} (round {round_number})"
        )

    def get_position_change_history(
        self,
        deliberation_id: str,
    ) -> list[PositionChange]:
        """
        Get complete position change history for a deliberation.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            List of position changes
        """
        return self.position_change_history.get(deliberation_id, [])

    def get_agent_position_changes(
        self,
        deliberation_id: str,
        agent_id: str,
    ) -> list[PositionChange]:
        """
        Get position changes for a specific agent.

        Args:
            deliberation_id: Deliberation identifier
            agent_id: Agent to get changes for

        Returns:
            List of position changes for the agent
        """
        history = self.position_change_history.get(deliberation_id, [])
        return [c for c in history if c.agent_id == agent_id]

    def steward_tiebreaker(
        self,
        deliberation_id: str,
        steward_id: str = "steward",
        criteria: str = "weighted_confidence",
    ) -> DeliberationResult | None:
        """
        Steward tiebreaker for deadlock situations.

        Called when max_rounds is reached without consensus.
        The Steward applies configurable criteria to break the tie.

        Args:
            deliberation_id: Deliberation identifier
            steward_id: ID of the Steward agent
            criteria: Tiebreaker criteria (weighted_confidence, first_position,
                     most_challenges, expert_determination)

        Returns:
            Final deliberation result or None if deliberation not found
        """
        if deliberation_id not in self.active_deliberations:
            logger.warning("Steward tiebreaker: Unknown deliberation {deliberation_id}")
            return None

        invocation_count = self._tiebreaker_invocations.get(deliberation_id, 0)
        self._tiebreaker_invocations[deliberation_id] = invocation_count + 1

        logger.info(
            f"Steward {steward_id} invoking tiebreaker for {deliberation_id} "
            f"(invocation #{invocation_count + 1}), criteria: {criteria}"
        )

        data = self.active_deliberations[deliberation_id]
        arguments = data.get("arguments", [])
        evidence = data.get("evidence", {})

        # Dispatch to appropriate tiebreaker method
        tiebreakers = {
            "weighted_confidence": self._tiebreak_weighted_confidence,
            "first_position": self._tiebreak_first_position,
            "most_challenges": self._tiebreak_most_challenges,
        }

        tiebreaker_func = tiebreakers.get(criteria, lambda **_: Position.NEUTRAL)
        final_position = tiebreaker_func(
            deliberation_id=deliberation_id,
            arguments=arguments,
        )

        consensus_score = self._calculate_consensus_score(deliberation_id)
        outcome = self._determine_tiebreak_outcome(consensus_score)
        confidence = self.calculate_consensus_confidence(deliberation_id)
        dissenting_agents = [d.agent_id for d in self.dissent_records.get(deliberation_id, [])]
        minority_report = self.dissent_records.get(deliberation_id, [])

        decision_data = {
            "deliberation_id": deliberation_id,
            "topic": data["topic"],
            "final_position": final_position.value,
            "consensus_score": consensus_score,
            "tiebreaker": criteria,
            "steward_id": steward_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        decision_hash = hashlib.sha256(str(sorted(decision_data.items())).encode()).hexdigest()

        result = DeliberationResult(
            deliberation_id=deliberation_id,
            topic=data["topic"],
            outcome=outcome,
            final_position=final_position,
            consensus_score=consensus_score,
            confidence=confidence,
            dissenting_agents=dissenting_agents,
            minority_report=minority_report,
            rounds_completed=self.current_rounds[deliberation_id],
            total_arguments=len(arguments),
            total_evidence=len(evidence),
            decision_hash=decision_hash,
        )

        self.deliberation_states[deliberation_id] = "completed"

        logger.info(
            f"Tiebreaker result for {deliberation_id}: {final_position.value} "
            f"(consensus: {consensus_score:.2f}, tiebreaker: {criteria})"
        )

        return result

    def _tiebreak_weighted_confidence(
        self,
        deliberation_id: str,
        arguments: list[Argument],
    ) -> Position:
        """
        Break tie using weighted confidence.

        Args:
            deliberation_id: Deliberation identifier
            arguments: List of arguments

        Returns:
            Final position based on weighted confidence
        """
        for_weight, against_weight, _ = self._calculate_position_weights(deliberation_id)

        if for_weight > against_weight:
            return Position.FOR
        if against_weight > for_weight:
            return Position.AGAINST
        return Position.NEUTRAL

    def _tiebreak_first_position(
        self,
        deliberation_id: str,
        arguments: list[Argument],
    ) -> Position:
        """
        Break tie using first position.

        Args:
            deliberation_id: Deliberation identifier
            arguments: List of arguments

        Returns:
            Final position based on first agent's position
        """
        data = self.active_deliberations[deliberation_id]
        positions = data.get("positions", {})
        sorted_agents = sorted(positions.keys())

        if sorted_agents:
            first_agent = sorted_agents[0]
            return positions[first_agent]["position"]
        return Position.NEUTRAL

    def _tiebreak_most_challenges(
        self,
        deliberation_id: str,
        arguments: list[Argument],
    ) -> Position:
        """
        Break tie using most challenges.

        Args:
            deliberation_id: Deliberation identifier
            arguments: List of arguments

        Returns:
            Final position based on challenge counts
        """
        challenge_counts: dict[str, int] = {}
        for arg in arguments:
            challenge_counts[arg.agent_id] = challenge_counts.get(arg.agent_id, 0) + len(
                arg.rebuttals
            )
        if challenge_counts:
            return Position.AGAINST
        return Position.NEUTRAL

    def _determine_tiebreak_outcome(self, consensus_score: float) -> DeliberationOutcome:
        """
        Determine outcome based on consensus score.

        Args:
            consensus_score: Calculated consensus score

        Returns:
            Deliberation outcome
        """
        if consensus_score >= self.config.consensus_threshold:
            return DeliberationOutcome.CONSENSUS
        if consensus_score > 0.5:
            return DeliberationOutcome.MAJORITY
        return DeliberationOutcome.DEADLOCK

    def _calculate_position_weights(
        self,
        deliberation_id: str,
    ) -> tuple[float, float, float]:
        """Calculate position weights for consensus scoring."""
        data = self.active_deliberations[deliberation_id]
        positions = data.get("positions", {})
        arguments = data.get("arguments", [])
        evidence = data.get("evidence", {})

        for_weight = 0.0
        against_weight = 0.0
        total_weight = 0.0

        for agent_id, pos_data in positions.items():
            weight = 1.0
            if self.expertise_profiler and data.get("domain"):
                weight = self.expertise_profiler.get_expertise_score(agent_id, data["domain"])

            agent_args = [a for a in arguments if a.agent_id == agent_id]
            if agent_args:
                arg_strength = max(a.calculate_strength(evidence) for a in agent_args)
                weight *= arg_strength

            weighted_confidence = weight * pos_data["confidence"]
            total_weight += weighted_confidence

            if pos_data["position"] == Position.FOR:
                for_weight += weighted_confidence
            elif pos_data["position"] == Position.AGAINST:
                against_weight += weighted_confidence

        return for_weight, against_weight, total_weight

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
            return None

        self.deliberation_states[deliberation_id] = "completed"

        data = self.active_deliberations[deliberation_id]
        arguments = data.get("arguments", [])
        evidence = data.get("evidence", {})

        # Calculate final consensus
        consensus_score = self._calculate_consensus_score(deliberation_id)

        # Determine final position
        for_weight, against_weight, _ = self._calculate_position_weights(deliberation_id)
        if for_weight > against_weight:
            final_position = Position.FOR
        elif against_weight > for_weight:
            final_position = Position.AGAINST
        else:
            final_position = Position.NEUTRAL

        # Determine outcome
        if consensus_score >= self.config.consensus_threshold:
            outcome = DeliberationOutcome.CONSENSUS
        elif consensus_score > 0.5:
            outcome = DeliberationOutcome.MAJORITY
        else:
            outcome = DeliberationOutcome.DEADLOCK

        # Calculate confidence
        confidence = self.calculate_consensus_confidence(deliberation_id)

        # Get dissenting agents
        dissenting_agents = [d.agent_id for d in self.dissent_records.get(deliberation_id, [])]
        minority_report = self.dissent_records.get(deliberation_id, [])

        # Generate decision hash
        decision_data = {
            "deliberation_id": deliberation_id,
            "topic": data["topic"],
            "final_position": final_position.value,
            "consensus_score": consensus_score,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        decision_hash = hashlib.sha256(str(sorted(decision_data.items())).encode()).hexdigest()

        result = DeliberationResult(
            deliberation_id=deliberation_id,
            topic=data["topic"],
            outcome=outcome,
            final_position=final_position,
            consensus_score=consensus_score,
            confidence=confidence,
            dissenting_agents=dissenting_agents,
            minority_report=minority_report,
            rounds_completed=self.current_rounds[deliberation_id],
            total_arguments=len(arguments),
            total_evidence=len(evidence),
            decision_hash=decision_hash,
        )

        logger.info(
            f"Deliberation {deliberation_id} finalized: "
            f"{final_position.value} (consensus: {consensus_score:.2f})"
        )

        return result

    def get_deliberation_state(self, deliberation_id: str) -> str | None:
        """Get current state of a deliberation."""
        return self.deliberation_states.get(deliberation_id)

    def get_position_distribution(
        self,
        deliberation_id: str,
    ) -> dict[str, float]:
        """Get distribution of positions as percentages."""
        if deliberation_id not in self.active_deliberations:
            return {}

        positions = self.active_deliberations[deliberation_id].get("positions", {})
        total = len(positions)

        if total == 0:
            return {}

        distribution: dict[str, int] = {}
        for pos_data in positions.values():
            key = pos_data["position"].value
            distribution[key] = distribution.get(key, 0) + 1

        return {k: v / total for k, v in distribution.items()}

    def get_round_history(self, deliberation_id: str) -> list[DeliberationRound]:
        """Get complete round history for a deliberation."""
        return self.round_results.get(deliberation_id, [])

    def get_deliberation_explanation(
        self,
        deliberation_id: str,
    ) -> dict[str, Any] | None:
        """
        Get a structured explanation of a deliberation decision.

        Returns why/whyNot/rollback_plan for OpenAEON-compatible explainability surface.

        Args:
            deliberation_id: Deliberation identifier

        Returns:
            Dict with deliberation explanation, or None if deliberation not found
        """
        if deliberation_id not in self.active_deliberations:
            return None

        deliberation = self.active_deliberations[deliberation_id]
        state = self.deliberation_states.get(deliberation_id, "unknown")

        # Compute position distribution
        positions = deliberation.get("positions", {})
        for_pos = sum(1 for p in positions.values() if hasattr(p, "value") and p.value == "FOR")
        against_pos = sum(
            1 for p in positions.values() if hasattr(p, "value") and p.value == "AGAINST"
        )
        neutral_pos = sum(
            1 for p in positions.values() if hasattr(p, "value") and p.value == "NEUTRAL"
        )

        # Determine final position from last round or consensus
        final_round = self.round_results.get(deliberation_id, [])
        final_position = "UNDETERMINED"
        consensus_score = 0.0
        if final_round:
            last = final_round[-1]
            final_position = (
                last.outcome.value if hasattr(last.outcome, "value") else str(last.outcome)
            )
            consensus_score = last.consensus_score

        # Top FOR and AGAINST arguments (up to 3 each)
        all_args = deliberation.get("arguments", [])
        for_args = [a for a in all_args if getattr(a.position, "value", "") == "FOR"][:3]
        against_args = [a for a in all_args if getattr(a.position, "value", "") == "AGAINST"][:3]

        # Rollback plan: suggest reverting to NEUTRAL if consensus is weak
        rollback_plan = None
        if consensus_score < self.config.consensus_threshold:
            rollback_plan = (
                f"Consensus ({consensus_score:.2f}) below threshold "
                f"({self.config.consensus_threshold}). Recommend reverting to NEUTRAL "
                f"and re-deliberating with additional evidence."
            )

        # Dissent records
        dissent = self.dissent_records.get(deliberation_id, [])
        dissent_summary = [
            {
                "agent_id": d.agent_id,
                "position": d.position.value if hasattr(d.position, "value") else str(d.position),
                "reasoning": d.reasoning,
                "resolved": d.resolved,
            }
            for d in dissent
        ]

        return {
            "deliberation_id": deliberation_id,
            "topic": deliberation.get("topic", ""),
            "domain": deliberation.get("domain", ""),
            "state": state,
            "final_position": final_position,
            "consensus_score": consensus_score,
            "participants": list(deliberation.get("participants", [])),
            "why": [a.content for a in for_args],
            "why_not": [a.content for a in against_args],
            "rollback_plan": rollback_plan,
            "position_distribution": {
                "for": for_pos,
                "against": against_pos,
                "neutral": neutral_pos,
                "total": len(positions),
            },
            "dissent_summary": dissent_summary,
            "rounds_completed": len(final_round),
            "start_time": deliberation.get("start_time"),
        }

    def get_statistics(self) -> dict[str, Any]:
        """Get deliberation engine statistics."""
        active_count = len(self.active_deliberations)
        completed_count = sum(1 for s in self.deliberation_states.values() if s == "completed")

        return {
            "active_deliberations": active_count,
            "completed_deliberations": completed_count,
            "max_rounds": self.config.max_rounds,
            "consensus_threshold": self.config.consensus_threshold,
            "min_participants": self.config.min_participants,
            "dissent_tracking_enabled": self.config.dissent_tracking,
        }

    def cleanup_deliberation(self, deliberation_id: str) -> None:
        """Clean up a completed deliberation."""
        for store in [
            self.active_deliberations,
            self.deliberation_states,
            self.current_rounds,
            self.round_results,
            self.evidence_store,
            self.dissent_records,
        ]:
            if deliberation_id in store:
                del store[deliberation_id]

        logger.debug("Cleaned up deliberation {deliberation_id}")
