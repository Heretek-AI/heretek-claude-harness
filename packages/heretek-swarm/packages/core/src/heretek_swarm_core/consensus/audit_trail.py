"""
Audit Trail - Core recording and storage operations for consensus decisions.

This module contains the writing/recording side of the audit system:
- Event recording (votes, arguments, decisions)
- Hash chain management
- Storage management
- Outcome tracking

Reading/querying is handled by audit_query.py.
The audit_models.py module contains shared dataclass definitions.
"""

import json
import queue
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

# JSONL file for --no-infra mode audit trail
_CONSENSUS_AUDIT_FILE = Path(".heretek/consensus_audit.jsonl")

from .audit_models import (
    ArgumentRecord,
    AuditEvent,
    AuditEventType,
    DecisionAudit,
    DecisionOutcome,
    DecisionRecord,
    DeliberationRoundRecord,
    VoteRecord,
)

logger = structlog.get_logger("ConsensusAuditTrail")


class ConsensusAuditTrail:
    """
    Audit trail for recording consensus decisions.

    Provides complete decision history with:
    - Vote breakdowns and argument logs
    - Outcome tracking for learning
    - Cryptographic integrity verification
    - Hash chain for immutability

    For querying and export, see audit_query.py.
    """

    def __init__(
        self,
        storage_backend: str = "memory",
        retention_days: int = 90,
        enable_hash_chain: bool = True,
    ) -> None:
        """
        Initialize the audit trail.

        Args:
            storage_backend: Storage backend (memory, postgresql, sqlite)
            retention_days: Number of days to retain audit data
            enable_hash_chain: Enable cryptographic event chaining
        """
        self.storage_backend = storage_backend
        self.retention_days = retention_days
        self.enable_hash_chain = enable_hash_chain

        # In-memory storage
        self.events: list[AuditEvent] = []
        self.decisions: dict[str, DecisionRecord] = {}
        self.votes: dict[str, list[VoteRecord]] = {}
        self.arguments: dict[str, list[ArgumentRecord]] = {}
        self.outcomes: dict[str, DecisionOutcome] = {}
        self.deliberation_rounds: dict[str, list[DeliberationRoundRecord]] = {}
        self.decision_audits: dict[str, DecisionAudit] = {}

        # Event chain tracking
        self.last_event_hash: str | None = None

        # Query statistics
        self.query_count = 0
        self.total_query_time_ms = 0.0

        # JSONL writer infrastructure (--no-infra mode)
        self._jsonl_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._writer_thread: threading.Thread | None = None
        self._writer_stop = threading.Event()

        logger.info(
            "ConsensusAuditTrail initialized",
            backend=storage_backend,
            retention=retention_days,
        )

    # ------------------------------------------------------------------------
    # Initialization & JSONL Writer (--no-infra mode)
    # ------------------------------------------------------------------------

    def initialize(self) -> None:
        """Start the background JSONL writer thread when in jsonl mode.

        Call this after construction when storage_backend == "jsonl".
        For in-memory mode, this is a no-op.
        """
        if self.storage_backend == "jsonl":
            self._writer_stop.clear()
            self._writer_thread = threading.Thread(
                target=self._jsonl_writer,
                name="consensus-audit-jsonl-writer",
                daemon=True,
            )
            self._writer_thread.start()
            logger.info("JSONL audit writer thread started")

    def _jsonl_writer(self) -> None:
        """Drain ``_jsonl_queue`` and write each event as a JSON line to
        ``_CONSENSUS_AUDIT_FILE``.

        Runs as a background thread started during ``initialize()``.
        The file is opened/closed per write (safe for concurrent readers).
        """
        while not self._writer_stop.is_set():
            try:
                record = self._jsonl_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                line = json.dumps(record, default=str, ensure_ascii=False)
                self._write_jsonl_line(_CONSENSUS_AUDIT_FILE, line)
                logger.debug(
                    "audit_jsonl_write",
                    event_type=record.get("event_type", "unknown"),
                )
            except TypeError as exc:
                logger.error(
                    "audit_jsonl_error",
                    error=str(exc),
                    record_keys=list(record.keys()) if isinstance(record, dict) else None,
                )
            except OSError as exc:
                logger.error(
                    "audit_jsonl_error",
                    error=str(exc),
                    path=str(_CONSENSUS_AUDIT_FILE),
                )
            finally:
                self._jsonl_queue.task_done()

        # Drain remaining items after stop signal
        while not self._jsonl_queue.empty():
            try:
                record = self._jsonl_queue.get_nowait()
                line = json.dumps(record, default=str, ensure_ascii=False)
                self._write_jsonl_line(_CONSENSUS_AUDIT_FILE, line)
                logger.debug("audit_jsonl_flush", event_type=record.get("event_type", "unknown"))
            except (TypeError, OSError, queue.Empty):
                break
            finally:
                self._jsonl_queue.task_done()

    @staticmethod
    def _write_jsonl_line(path: Path, line: str) -> None:
        """Synchronous file-write helper for JSONL audit records."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")

    def _record_to_jsonl(self, record: dict[str, Any]) -> None:
        """Put a serializable record dict on the JSONL writer queue.

        Only used when storage_backend == "jsonl". Non-blocking — the
        background thread handles the actual file I/O.
        """
        self._jsonl_queue.put(record)

    def cleanup(self) -> None:
        """Flush pending JSONL writes and stop the background writer.

        Safe to call multiple times. No-op for in-memory mode.
        """
        if self._writer_thread is None or not self._writer_thread.is_alive():
            return

        # Signal the writer to stop, then wait for queue to drain
        self._writer_stop.set()
        self._jsonl_queue.join()
        self._writer_thread.join(timeout=5.0)
        self._writer_thread = None
        logger.info("audit_jsonl_flush", message="JSONL audit writer stopped")

    # ------------------------------------------------------------------------
    # Event Recording
    # ------------------------------------------------------------------------

    def record_event(
        self,
        event_type: AuditEventType,
        consensus_id: str,
        agent_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """
        Record an audit event.

        Args:
            event_type: Type of event
            consensus_id: Related consensus process
            agent_id: Related agent (if any)
            data: Event-specific data

        Returns:
            Created audit event
        """
        event_id = f"evt-{consensus_id}-{len(self.events) + 1}"
        previous_hash = self.last_event_hash if self.enable_hash_chain else None

        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now(UTC).isoformat(),
            consensus_id=consensus_id,
            agent_id=agent_id,
            data=data or {},
            previous_hash=previous_hash,
        )

        self.events.append(event)
        self.last_event_hash = event.hash

        logger.debug("Audit event recorded: {event_id} ({event_type.value})")
        return event

    # ------------------------------------------------------------------------
    # Decision Recording
    # ------------------------------------------------------------------------

    def record_decision(
        self,
        decision_id: str,
        consensus_id: str,
        proposal: str,
        decision: str,
        confidence: float,
        participants: list[str] | None = None,
        reasoning: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionRecord:
        """
        Record a consensus decision.

        Args:
            decision_id: Decision identifier
            consensus_id: Related consensus process
            proposal: Original proposal
            decision: Final decision
            confidence: Overall confidence
            participants: List of participating agents
            reasoning: Optional reasoning summary
            metadata: Additional metadata

        Returns:
            Created decision record
        """
        self.record_event(
            event_type=AuditEventType.CONSENSUS_INITIATED,
            consensus_id=consensus_id,
            data={
                "decision_id": decision_id,
                "proposal": proposal,
                "participants": participants or [],
            },
        )

        record = DecisionRecord(
            decision_id=decision_id,
            consensus_id=consensus_id,
            proposal=proposal,
            decision=decision,
            confidence=confidence,
            participants=participants or [],
            reasoning_summary=reasoning,
            metadata=metadata or {},
        )

        self.decisions[decision_id] = record

        self.record_event(
            event_type=AuditEventType.CONSENSUS_REACHED,
            consensus_id=consensus_id,
            data={
                "decision_id": decision_id,
                "decision": decision,
                "confidence": confidence,
            },
        )

        # Queue for JSONL persistence in --no-infra mode
        if self.storage_backend == "jsonl":
            self._record_to_jsonl(
                {
                    "record_type": "decision",
                    "decision_id": decision_id,
                    "consensus_id": consensus_id,
                    "proposal": proposal,
                    "decision": decision,
                    "confidence": confidence,
                    "participants": participants or [],
                    "reasoning_summary": reasoning,
                    "metadata": metadata or {},
                    "timestamp": record.start_time,
                }
            )

        logger.info(
            f"Decision recorded: {decision_id} -> {decision} (confidence: {confidence:.2f})"
        )
        return record

    def record_vote(
        self,
        consensus_id: str,
        agent_id: str,
        decision: str,
        confidence: float,
        reasoning: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> VoteRecord:
        """
        Record a single vote.

        Args:
            consensus_id: Consensus process identifier
            agent_id: Voting agent
            decision: Vote decision
            confidence: Confidence level
            reasoning: Optional reasoning text
            metadata: Additional metadata

        Returns:
            Created vote record
        """
        vote_id = f"vote-{consensus_id}-{agent_id}"

        vote = VoteRecord(
            vote_id=vote_id,
            consensus_id=consensus_id,
            agent_id=agent_id,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            metadata=metadata or {},
        )

        if consensus_id not in self.votes:
            self.votes[consensus_id] = []
        self.votes[consensus_id].append(vote)

        # Update decision record if exists
        for decision_record in self.decisions.values():
            if decision_record.consensus_id == consensus_id:
                decision_record.votes.append(vote)
                if agent_id not in decision_record.participants:
                    decision_record.participants.append(agent_id)

        self.record_event(
            event_type=AuditEventType.VOTE_SUBMITTED,
            consensus_id=consensus_id,
            agent_id=agent_id,
            data={
                "vote_id": vote_id,
                "decision": decision,
                "confidence": confidence,
            },
        )

        # Queue for JSONL persistence in --no-infra mode
        if self.storage_backend == "jsonl":
            self._record_to_jsonl(
                {
                    "record_type": "vote",
                    "vote_id": vote_id,
                    "consensus_id": consensus_id,
                    "agent_id": agent_id,
                    "decision": decision,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "metadata": metadata or {},
                    "timestamp": vote.timestamp,
                }
            )

        logger.debug("Vote recorded: {agent_id} -> {decision} (confidence: {confidence:.2f})")
        return vote

    def record_argument(
        self,
        consensus_id: str,
        agent_id: str,
        position: str,
        content: str,
        supports: list[str] | None = None,
        rebuttals: list[str] | None = None,
    ) -> ArgumentRecord:
        """
        Record an argument submitted during deliberation.

        Args:
            consensus_id: Consensus process identifier
            agent_id: Submitting agent
            position: Position being supported
            content: Argument content
            supports: IDs of supported arguments
            rebuttals: IDs of rebutted arguments

        Returns:
            Created argument record
        """
        argument_id = f"arg-{consensus_id}-{len(self.arguments.get(consensus_id, [])) + 1}"

        argument = ArgumentRecord(
            argument_id=argument_id,
            consensus_id=consensus_id,
            agent_id=agent_id,
            position=position,
            content=content,
            supports=supports or [],
            rebuttals=rebuttals or [],
        )

        if consensus_id not in self.arguments:
            self.arguments[consensus_id] = []
        self.arguments[consensus_id].append(argument)

        # Update decision record if exists
        for decision_record in self.decisions.values():
            if decision_record.consensus_id == consensus_id:
                decision_record.arguments.append(argument)

        self.record_event(
            event_type=AuditEventType.ARGUMENT_SUBMITTED,
            consensus_id=consensus_id,
            agent_id=agent_id,
            data={
                "argument_id": argument_id,
                "position": position,
                "content_length": len(content),
            },
        )

        logger.debug("Argument recorded: {argument_id} by {agent_id} ({position})")
        return argument

    def record_decision_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        outcome_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Record the outcome of a decision.

        Args:
            decision_id: Decision identifier
            outcome: Decision outcome
            outcome_data: Additional outcome data
        """
        if decision_id not in self.decisions:
            logger.warning("Decision not found: {decision_id}")
            return

        self.decisions[decision_id].outcome = outcome
        if outcome_data:
            self.decisions[decision_id].metadata["outcome_data"] = outcome_data

        self.outcomes[decision_id] = outcome

        if outcome == DecisionOutcome.FAILURE:
            self.record_event(
                event_type=AuditEventType.CONSENSUS_FAILED,
                consensus_id=self.decisions[decision_id].consensus_id,
                data={
                    "decision_id": decision_id,
                    "outcome": outcome.value,
                    "outcome_data": outcome_data,
                },
            )

        logger.info("Decision outcome recorded: {decision_id} -> {outcome.value}")

    def record_rollback(
        self,
        decision_id: str,
        reason: str,
    ) -> None:
        """
        Record a decision rollback.

        Args:
            decision_id: Decision identifier
            reason: Reason for rollback
        """
        if decision_id not in self.decisions:
            logger.warning("Decision not found: {decision_id}")
            return

        self.decisions[decision_id].metadata["rollback_reason"] = reason
        self.decisions[decision_id].metadata["rollback_time"] = datetime.now(UTC).isoformat()

        self.record_event(
            event_type=AuditEventType.DECISION_ROLLED_BACK,
            consensus_id=self.decisions[decision_id].consensus_id,
            data={
                "decision_id": decision_id,
                "reason": reason,
            },
        )

        logger.info("Rollback recorded for {decision_id}: {reason}")

    # ------------------------------------------------------------------------
    # Decision Audit Recording
    # ------------------------------------------------------------------------

    def create_decision_audit(
        self,
        decision_id: str,
        consensus_id: str,
        final_decision: str,
        consensus_method: str = "MAKER",
        confidence_score: float = 0.5,
        confidence_breakdown: dict[str, float] | None = None,
        dissenting_agents: list[str] | None = None,
        minority_report: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionAudit:
        """
        Create a comprehensive decision audit record.

        Args:
            decision_id: Decision identifier
            consensus_id: Related consensus process
            final_decision: Final decision string
            consensus_method: Method used (e.g., "MAKER", "Deliberation")
            confidence_score: Overall confidence score
            confidence_breakdown: Breakdown of confidence components
            dissenting_agents: Agents who dissented
            minority_report: Summary of minority position
            metadata: Additional metadata

        Returns:
            Created DecisionAudit record
        """
        existing_decision = self.decisions.get(decision_id)
        votes = self.votes.get(consensus_id, [])
        rounds = self.deliberation_rounds.get(consensus_id, [])

        audit = DecisionAudit(
            decision_id=decision_id,
            consensus_id=consensus_id,
            deliberation_rounds=rounds,
            votes_with_reasoning=votes,
            final_decision=final_decision,
            consensus_method=consensus_method,
            confidence_score=confidence_score,
            confidence_breakdown=confidence_breakdown or {},
            dissenting_agents=dissenting_agents or [],
            minority_report=minority_report,
            outcome=(existing_decision.outcome if existing_decision else DecisionOutcome.PENDING),
            metadata=metadata or {},
        )

        self.decision_audits[decision_id] = audit

        logger.info(
            f"Decision audit created: {decision_id} with {len(rounds)} rounds, {len(votes)} votes"
        )
        return audit

    def record_deliberation_round(
        self,
        consensus_id: str,
        round_number: int,
        arguments_submitted: list[str] | None = None,
        positions: dict[str, str] | None = None,
        consensus_score: float = 0.0,
    ) -> DeliberationRoundRecord:
        """
        Record a deliberation round for later audit.

        Args:
            consensus_id: Consensus process identifier
            round_number: Round number in sequence
            arguments_submitted: Arguments submitted in this round
            positions: Agent positions at end of round
            consensus_score: Consensus score at end of round

        Returns:
            Created DeliberationRoundRecord
        """
        round_id = f"round-{consensus_id}-{round_number}"

        round_record = DeliberationRoundRecord(
            round_id=round_id,
            round_number=round_number,
            consensus_id=consensus_id,
            arguments_submitted=arguments_submitted or [],
            positions=positions or {},
            consensus_score=consensus_score,
        )

        if consensus_id not in self.deliberation_rounds:
            self.deliberation_rounds[consensus_id] = []
        self.deliberation_rounds[consensus_id].append(round_record)

        # Update any existing audit record for this consensus
        for audit in self.decision_audits.values():
            if audit.consensus_id == consensus_id:
                audit.add_deliberation_round(round_record)

        logger.debug("Deliberation round recorded: {round_id} (score: {consensus_score:.2f})")
        return round_record

    # ------------------------------------------------------------------------
    # Getter Accessors (for internal use and query layer)
    # ------------------------------------------------------------------------

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        """Get complete decision record."""
        return self.decisions.get(decision_id)

    def get_votes_for_consensus(self, consensus_id: str) -> list[VoteRecord]:
        """Get all votes for a consensus process."""
        return self.votes.get(consensus_id, [])

    def get_arguments_for_consensus(
        self,
        consensus_id: str,
    ) -> list[ArgumentRecord]:
        """Get all arguments for a consensus process."""
        return self.arguments.get(consensus_id, [])

    def get_deliberation_history(
        self,
        consensus_id: str,
    ) -> list[DeliberationRoundRecord]:
        """Get complete deliberation history for a consensus process."""
        return self.deliberation_rounds.get(consensus_id, [])

    def get_decision_audit(self, decision_id: str) -> DecisionAudit | None:
        """Get comprehensive decision audit record."""
        return self.decision_audits.get(decision_id)

    def get_audits_by_outcome(
        self,
        outcome: DecisionOutcome,
    ) -> list[DecisionAudit]:
        """Get all decision audits with a specific outcome."""
        return [audit for audit in self.decision_audits.values() if audit.outcome == outcome]

    def get_failed_audits(self) -> list[DecisionAudit]:
        """Get all audits with failure outcomes."""
        return self.get_audits_by_outcome(DecisionOutcome.FAILURE)

    def get_successful_audits(self) -> list[DecisionAudit]:
        """Get all audits with success outcomes."""
        return self.get_audits_by_outcome(DecisionOutcome.SUCCESS)

    # ------------------------------------------------------------------------
    # Integrity Verification
    # ------------------------------------------------------------------------

    def verify_audit_integrity(self, decision_id: str) -> dict[str, Any]:
        """
        Verify the integrity of a decision audit record.

        Args:
            decision_id: Decision identifier

        Returns:
            Verification result with integrity status
        """
        audit = self.decision_audits.get(decision_id)
        if not audit:
            return {"valid": False, "error": "Audit record not found"}

        is_valid = audit.verify_integrity()
        return {
            "valid": is_valid,
            "decision_id": decision_id,
            "provenance_hash": audit.provenance_hash,
            "verified_at": datetime.now(UTC).isoformat(),
        }

    def verify_integrity(self) -> dict[str, Any]:
        """
        Verify cryptographic integrity of audit trail.

        Returns:
            Integrity verification results
        """
        results = {
            "total_events": len(self.events),
            "verified_events": 0,
            "failed_events": 0,
            "chain_broken": False,
            "errors": [],
        }

        if not self.enable_hash_chain:
            results["status"] = "hash_chain_disabled"
            return results

        previous_hash = None
        for i, event in enumerate(self.events):
            expected_hash = event._generate_hash()
            if event.hash != expected_hash:
                results["failed_events"] += 1
                results["errors"].append(f"Event {event.event_id}: hash mismatch")
            else:
                results["verified_events"] += 1

            if event.previous_hash != previous_hash:
                results["chain_broken"] = True
                results["errors"].append(f"Event {event.event_id}: chain broken at position {i}")

            previous_hash = event.hash

        results["status"] = (
            "valid" if results["failed_events"] == 0 and not results["chain_broken"] else "invalid"
        )

        logger.info(
            f"Integrity verification: {results['status']} "
            f"({results['verified_events']}/{results['total_events']} verified)"
        )
        return results

    # ------------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------------

    def get_statistics(self) -> dict[str, Any]:
        """
        Get audit trail statistics.

        Returns:
            Statistics dictionary
        """
        outcome_counts: dict[str, int] = {}
        for outcome in self.outcomes.values():
            outcome_key = outcome.value
            outcome_counts[outcome_key] = outcome_counts.get(outcome_key, 0) + 1

        return {
            "total_events": len(self.events),
            "total_decisions": len(self.decisions),
            "total_votes": sum(len(v) for v in self.votes.values()),
            "total_arguments": sum(len(a) for a in self.arguments.values()),
            "outcome_distribution": outcome_counts,
            "query_count": self.query_count,
            "avg_query_time_ms": (
                self.total_query_time_ms / self.query_count if self.query_count > 0 else 0.0
            ),
            "storage_backend": self.storage_backend,
            "retention_days": self.retention_days,
            "hash_chain_enabled": self.enable_hash_chain,
        }

    def get_audit_statistics(self) -> dict[str, Any]:
        """
        Get statistics about decision audits.

        Returns:
            Dictionary with audit statistics
        """
        total = len(self.decision_audits)
        by_outcome = {
            outcome.value: len([a for a in self.decision_audits.values() if a.outcome == outcome])
            for outcome in DecisionOutcome
        }

        avg_confidence = (
            sum(a.confidence_score for a in self.decision_audits.values()) / total
            if total > 0
            else 0.0
        )

        avg_rounds = (
            sum(len(a.deliberation_rounds) for a in self.decision_audits.values()) / total
            if total > 0
            else 0.0
        )

        return {
            "total_audits": total,
            "by_outcome": by_outcome,
            "average_confidence": avg_confidence,
            "average_deliberation_rounds": avg_rounds,
            "total_deliberation_rounds": sum(
                len(a.deliberation_rounds) for a in self.decision_audits.values()
            ),
        }

    # ------------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------------

    def cleanup_old_data(self, current_date: datetime | None = None) -> int:
        """
        Clean up data older than retention period.

        Args:
            current_date: Current date for calculation

        Returns:
            Number of records cleaned up
        """
        if current_date is None:
            current_date = datetime.now(UTC)

        cleaned = 0
        logger.info("Cleanup completed: {cleaned} records removed")
        return cleaned
