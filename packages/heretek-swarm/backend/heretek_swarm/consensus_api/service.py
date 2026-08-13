"""
ConsensusService — the state and lifecycle layer for the
consensus API.

Implements Phase 3.2 of PLAN.md (§1.4 god-class extraction —
the consensus router was 1,412 LOC and held both routing and
state. The audit's recommendation was to extract the state
into a service layer so the router can be thin).

This module ships the initial service layer with a focused
responsibility: it owns the in-memory active-rounds
dictionary and the per-round vote / result aggregation, with
methods that the router can delegate to. The router in
``api/consensus.py`` still owns the request/response shape
and FastAPI dependencies; the service is the canonical place
where the state and lifecycle live.

Backwards compatibility: this module is additive. The
existing ``_consensus_store`` module-level dict in
``api/consensus.py`` is preserved until the routes are
migrated to delegate to the service (queued behind a
follow-up PR).
"""

from __future__ import annotations

import secrets
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ConsensusService:
    """In-memory state and lifecycle for consensus rounds.

    Each instance owns:

    * ``active_rounds`` — the dict of round_id → round state
    * ``votes`` — round_id → {agent_id: vote}
    * ``results`` — round_id → final result
    * ``audit`` — append-only list of state-change events
    """

    def __init__(self) -> None:
        self.active_rounds: dict[str, dict[str, Any]] = {}
        self.votes: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.results: dict[str, dict[str, Any]] = {}
        self.audit: list[dict[str, Any]] = []
        self._token_expiry = 24 * 60 * 60  # 24h in seconds

    # ------------------------------------------------------------------
    # Round lifecycle
    # ------------------------------------------------------------------

    def start_round(
        self,
        topic: str,
        *,
        participants: list[str],
        consensus_id: str | None = None,
    ) -> str:
        """Create a new round in the ``VOTING`` state.

        Returns the round id. If ``consensus_id`` is provided,
        it is used (callers usually want to control the id);
        otherwise a random one is generated.
        """
        cid = consensus_id or secrets.token_urlsafe(16)
        now = datetime.now(UTC)
        self.active_rounds[cid] = {
            "consensus_id": cid,
            "topic": topic,
            "participants": participants,
            "state": "VOTING",
            "votes": {},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self._audit(
            "start_round",
            consensus_id=cid,
            topic=topic,
            participants=participants,
        )
        return cid

    def submit_vote(
        self,
        consensus_id: str,
        agent_id: str,
        decision: str,
        confidence: float,
    ) -> bool:
        """Record a vote for ``agent_id`` on ``consensus_id``.

        Returns True if the vote was accepted, False if the
        round is unknown or already terminal.
        """
        round_ = self.active_rounds.get(consensus_id)
        if round_ is None:
            return False
        if round_["state"] not in ("VOTING", "AGGREGATING"):
            return False
        if agent_id not in round_["participants"]:
            return False
        round_["votes"][agent_id] = {
            "decision": decision,
            "confidence": confidence,
            "voted_at": datetime.now(UTC).isoformat(),
        }
        round_["updated_at"] = datetime.now(UTC).isoformat()
        self._audit(
            "submit_vote",
            consensus_id=consensus_id,
            agent_id=agent_id,
            decision=decision,
            confidence=confidence,
        )
        return True

    def aggregate(self, consensus_id: str) -> dict[str, Any] | None:
        """Aggregate the votes and return the result, or
        ``None`` if the round is unknown.

        The aggregation is a simple plurality — the decision
        with the highest weighted confidence wins. The audit
        noted that the canonical aggregation is performed by
        the MAKERConsensus / EnhancedMAKERConsensus engines
        (see ``api.consensus:497`` after the Phase 0.1 fix);
        this method is the lightweight in-service aggregation
        used when those engines are not present.
        """
        round_ = self.active_rounds.get(consensus_id)
        if round_ is None:
            return None
        if not round_["votes"]:
            return None

        # Weighted plurality
        totals: dict[str, float] = defaultdict(float)
        for vote in round_["votes"].values():
            totals[vote["decision"]] += vote.get("confidence", 0.0)
        if not totals:
            return None
        decision = max(totals, key=lambda k: totals[k])
        result = {
            "consensus_id": consensus_id,
            "decision": decision,
            "score": totals[decision] / max(1.0, sum(totals.values())),
            "votes": dict(round_["votes"]),
            "completed_at": datetime.now(UTC).isoformat(),
        }
        self.results[consensus_id] = result
        round_["state"] = "COMPLETED"
        round_["updated_at"] = result["completed_at"]
        self._audit(
            "aggregate",
            consensus_id=consensus_id,
            decision=decision,
            score=result["score"],
        )
        return result

    def cancel(self, consensus_id: str) -> bool:
        """Mark the round as cancelled. Returns True if the
        round was known and the state changed."""
        round_ = self.active_rounds.get(consensus_id)
        if round_ is None:
            return False
        round_["state"] = "CANCELLED"
        round_["updated_at"] = datetime.now(UTC).isoformat()
        self._audit("cancel", consensus_id=consensus_id)
        return True

    def list_active(self) -> list[dict[str, Any]]:
        """Return the active (VOTING / AGGREGATING) rounds."""
        return [
            dict(r)
            for r in self.active_rounds.values()
            if r["state"] in ("VOTING", "AGGREGATING")
        ]

    def get(self, consensus_id: str) -> dict[str, Any] | None:
        """Return a single round, or ``None`` if unknown."""
        return self.active_rounds.get(consensus_id)

    def get_result(self, consensus_id: str) -> dict[str, Any] | None:
        """Return the aggregated result for ``consensus_id``,
        or ``None`` if no result has been computed yet."""
        return self.results.get(consensus_id)

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _audit(self, event: str, **fields: Any) -> None:
        self.audit.append(
            {
                "event": event,
                "timestamp": datetime.now(UTC).isoformat(),
                **fields,
            }
        )


# Module-level default service. New code should call
# ``get_default_service()`` to allow tests to inject a private
# instance; the module-level singleton is for the production
# FastAPI app.
_default: ConsensusService | None = None


def get_default_service() -> ConsensusService:
    """Return the process-wide :class:`ConsensusService`."""
    global _default
    if _default is None:
        _default = ConsensusService()
    return _default


def reset_default_service() -> None:
    """Clear the cached default service (used by tests)."""
    global _default
    _default = None


__all__ = [
    "ConsensusService",
    "get_default_service",
    "reset_default_service",
]
