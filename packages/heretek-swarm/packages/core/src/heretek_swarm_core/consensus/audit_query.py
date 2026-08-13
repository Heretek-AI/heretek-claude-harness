"""
Audit Query - Query, export, and analysis operations for consensus decisions.

This module contains the reading/querying side of the audit system:
- Decision querying with filters
- Vote breakdown analysis
- Timeline reconstruction
- Data export (JSON/CSV)
- Statistics and reporting

Recording is handled by audit_trail.py.
The audit_models.py module contains shared dataclass definitions.
"""

import json
from datetime import UTC, datetime
from typing import Any

import structlog

from .audit_models import (
    AuditEventType,
    DecisionOutcome,
    QueryResult,
)

logger = structlog.get_logger("ConsensusAuditQuery")


class AuditQueryMixin:
    """
    Query operations for the consensus audit system.

    This mixin provides all reading/querying methods on top of
    the storage managed by audit_trail.py (ConsensusAuditTrail).
    Inheriting classes should expose a `ConsensusAuditTrail` instance
    as `self` or provide these attribute references directly.
    """

    # Subclass must provide these attributes
    _trail: Any = None  # Reference to ConsensusAuditTrail instance

    def _get_trail(self) -> Any:
        """Get the audit trail instance (backwards-compatible)."""
        return self

    def query_decisions(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        consensus_type: str | None = None,
        min_confidence: float | None = None,
        outcome: DecisionOutcome | None = None,
        participants: list[str] | None = None,
    ) -> QueryResult:
        """
        Query decisions with filters.

        Args:
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)
            consensus_type: Filter by consensus type
            min_confidence: Filter by minimum confidence
            outcome: Filter by outcome
            participants: Filter by participants

        Returns:
            Query result
        """
        trail = self._get_trail()
        start_time = datetime.now(UTC)

        # Record query event
        trail.record_event(
            event_type=AuditEventType.AUDIT_QUERY,
            consensus_id="audit_system",
            data={
                "query_type": "decisions",
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "consensus_type": consensus_type,
                    "min_confidence": min_confidence,
                    "outcome": outcome.value if outcome else None,
                    "participants": participants,
                },
            },
        )

        # Filter decisions
        results = []
        for decision_id, record in trail.decisions.items():
            # Apply filters
            if start_date and record.start_time < start_date:
                continue
            if end_date and record.end_time and record.end_time > end_date:
                continue
            if min_confidence and record.confidence < min_confidence:
                continue
            if outcome and record.outcome != outcome:
                continue
            if participants and not any(p in record.participants for p in participants):
                continue

            # Add to results
            results.append(
                {
                    "decision_id": decision_id,
                    "consensus_id": record.consensus_id,
                    "proposal": record.proposal,
                    "decision": record.decision,
                    "confidence": record.confidence,
                    "outcome": record.outcome.value,
                    "participants": record.participants,
                    "start_time": record.start_time,
                    "end_time": record.end_time,
                    "vote_count": len(record.votes),
                    "argument_count": len(record.arguments),
                }
            )

        # Calculate execution time
        end_time = datetime.now(UTC)
        execution_time_ms = (end_time - start_time).total_seconds() * 1000

        # Update query statistics
        trail.query_count += 1
        trail.total_query_time_ms += execution_time_ms

        query_result = QueryResult(
            query={
                "start_date": start_date,
                "end_date": end_date,
                "consensus_type": consensus_type,
                "min_confidence": min_confidence,
                "outcome": outcome,
                "participants": participants,
            },
            total_results=len(results),
            results=results,
            execution_time_ms=execution_time_ms,
        )

        logger.info("Audit query completed: {len(results)} results in {execution_time_ms:.2f}ms")
        return query_result

    def get_vote_breakdown(self, consensus_id: str) -> dict[str, Any]:
        """
        Get vote breakdown for a consensus process.

        Args:
            consensus_id: Consensus identifier

        Returns:
            Vote breakdown dictionary
        """
        trail = self._get_trail()
        votes = trail.get_votes_for_consensus(consensus_id)

        if not votes:
            return {"total_votes": 0, "by_decision": {}, "by_agent": {}}

        # Group by decision
        by_decision: dict[str, list] = {}
        by_agent: dict[str, Any] = {}

        for vote in votes:
            if vote.decision not in by_decision:
                by_decision[vote.decision] = []
            by_decision[vote.decision].append(vote)
            by_agent[vote.agent_id] = vote

        return {
            "total_votes": len(votes),
            "by_decision": {
                decision: {
                    "count": len(v),
                    "avg_confidence": sum(vote_.confidence for vote_ in v) / len(v),
                    "votes": [
                        {
                            "agent_id": vote_.agent_id,
                            "confidence": vote_.confidence,
                            "reasoning": vote_.reasoning,
                        }
                        for vote_ in v
                    ],
                }
                for decision, v in by_decision.items()
            },
            "by_agent": {
                agent_id: {
                    "decision": vote.decision,
                    "confidence": vote.confidence,
                }
                for agent_id, vote in by_agent.items()
            },
        }

    def get_decision_timeline(self, consensus_id: str) -> list[dict[str, Any]]:
        """
        Get complete timeline of events for a consensus process.

        Args:
            consensus_id: Consensus identifier

        Returns:
            Timeline of events
        """
        trail = self._get_trail()
        timeline = []

        # Get all events for this consensus
        consensus_events = [e for e in trail.events if e.consensus_id == consensus_id]

        for event in consensus_events:
            timeline.append(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp,
                    "agent_id": event.agent_id,
                    "data": event.data,
                }
            )

        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])
        return timeline

    def export_audit_data(
        self,
        format: str = "json",
        consensus_id: str | None = None,
        include_events: bool = True,
        include_votes: bool = True,
        include_arguments: bool = True,
    ) -> dict[str, Any]:
        """
        Export audit data for external analysis.

        Args:
            format: Export format (json, csv)
            consensus_id: Optional specific consensus to export
            include_events: Include event log
            include_votes: Include vote records
            include_arguments: Include argument records

        Returns:
            Exported data dictionary
        """
        trail = self._get_trail()

        export_data: dict[str, Any] = {
            "export_timestamp": datetime.now(UTC).isoformat(),
            "format": format,
            "audit_trail_version": "1.0",
        }

        if consensus_id:
            # Export specific consensus
            decision = None
            for dec_record in trail.decisions.values():
                if dec_record.consensus_id == consensus_id:
                    decision = dec_record
                    break
            if decision:
                export_data["decisions"] = [
                    {
                        "decision_id": decision.decision_id,
                        "consensus_id": decision.consensus_id,
                        "proposal": decision.proposal,
                        "decision": decision.decision,
                        "confidence": decision.confidence,
                        "outcome": decision.outcome.value,
                        "participants": decision.participants,
                        "reasoning_summary": decision.reasoning_summary,
                        "start_time": decision.start_time,
                        "end_time": decision.end_time,
                        "metadata": decision.metadata,
                    }
                ]

            if include_votes:
                export_data["votes"] = [
                    {
                        "vote_id": v.vote_id,
                        "agent_id": v.agent_id,
                        "decision": v.decision,
                        "confidence": v.confidence,
                        "reasoning": v.reasoning,
                        "timestamp": v.timestamp,
                    }
                    for v in trail.get_votes_for_consensus(consensus_id)
                ]

            if include_arguments:
                export_data["arguments"] = [
                    {
                        "argument_id": a.argument_id,
                        "agent_id": a.agent_id,
                        "position": a.position,
                        "content": a.content,
                        "timestamp": a.timestamp,
                    }
                    for a in trail.get_arguments_for_consensus(consensus_id)
                ]

            if include_events:
                export_data["events"] = [
                    {
                        "event_id": e.event_id,
                        "event_type": e.event_type.value,
                        "timestamp": e.timestamp,
                        "agent_id": e.agent_id,
                        "data": e.data,
                    }
                    for e in trail.events
                    if e.consensus_id == consensus_id
                ]
        else:
            # Export all data
            export_data["decisions"] = [
                {
                    "decision_id": d.decision_id,
                    "consensus_id": d.consensus_id,
                    "proposal": d.proposal,
                    "decision": d.decision,
                    "confidence": d.confidence,
                    "outcome": d.outcome.value,
                    "participants": d.participants,
                    "start_time": d.start_time,
                    "end_time": d.end_time,
                }
                for d in trail.decisions.values()
            ]

            if include_events:
                export_data["events"] = [
                    {
                        "event_id": e.event_id,
                        "event_type": e.event_type.value,
                        "timestamp": e.timestamp,
                        "consensus_id": e.consensus_id,
                        "agent_id": e.agent_id,
                        "data": e.data,
                    }
                    for e in trail.events
                ]

        # Record export event
        trail.record_event(
            event_type=AuditEventType.DECISION_EXPORTED,
            consensus_id=consensus_id or "all",
            data={
                "format": format,
                "record_count": len(export_data.get("decisions", [])),
            },
        )

        logger.info("Audit data exported: {len(export_data.get('decisions', []))} decisions")
        return export_data

    def export_decision_audit(self, decision_id: str, format: str = "json") -> str:
        """
        Export a complete decision audit record.

        Args:
            decision_id: Decision identifier
            format: Export format ("json" supported)

        Returns:
            Exported audit data as string

        Raises:
            ValueError: If decision not found or invalid format
        """
        trail = self._get_trail()
        audit = trail.decision_audits.get(decision_id)
        if not audit:
            # Sanitize: do not log raw user-controlled decision_id
            logger.warning("Decision audit not found (ID hidden for security)")
            raise ValueError(f"Decision audit not found: {decision_id}")

        if format == "json":
            return json.dumps(audit.to_dict(), indent=2, sort_keys=True)
        raise ValueError(f"Unsupported export format: {format}")

    def export_all_audits(self, format: str = "json") -> str:
        """
        Export all decision audit records.

        Args:
            format: Export format ("json" supported)

        Returns:
            Exported audit data as string
        """
        trail = self._get_trail()
        if format == "json":
            data = {
                "export_timestamp": datetime.now(UTC).isoformat(),
                "total_audits": len(trail.decision_audits),
                "audits": [audit.to_dict() for audit in trail.decision_audits.values()],
            }
            return json.dumps(data, indent=2, sort_keys=True)
        raise ValueError(f"Unsupported export format: {format}")


