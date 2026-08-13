"""heretek_swarm_core — Phase 4 of PLAN.md.

The sovereign service library for the Heretek Swarm. Phase 4
of the audit (§1.13 'Sovereign multi-package monorepo')
carves the core sub-packages out of the single heretek-swarm
package.

This package is the future home for:
  * actors/, mixins/, base/
  * consensus/, gateway/, runtime/
  * memory/, llm/, embeddings/
  * models/, schemas/, swarm_logging/
  * config/ (lib portion), utils/, validation/, channels/

Today (2026-06-03), the canonical code still lives under
``backend/heretek_swarm/``. This ``__init__.py`` re-exports
the public surface from there so the new package is a
drop-in namespace for new code; activating the actual
build (which would require this package to own the source
files) is a multi-PR effort.

The migration plan is captured in the audit:
  1. Move the sub-packages from ``backend/heretek_swarm/``
     into this directory (``packages/core/src/heretek_swarm_core/``).
  2. Update internal imports to use the new namespace.
  3. Add heretek-swarm-core to heretek-swarm-api's deps.
  4. Activate the workspace member in the root
     ``pyproject.toml``.

Until then, this ``__init__.py`` is the bridge: new code
can write ``from heretek_swarm_core import …`` and the
import resolves through the re-exports below.
"""

from __future__ import annotations

# Re-export the canonical public surface from the legacy
# monolith. New code that imports from heretek_swarm_core
# gets the same names as if it imported from heretek_swarm.
# When the actual move happens, the re-exports below are
# removed and the source files live in this package.
from heretek_swarm.actors.base.core import AgentActor, ActorMessage  # noqa: F401

# NOTE: ActorSupervisor is exposed lazily via __getattr__ at the bottom
# of this file. Eagerly importing it here would re-introduce the cycle
# that the backward-compat security/ shim had to work around (Task 3),
# and it will resurface when Task 4 moves consensus/ into this package.
from heretek_swarm.actors.factory import ActorFactory  # noqa: F401
from heretek_swarm_core.consensus import (  # noqa: F401
    MAKERConsensus,
    EnhancedMAKERConsensus,
    SwarmDeliberationEngine,
)
from heretek_swarm_core.consensus.deliberation import (  # noqa: F401
    DeliberationEngine,
)
from heretek_swarm_core.consensus.protocol import (  # noqa: F401
    ConsensusEngine,
    compute_consensus_for,
    is_consensus_engine,
)
from heretek_swarm.gateway.auth import (  # noqa: F401
    TokenStore,
    default_token_store,
    verify_auth,
    verify_jwt,
)
from heretek_swarm_core.memory import (  # noqa: F401
    MemoryStore,
    MemoryType,
    MemoryEntry,
    get_default_store,
)
from heretek_swarm_core.llm.headroom_compat import (  # noqa: F401
    HEADROOM_AVAILABLE,
    wrap as headroom_wrap,
    unwrap as headroom_unwrap,
)
from heretek_swarm_core.llm.hindsight_compat import (  # noqa: F401
    HindsightClient,
    HINDSIGHT_ENABLED as HINDSIGHT_AVAILABLE,
    HINDSIGHT_URL,
    get_hindsight_client,
)
from heretek_swarm.orchestration import (  # noqa: F401
    LangGraphHeavySwarmWorkflow,
    WorkflowPhase,
    WorkflowResult,
)

# NOTE: runtime.main_loop / runtime.wiring re-exports are lazy via
# __getattr__. They pull in actors.supervisor mid-import which cycles
# through actors.mixins -> collective -> consciousness -> fep_active
# _inference -> security. Same cycle ActorSupervisor hits; resolved by
# deferring the import.
from heretek_swarm_core.security.immune import (  # noqa: F401
    ImmuneResponseBuilding,
    ResponseOutcome,
)
from heretek_swarm_core.security.rate_limiter import (  # noqa: F401
    limiter,
    install_rate_limiter,
)

# NOTE: heretek_swarm.services re-exports cycle through
# consensus_api -> api -> api.consciousness -> collective.agency_tracking
# mid-import. Resolved via __getattr__.
from heretek_swarm_core.memory import *  # noqa: F401,F403
from heretek_swarm_core.embeddings import *  # noqa: F401,F403
from heretek_swarm_core.models import *  # noqa: F401,F403
from heretek_swarm_core.schemas import *  # noqa: F401,F403
from heretek_swarm_core.swarm_logging import *  # noqa: F401,F403
from heretek_swarm_core.utils import *  # noqa: F401,F403
from heretek_swarm_core.validation import *  # noqa: F401,F403

__all__ = [
    "AgentActor",
    "ActorMessage",
    "ActorSupervisor",
    "ActorFactory",
    "ActorOrchestrator",
    "AutonomousSwarm",
    "ConsensusEngine",
    "MAKERConsensus",
    "EnhancedMAKERConsensus",
    "SwarmDeliberationEngine",
    "DeliberationEngine",
    "compute_consensus_for",
    "is_consensus_engine",
    "TokenStore",
    "default_token_store",
    "verify_auth",
    "verify_jwt",
    "MemoryStore",
    "MemoryType",
    "MemoryEntry",
    "get_default_store",
    "HEADROOM_AVAILABLE",
    "headroom_wrap",
    "headroom_unwrap",
    "HindsightClient",
    "HINDSIGHT_AVAILABLE",
    "HINDSIGHT_URL",
    "get_hindsight_client",
    "LangGraphHeavySwarmWorkflow",
    "WorkflowPhase",
    "WorkflowResult",
    "wire_orchestrators",
    "thread_event_mesh_to_supervisor",
    "ImmuneResponseBuilding",
    "ResponseOutcome",
    "limiter",
    "install_rate_limiter",
    "ConsensusServiceStub",
    "MemoryServiceStub",
    "ObservabilityServiceStub",
    "RealtimeServiceStub",
]


# PEP 562 lazy module attribute. ``ActorSupervisor`` triggers a cycle:
# actors.supervisor -> mixins -> collective -> consciousness ->
# fep_active_inference, which loops back through this __init__.py when
# ``heretek_swarm.security`` is imported during the cycle.
#
# Eagerly importing it here was previously masked because Task 3 left
# security/ under backend/heretek_swarm/ — moving consensus/ (Task 4)
# will surface the cycle on every `import heretek_swarm_core`. Resolving
# it lazily keeps the public surface stable while breaking the loop
# at module-load time. `from heretek_swarm_core import ActorSupervisor`
# still works; it just costs one extra dict lookup on first access.
_LAZY_ATTRS = {
    "ActorSupervisor": ("heretek_swarm.actors.supervisor", "ActorSupervisor"),
    "AutonomousSwarm": ("heretek_swarm.runtime.main_loop", "AutonomousSwarm"),
    "wire_orchestrators": (
        "heretek_swarm.runtime.wiring",
        "wire_orchestrators",
    ),
    "thread_event_mesh_to_supervisor": (
        "heretek_swarm.runtime.wiring",
        "thread_event_mesh_to_supervisor",
    ),
    "ConsensusServiceStub": (
        "heretek_swarm.services",
        "ConsensusServiceStub",
    ),
    "MemoryServiceStub": ("heretek_swarm.services", "MemoryServiceStub"),
    "ObservabilityServiceStub": (
        "heretek_swarm.services",
        "ObservabilityServiceStub",
    ),
    "RealtimeServiceStub": ("heretek_swarm.services", "RealtimeServiceStub"),
}


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    target = _LAZY_ATTRS.get(name)
    if target is not None:
        module_path, attr_name = target
        import importlib

        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
