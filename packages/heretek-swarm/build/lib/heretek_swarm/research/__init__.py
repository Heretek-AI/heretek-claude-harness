"""
Research Tier — Consciousness, Emergence, and Evolved Behavior Code.

.. deprecated::
    This package re-exports from :mod:`heretek_swarm.consciousness` and
    :mod:`heretek_swarm.collective` for backward compatibility. Per
    PLAN.md §M-arch PR #8, the production runtime no longer pays the
    cost of consciousness / emergence / evolution code — the original
    audit found that the 22,979 LOC of code in those modules is
    either research code dressed as production runtime (the IIT phi
    computation is intractable in the general case) or aspirational
    telemetry (values are computed and reported to the dashboard but
    do not actuate any behavior change).

    New code should treat these modules as research-only and avoid
    importing them from production hot paths. A follow-up PR will
    physically move the code; this PR creates the namespace and
    adds deprecation markers.

M-arch PR #8: extract IIT/FEP/GWT/emergent-detection/evolution to
``heretek_swarm.research/``. The submodules are re-exported so
existing imports keep working during the transition.
"""

from __future__ import annotations

from heretek_swarm.collective import (
    agency_tracking,
    emergence_analyzer,
    emergent_detection,
    emergent_detection_types,
    evolution_engine,
)
from heretek_swarm.consciousness import (
    ast,
    fep,
    fep_active_inference,
    gwt,
    gwt_deliberation,
    iit,
    iit_phi,
    introspection,
    self_model,
)

__all__ = [
    "agency_tracking",
    "ast",
    "emergence_analyzer",
    "emergent_detection",
    "emergent_detection_types",
    "evolution_engine",
    "fep",
    "fep_active_inference",
    "gwt",
    "gwt_deliberation",
    "iit",
    "iit_phi",
    "introspection",
    "self_model",
]
