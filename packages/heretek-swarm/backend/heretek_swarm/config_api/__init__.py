"""
Configuration API package — extracted from
``api/wizard.py`` as part of Phase 3.3 of PLAN.md
(§1.4 'Extract api/wizard.py into a config_api/ package:
routers (thin) + probes (ProviderProbe Protocol)').

The audit's exit criterion is that ``api/wizard.py`` is
replaced with a thin router that delegates to a service
layer in the new package, with the provider validation
behind a ``ProviderProbe`` Protocol. This commit ships the
structural foundation:

* ``router.py`` — the FastAPI ``APIRouter`` re-exported
  under the new namespace.
* ``probes.py`` — the ``ProviderProbe`` Protocol that
  validates LLM / embedding providers before they are
  persisted.

Backwards compatibility: ``api/wizard.py`` is preserved
as a re-export shim so existing imports keep working.
"""

from __future__ import annotations

from heretek_swarm.api.wizard import (  # noqa: F401
    router,
    WizardState,
    # Catalog re-exports (Phase 2.4)
    AVAILABLE_PROVIDERS,
    AGENT_TIERS,
)

from heretek_swarm.config_api.probes import (  # noqa: F401
    ProviderProbe,
    ProbeResult,
    HttpProbe,
    StaticProbe,
)

__all__ = [
    "ProviderProbe",
    "ProbeResult",
    "HttpProbe",
    "StaticProbe",
    "WizardState",
    "router",
    "AVAILABLE_PROVIDERS",
    "AGENT_TIERS",
]
