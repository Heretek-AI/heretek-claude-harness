"""
Consensus service stub — Phase 5.1 of PLAN.md.

In-process skeleton for the future gRPC consensus service.
The stub exposes the same shape the gRPC service would
expose (CreateRound, AddVote, Compute, StreamRounds) but
runs in the same process. Tests and the rest of the swarm
can call it today; flipping the switch to a real gRPC
service is a deployment change, not a code change.

The stub delegates to the existing ``consensus_api.service.ConsensusService``
(Phase 3.2) so behavior matches the in-process consensus
router exactly.

The wire format (gRPC protobuf) is captured in
``docs/SOVEREIGN_SERVICES.md`` (Phase 5.1). Activating
the gRPC service means:

  1. Generate Python stubs from the .proto in
     ``docs/SOVEREIGN_SERVICES.md``.
  2. Replace the in-process ``compute_consensus`` call
     with a gRPC client call.
  3. Deploy a new Docker image
     ``heretek-swarm-consensus-svc`` running the gRPC
     server (which uses this module as its implementation).

The exit criterion for activating 5.1 is in
``docs/SOVEREIGN_SERVICES.md``: synthetic load test
demonstrates p99 consensus latency in the monolith is
unacceptable, AND the gRPC interface passes a side-by-side
parity test against the monolith for 1 week.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from heretek_swarm.consensus_api import (
    ConsensusService as _InProcessService,
    get_default_service,
)


@dataclass
class ConsensusRequest:
    """Wire-format request for ``CreateRound``.

    Mirrors the gRPC ``CreateRoundRequest`` captured in
    ``docs/SOVEREIGN_SERVICES.md``.
    """

    topic: str
    participants: list[str]
    consensus_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResponse:
    """Wire-format response for ``CreateRound`` and
    ``Compute``."""

    consensus_id: str
    state: str
    decision: str | None = None
    score: float | None = None
    votes: dict[str, Any] = field(default_factory=dict)


class ConsensusServiceStub:
    """In-process skeleton for the future gRPC consensus
    service.

    Public surface:

    * ``create_round(request)`` → ``ConsensusResponse``
    * ``add_vote(consensus_id, agent_id, decision, confidence)``
    * ``compute(consensus_id)`` → ``ConsensusResponse``
    * ``stream_rounds()`` → async iterator of
      ``ConsensusResponse``
    * ``cancel(consensus_id)`` → bool

    Delegates to ``heretek_swarm.consensus_api.ConsensusService``
    so behavior matches the in-process consensus router
    exactly.
    """

    def __init__(self, service: _InProcessService | None = None) -> None:
        self._service = service or get_default_service()

    async def create_round(self, request: ConsensusRequest) -> ConsensusResponse:
        cid = self._service.start_round(
            topic=request.topic,
            participants=request.participants,
            consensus_id=request.consensus_id,
        )
        return ConsensusResponse(consensus_id=cid, state="VOTING")

    async def add_vote(
        self,
        consensus_id: str,
        agent_id: str,
        decision: str,
        confidence: float,
    ) -> ConsensusResponse:
        ok = self._service.submit_vote(
            consensus_id, agent_id, decision, confidence
        )
        if not ok:
            return ConsensusResponse(
                consensus_id=consensus_id, state="REJECTED"
            )
        return ConsensusResponse(consensus_id=consensus_id, state="ACCEPTED")

    async def compute(self, consensus_id: str) -> ConsensusResponse:
        result = self._service.aggregate(consensus_id)
        if result is None:
            return ConsensusResponse(
                consensus_id=consensus_id, state="UNKNOWN"
            )
        return ConsensusResponse(
            consensus_id=consensus_id,
            state="COMPLETED",
            decision=result["decision"],
            score=result["score"],
            votes=result["votes"],
        )

    async def stream_rounds(self) -> Any:
        """Async iterator over the active rounds.

        The gRPC counterpart is a server-streaming RPC; the
        in-process stub returns the current snapshot as
        a single batch.
        """
        for r in self._service.list_active():
            yield ConsensusResponse(
                consensus_id=r["consensus_id"],
                state=r["state"],
            )

    async def cancel(self, consensus_id: str) -> bool:
        return self._service.cancel(consensus_id)


_singleton: ConsensusServiceStub | None = None


def get_consensus_svc() -> ConsensusServiceStub:
    """Return the process-wide :class:`ConsensusServiceStub`."""
    global _singleton
    if _singleton is None:
        _singleton = ConsensusServiceStub()
    return _singleton


__all__ = [
    "ConsensusServiceStub",
    "ConsensusRequest",
    "ConsensusResponse",
    "get_consensus_svc",
]
