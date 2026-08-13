"""
Composable initializers for AutonomousSwarm.

Implements Phase 2.6 of PLAN.md (§1.4 god-class
extraction; the audit's exit criterion is
"runtime/main_loop.py into composable initializers; replace
_rewire_orchestrator_refs post-hoc patching with
constructor injection").

Each module in this package owns one initialization
concern. The free functions take the swarm instance and
configure it; the main_loop method delegates to the
function. The full constructor-injection refactor
(touching every orchestrator) is queued behind a
follow-up; this commit ships the structural decomposition.

The available initializers are:

* :mod:`.channel_registry` — channel + group registries
* :mod:`.memory` — cognee reader + writer
* :mod:`.rag` — RAG retriever
* :mod:`.consensus` — MAKERConsensus engine
* :mod:`.event_mesh` — NATS event mesh
* :mod:`.jetstream` — JetStream streams
* :mod:`.mcp_tools` — MCP tools + registry bridge
* :mod:`.supervisor` — ActorSupervisor
* :mod:`.model_garage` — ModelGarage + global install
* :mod:`.election_manager` — Raft-based ElectionManager
"""

from __future__ import annotations

from heretek_swarm.runtime.initializers import (  # noqa: F401
    channel_registry,
    consensus,
    election_manager,
    event_mesh,
    jetstream,
    mcp_tools,
    memory,
    model_garage,
    rag,
    supervisor,
)
from heretek_swarm.runtime.initializers.channel_registry import (  # noqa: F401
    initialize_channel_registry,
)
from heretek_swarm.runtime.initializers.consensus import (  # noqa: F401
    initialize_consensus,
)
from heretek_swarm.runtime.initializers.election_manager import (  # noqa: F401
    initialize_election_manager,
)
from heretek_swarm.runtime.initializers.event_mesh import (  # noqa: F401
    initialize_event_mesh,
)
from heretek_swarm.runtime.initializers.jetstream import (  # noqa: F401
    initialize_jetstream,
)
from heretek_swarm.runtime.initializers.mcp_tools import (  # noqa: F401
    initialize_mcp_tools,
)
from heretek_swarm.runtime.initializers.memory import (  # noqa: F401
    initialize_memory,
)
from heretek_swarm.runtime.initializers.model_garage import (  # noqa: F401
    initialize_model_garage,
)
from heretek_swarm.runtime.initializers.rag import (  # noqa: F401
    initialize_rag,
)
from heretek_swarm.runtime.initializers.supervisor import (  # noqa: F401
    initialize_supervisor,
)

__all__ = [
    "channel_registry",
    "consensus",
    "election_manager",
    "event_mesh",
    "jetstream",
    "mcp_tools",
    "memory",
    "model_garage",
    "rag",
    "supervisor",
    "initialize_channel_registry",
    "initialize_consensus",
    "initialize_election_manager",
    "initialize_event_mesh",
    "initialize_jetstream",
    "initialize_mcp_tools",
    "initialize_memory",
    "initialize_model_garage",
    "initialize_rag",
    "initialize_supervisor",
]
