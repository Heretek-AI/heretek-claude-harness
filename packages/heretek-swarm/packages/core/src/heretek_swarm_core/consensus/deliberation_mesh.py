"""
NATS Deliberation Mesh & HXA Connect debate lifecycle implementation.

Manages structured inter-agent deliberation streams and state transitions
(ACTIVE -> BLOCKED -> REVIEWING -> RESOLVED) over NATS event mesh.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

import structlog
from pydantic import BaseModel, Field

from heretek_swarm_core.consensus.audit_trail import ConsensusAuditTrail

if TYPE_CHECKING:
    from heretek_swarm_core.actors.validation import DeliberationRequest

logger = structlog.get_logger("NATSDeliberationMesh")


class _DeliberationRequestProtocol(Protocol):
    """Structural protocol for DeliberationRequest — breaks the actors cycle.

    DeliberationRequest lives in ``heretek_swarm_core.actors.validation``,
    which transitively pulls actors.supervisor at import time and cycles
    back through this package via security/fep_active_inference. To avoid
    that import-time cycle, we declare the attributes we actually use as a
    ``Protocol`` and import the concrete class only inside the call sites
    that need it (see ``_load_deliberation_request_class`` below).
    """

    deliberation_id: str
    topic: str
    triad_members: list[str]
    reason: str
    blocked_by: str
    reviewer_id: str
    consensus_score: float
    resolution: str
    dissenting_opinions: list[str]


def _load_deliberation_request_class() -> type:
    """Lazily resolve the concrete ``DeliberationRequest`` from actors.

    Imported inside a function so the actors package is only touched on
    first call rather than at module import time. Keeps the cycle at
    runtime (one-shot) instead of module-load (per-import).
    """
    from heretek_swarm_core.actors.validation import DeliberationRequest

    return DeliberationRequest


class HXADebateState(StrEnum):
    """Lifecycle states for HXA Connect debate cycles."""

    ACTIVE = "active"
    BLOCKED = "blocked"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"


_DELIBERATION_ID_PATTERN = r"^del_[0-9]{8}_[0-9]{6}$"


class DeliberationBlockedPayload(BaseModel):
    """Schema for blocking/suspending an active debate."""

    deliberation_id: str = Field(..., pattern=_DELIBERATION_ID_PATTERN)
    reason: str = Field(..., min_length=1, max_length=512)
    blocked_by: str = Field(..., min_length=1, max_length=128)


class DeliberationReviewingPayload(BaseModel):
    """Schema for placing a debate under tribunal/triad review."""

    deliberation_id: str = Field(..., pattern=_DELIBERATION_ID_PATTERN)
    reviewer_id: str = Field(..., min_length=1, max_length=128)


class DeliberationResolvedPayload(BaseModel):
    """Schema for successful debate consensus resolution."""

    deliberation_id: str = Field(..., pattern=_DELIBERATION_ID_PATTERN)
    resolution: str = Field(..., min_length=1, max_length=10000)
    consensus_score: float = Field(..., ge=0.0, le=1.0)
    dissenting_opinions: list[str] = Field(default_factory=list)


@dataclass
class HXADebateCycle:
    """Represents a structured inter-agent HXA Connect debate cycle."""

    deliberation_id: str
    topic: str
    participants: list[str]
    state: HXADebateState = HXADebateState.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    history: list[dict[str, Any]] = field(default_factory=list)

    def transition_to(self, new_state: HXADebateState, note: str | None = None) -> None:
        """Transition debate cycle to a new state and record in lineage history."""
        old_state = self.state
        self.state = new_state
        self.updated_at = datetime.now(UTC).isoformat()
        self.history.append(
            {
                "from": old_state,
                "to": new_state,
                "timestamp": self.updated_at,
                "note": note,
            }
        )
        logger.info(
            "hxa_debate_state_transition",
            deliberation_id=self.deliberation_id,
            from_state=old_state,
            to_state=new_state,
            note=note,
        )


class NATSDeliberationMesh:
    """
    Subscribes to NATS debate subjects, validates messages via Pydantic,
    governs debate cycle state machines, and records outcomes to the audit trail.
    """

    def __init__(
        self,
        event_mesh: Any,
        audit_trail: ConsensusAuditTrail | None = None,
    ) -> None:
        """
        Initialize the NATS Deliberation Mesh.

        Args:
            event_mesh: A NATSEventMesh or StubEventMesh instance
            audit_trail: Optional ConsensusAuditTrail instance
        """
        self.event_mesh = event_mesh
        self.audit_trail = audit_trail or ConsensusAuditTrail()
        self.active_debates: dict[str, HXADebateCycle] = {}
        self._subscriptions: list[str] = []

    async def start_listeners(self) -> None:
        """Subscribe to HXA Connect deliberation NATS subjects."""
        if not self.event_mesh:
            logger.warning("No event mesh provided, listeners not started")
            return

        subjects = {
            "deliberation.request": self._handle_deliberation_request,
            "deliberation.blocked": self._handle_deliberation_blocked,
            "deliberation.reviewing": self._handle_deliberation_reviewing,
            "deliberation.resolved": self._handle_deliberation_resolved,
        }

        for subj, handler in subjects.items():
            try:
                sid = await self.event_mesh.subscribe(subj, handler)
                if sid:
                    self._subscriptions.append(sid)
                logger.info("subscribed_to_deliberation_subject", subject=subj)
            except Exception as e:
                logger.error("deliberation_subscribe_failed", subject=subj, error=str(e))

    async def stop_listeners(self) -> None:
        """Unsubscribe from NATS debate subjects."""
        if not self.event_mesh or not self._subscriptions:
            return

        for sid in self._subscriptions:
            try:
                # StubEventMesh and NATSEventMesh may expose unsubscribe
                if hasattr(self.event_mesh, "unsubscribe"):
                    await self.event_mesh.unsubscribe(sid)
            except Exception as e:
                logger.debug("unsubscribe_failed", sid=sid, error=str(e))
        self._subscriptions.clear()

    async def _handle_deliberation_request(
        self,
        _mesh: Any,
        _subject: str,
        data: dict[str, Any],
    ) -> None:
        """Handle incoming deliberation initialization requests with strict Pydantic validation."""
        try:
            # Validate input schema strictly
            validated = _load_deliberation_request_class()(**data)
            delib_id = validated.deliberation_id

            if delib_id in self.active_debates:
                logger.warning("deliberation_already_exists", deliberation_id=delib_id)
                return

            # Initialize structured HXA debate in ACTIVE state
            cycle = HXADebateCycle(
                deliberation_id=delib_id,
                topic=validated.topic,
                participants=validated.triad_members,
                state=HXADebateState.ACTIVE,
            )
            self.active_debates[delib_id] = cycle

            # Log to structured audit trail
            self.audit_trail.record_event(
                event_type="deliberation_request_received",
                agent_id="NATSDeliberationMesh",
                details={
                    "deliberation_id": delib_id,
                    "topic": validated.topic,
                    "participants": validated.triad_members,
                },
            )

            # Broadcast cycle state change
            await self._broadcast_state_change(cycle)

        except Exception as e:
            logger.error("deliberation_request_handling_failed", error=str(e), payload=data)

    async def _handle_deliberation_blocked(
        self,
        _mesh: Any,
        _subject: str,
        data: dict[str, Any],
    ) -> None:
        """Handle incoming suspend/block events for a debate cycle."""
        try:
            validated = DeliberationBlockedPayload(**data)
            delib_id = validated.deliberation_id

            cycle = self.active_debates.get(delib_id)
            if not cycle:
                logger.warning("deliberation_not_found", deliberation_id=delib_id)
                return

            # Transition to BLOCKED
            cycle.transition_to(
                HXADebateState.BLOCKED,
                note=f"Blocked by {validated.blocked_by} due to: {validated.reason}",
            )

            # Log to audit trail
            self.audit_trail.record_event(
                event_type="deliberation_blocked",
                agent_id=validated.blocked_by,
                details={
                    "deliberation_id": delib_id,
                    "reason": validated.reason,
                },
            )

            await self._broadcast_state_change(cycle)

        except Exception as e:
            logger.error("deliberation_blocked_handling_failed", error=str(e), payload=data)

    async def _handle_deliberation_reviewing(
        self,
        _mesh: Any,
        _subject: str,
        data: dict[str, Any],
    ) -> None:
        """Handle transitioning a debate cycle to REVIEWING state."""
        try:
            validated = DeliberationReviewingPayload(**data)
            delib_id = validated.deliberation_id

            cycle = self.active_debates.get(delib_id)
            if not cycle:
                logger.warning("deliberation_not_found", deliberation_id=delib_id)
                return

            # Transition to REVIEWING
            cycle.transition_to(
                HXADebateState.REVIEWING,
                note=f"Placed under review by {validated.reviewer_id}",
            )

            self.audit_trail.record_event(
                event_type="deliberation_review_started",
                agent_id=validated.reviewer_id,
                details={"deliberation_id": delib_id},
            )

            await self._broadcast_state_change(cycle)

        except Exception as e:
            logger.error("deliberation_reviewing_handling_failed", error=str(e), payload=data)

    async def _handle_deliberation_resolved(
        self,
        _mesh: Any,
        _subject: str,
        data: dict[str, Any],
    ) -> None:
        """Handle consensus resolution, committing outcomes and cleanup."""
        try:
            validated = DeliberationResolvedPayload(**data)
            delib_id = validated.deliberation_id

            cycle = self.active_debates.get(delib_id)
            if not cycle:
                logger.warning("deliberation_not_found", deliberation_id=delib_id)
                return

            # Transition to RESOLVED
            cycle.transition_to(
                HXADebateState.RESOLVED,
                note=f"Resolved with consensus score {validated.consensus_score:.2f}",
            )

            # Persist decision to ConsensusAuditTrail
            self.audit_trail.record_decision(
                decision_id=delib_id,
                proposal=cycle.topic,
                rationale=validated.resolution,
                consensus_score=validated.consensus_score,
                agents_participating=len(cycle.participants),
            )

            # Log dissent / minority reports if present
            if validated.dissenting_opinions:
                self.audit_trail.record_event(
                    event_type="minority_report_filed",
                    agent_id="NATSDeliberationMesh",
                    details={
                        "deliberation_id": delib_id,
                        "dissenting_opinions": validated.dissenting_opinions,
                    },
                )

            await self._broadcast_state_change(cycle)

            # Clean up resolved debate cycle from hot memory
            del self.active_debates[delib_id]

        except Exception as e:
            logger.error("deliberation_resolved_handling_failed", error=str(e), payload=data)

    async def _broadcast_state_change(self, cycle: HXADebateCycle) -> None:
        """Publish cycle state change over NATS for mesh-wide synchronization."""
        if not self.event_mesh:
            return

        subject = f"deliberation.state_change.{cycle.deliberation_id}"
        payload = {
            "deliberation_id": cycle.deliberation_id,
            "topic": cycle.topic,
            "state": cycle.state,
            "updated_at": cycle.updated_at,
            "history": cycle.history,
        }

        try:
            await self.event_mesh.publish(subject, payload)
            logger.debug(
                "broadcasted_deliberation_state",
                subject=subject,
                state=cycle.state,
            )
        except Exception as e:
            logger.error("failed_to_broadcast_state_change", subject=subject, error=str(e))
