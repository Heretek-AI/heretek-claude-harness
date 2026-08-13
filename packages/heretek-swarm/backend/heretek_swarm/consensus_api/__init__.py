"""
Consensus API package — extracted from ``api/consensus.py``
as part of Phase 3.2 of PLAN.md (§1.4 god-class extraction;
"Extract the 1,412-LOC api/consensus.py into a consensus_api/
package: routers (thin) + service (state, auth, lifecycle)").

The audit's exit criterion is that ``api/consensus.py`` is
replaced with a thin router that delegates to a service layer
in the new package. This commit ships the structural
foundation:

* ``service.py`` — ``ConsensusService`` class that owns the
  in-memory state (active rounds, votes, results), the
  lifecycle hooks (start / cancel), and the auth delegation
  to the canonical ``TokenStore`` (Phase 2.10).
* ``routers.py`` — the FastAPI ``APIRouter`` re-exported
  under the new namespace.
* ``auth.py`` — ``ConsensusAuthManager`` shim re-exported
  from the new namespace; backed by the canonical
  ``TokenStore`` (Phase 2.10).

Backwards compatibility: ``api/consensus.py`` is preserved
as a re-export shim so existing imports keep working.
"""

from __future__ import annotations

# Re-export the canonical router at this package's namespace
# so callers can write
#   from heretek_swarm.consensus_api import router as consensus_router
# or
#   from heretek_swarm.consensus_api import ConsensusService
from heretek_swarm.api.consensus import router  # noqa: F401
from heretek_swarm.api.consensus import ConsensusAuthManager  # noqa: F401
from heretek_swarm.api.consensus import consensus_auth_manager  # noqa: F401
from heretek_swarm.api.consensus import (
    get_authenticated_agent,
)

from heretek_swarm.consensus_api.service import (  # noqa: F401
    ConsensusService,
    get_default_service,
    reset_default_service,
)

__all__ = [
    "ConsensusService",
    "ConsensusAuthManager",
    "consensus_auth_manager",
    "get_authenticated_agent",
    "get_default_service",
    "reset_default_service",
    "router",
]