# Standalone query functions for use with ConsensusAuditTrail
def query_decisions(
    trail: Any,
    start_date: str | None = None,
    end_date: str | None = None,
    consensus_type: str | None = None,
    min_confidence: float | None = None,
    outcome: DecisionOutcome | None = None,
    participants: list[str] | None = None,
) -> QueryResult:
    """Query decisions on a provided trail instance."""
    query = AuditQueryMixin()
    query._trail = trail
    return query.query_decisions(
        start_date=start_date,
        end_date=end_date,
        consensus_type=consensus_type,
        min_confidence=min_confidence,
        outcome=outcome,
        participants=participants,
    )


def export_audit_data(
    trail: Any,
    format: str = "json",
    consensus_id: str | None = None,
    include_events: bool = True,
    include_votes: bool = True,
    include_arguments: bool = True,
) -> dict[str, Any]:
    """Export audit data from a provided trail instance."""
    query = AuditQueryMixin()
    query._trail = trail
    return query.export_audit_data(
        format=format,
        consensus_id=consensus_id,
        include_events=include_events,
        include_votes=include_votes,
        include_arguments=include_arguments,
    )


def get_vote_breakdown(trail: Any, consensus_id: str) -> dict[str, Any]:
    """Get vote breakdown from a provided trail instance."""
    query = AuditQueryMixin()
    query._trail = trail
    return query.get_vote_breakdown(consensus_id)


def get_decision_timeline(trail: Any, consensus_id: str) -> list[dict[str, Any]]:
    """Get decision timeline from a provided trail instance."""
    query = AuditQueryMixin()
    query._trail = trail
    return query.get_decision_timeline(consensus_id)
