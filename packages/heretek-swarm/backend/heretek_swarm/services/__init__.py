"""
Sovereign services package — Phase 5 of PLAN.md (§1.13
'Graduated sovereign services — only pursue if 24/7 autonomy
pressure demands it').

This package holds the **skeleton stubs** for the four
services the audit recommended for extraction:

* :mod:`heretek_swarm.services.consensus_svc` — gRPC
  interface to the consensus engines
* :mod:`heretek_swarm.services.memory_svc` — gRPC/HTTP
  interface to the cognee + mem0 dual backend
* :mod:`heretek_swarm.services.realtime_svc` — WebSocket
  fan-out sidecar
* :mod:`heretek_swarm.services.observability_svc` —
  OpenTelemetry / opik sidecar

Each module is the in-process skeleton. The actual service
extraction (new Docker images, new gRPC servers, mTLS
auth) is queued for when the operational conditions in
``docs/SOVEREIGN_SERVICES.md`` are met.

The skeletons here are in-process: they expose the same
interface that the gRPC wrappers would expose, but
implemented as in-memory classes. Tests and the rest of
the swarm can call them today; flipping the switch to
real gRPC services is a deployment change, not a code
change.
"""

from __future__ import annotations

from heretek_swarm.services.consensus_svc import (  # noqa: F401
    ConsensusServiceStub,
    get_consensus_svc,
)
from heretek_swarm.services.memory_svc import (  # noqa: F401
    MemoryServiceStub,
    get_memory_svc,
)
from heretek_swarm.services.observability_svc import (  # noqa: F401
    ObservabilityServiceStub,
    get_observability_svc,
)
from heretek_swarm.services.realtime_svc import (  # noqa: F401
    RealtimeServiceStub,
    get_realtime_svc,
)


__all__ = [
    "ConsensusServiceStub",
    "MemoryServiceStub",
    "ObservabilityServiceStub",
    "RealtimeServiceStub",
    "get_consensus_svc",
    "get_memory_svc",
    "get_observability_svc",
    "get_realtime_svc",
]
