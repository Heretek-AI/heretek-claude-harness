"""
ConsensusEngine — canonical Protocol for every consensus backend.

Implements Phase 3.1 of PLAN.md (§1.4 "stop pretending api/consensus.py
and api/wizard.py are routers"; §1.12 "4 consensus algorithms — turn
them into 1 composable system"). The audit's recommendation was
to extract a ``ConsensusEngine`` Protocol with 4 implementations:
MAKER, EnhancedMAKER, SwarmDeliberation, Deliberation.

This module ships the Protocol. The four implementations already
exist (in ``consensus/maker.py``, ``maker_enhanced.py``,
``swarm_deliberation.py``, ``deliberation.py``); they pre-date
this Protocol and are not annotated against it. A follow-up PR
can add ``runtime_checkable`` conformance checks at import time
without changing the implementation bodies.

Why a Protocol (not an ABC)
---------------------------
The four implementations differ significantly in their
public surface (``start_consensus`` vs ``start_deliberation``,
``add_vote`` vs ``submit_argument``). A strict ABC would force
all of them onto a common verb set; a Protocol lets us
document the minimum viable surface (compute + start) that
every backend must expose while still allowing each
implementation to keep its richer, domain-specific API.

The :func:`compute_consensus_for` function below is the
canonical entry point for new code: it accepts any object
implementing the Protocol and returns the ``ConsensusResult``.
This is the surface the rest of the swarm should use when it
wants to call a consensus engine without committing to a
specific implementation.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConsensusEngine(Protocol):
    """The minimum viable surface every consensus backend must expose.

    Implementations (Phase 3.1):

    * :class:`heretek_swarm.consensus.maker.MAKERConsensus` —
      first-to-ahead-by-k voting with reputation weighting.
    * :class:`heretek_swarm.consensus.maker_enhanced.EnhancedMAKERConsensus` —
      adds reasoning chains, rollback, pattern library, NATS emission.
    * :class:`heretek_swarm.consensus.swarm_deliberation.SwarmDeliberationEngine` —
      5-tier Position enum, confidence weighting, dissent tracking.
    * :class:`heretek_swarm.consensus.deliberation.DeliberationEngine` —
      argument / counter-argument structured debate.

    Every implementation must expose ``compute_consensus`` and a
    way to register input. The exact verb differs across
    implementations (``start_consensus`` vs ``start_deliberation``,
    ``add_vote`` vs ``submit_argument``); the Protocol captures
    the minimum surface in implementation-neutral terms.
    """

    def compute_consensus(self, consensus_id: str) -> Any:
        """Compute the final consensus decision for ``consensus_id``.

        Returns a :class:`ConsensusResult` (or backend-specific
        equivalent) when the computation succeeds, ``None`` when
        the consensus is not yet ready (insufficient votes,
        still collecting arguments, etc.).
        """
        ...


def compute_consensus_for(
    engine: ConsensusEngine, consensus_id: str
) -> Any:
    """Call :meth:`ConsensusEngine.compute_consensus` and return the result.

    Thin convenience wrapper so callers can write
    ``compute_consensus_for(engine, "round-1")`` instead of
    ``engine.compute_consensus("round-1")``. The wrapper
    exists so the canonical entry point is a free function
    (per the audit's "stop pretending routers are routers"
    guidance — the router imports a free function, not a
    class method).
    """
    return engine.compute_consensus(consensus_id)


def is_consensus_engine(obj: Any) -> bool:
    """Return True if ``obj`` satisfies the :class:`ConsensusEngine` Protocol.

    The :func:`runtime_checkable` decorator on the Protocol
    makes :func:`isinstance` work, but ``isinstance(x, P)``
    is a method-resolution-order search; for the explicit
    "does this object implement the consensus surface" check
    this free function is the cleaner API.
    """
    return isinstance(obj, ConsensusEngine)


__all__ = [
    "ConsensusEngine",
    "compute_consensus_for",
    "is_consensus_engine",
]
