"""heretek_swarm_api — Phase 4 of PLAN.md.

The FastAPI HTTP surface for the Heretek Swarm. Phase 4 of
the audit (§1.13) carves the api sub-packages out of the
single heretek-swarm package.

This package is the future home for:
  * api/ — FastAPI application + 22+ routers
  * observability/ (router portion) — alerting, db_timing,
    metrics, prometheus_metrics, timing
  * security/ (auth portion) — zero_trust middleware,
    adversarial detection, ddos_protection, etc.
  * mcp/, integrations/, plugins/
  * rag/ (orchestration-specific bits)
  * agents/ — agent registration HTTP

Today (2026-06-03), the canonical code still lives under
``backend/heretek_swarm/``. This ``__init__.py`` re-exports
the public surface from there so the new package is a
drop-in namespace.

The full migration is queued behind a multi-PR effort
(touches every router + middleware). The structural
foundation in this commit ships the namespace, the
pyproject.toml stub, and the re-export bridge.
"""

from __future__ import annotations

# Re-export the canonical public surface from the legacy
# monolith. New code that imports from heretek_swarm_api
# gets the same names as if it imported from heretek_swarm.
from heretek_swarm.api.main import app  # noqa: F401

# Re-export the per-entity router objects
from heretek_swarm.api import (  # noqa: F401
    deliberation as deliberation_module,
)
from heretek_swarm.consensus_api import (  # noqa: F401
    router as consensus_router,
    ConsensusService,
)
from heretek_swarm_api.realtime import (  # noqa: F401
    WebSocketAuthManager,
    ConnectionManager,
    manager as ws_manager,
)
from heretek_swarm.config_api import (  # noqa: F401
    ProviderProbe,
    HttpProbe,
    StaticProbe,
    ProbeResult,
    router as wizard_router,
    AVAILABLE_PROVIDERS,
    AGENT_TIERS,
)
from heretek_swarm_core.security.rate_limiter import (  # noqa: F401
    limiter,
    install_rate_limiter,
)

__all__ = [
    "app",
    "deliberation_module",
    "consensus_router",
    "ConsensusService",
    "WebSocketAuthManager",
    "ConnectionManager",
    "ws_manager",
    "ProviderProbe",
    "HttpProbe",
    "StaticProbe",
    "ProbeResult",
    "wizard_router",
    "AVAILABLE_PROVIDERS",
    "AGENT_TIERS",
    "limiter",
    "install_rate_limiter",
]
