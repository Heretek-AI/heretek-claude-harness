"""
Immune-response system — anomaly detection and pattern preservation.

The immune-response engine was previously misfiled under
:mod:`heretek_swarm.consensus.immune` (PLAN.md §1.12 "4 consensus
algorithms + immune" — immune is misfiled). Phase 2.11 of PLAN.md
moves the implementation under the security umbrella where the
Sentinel / Sentinel-Prime / Arbiter mixins already consume it
(:mod:`heretek_swarm.actors.sentinel.immune`,
:mod:`heretek_swarm.actors.sentinel.anomaly`,
:mod:`heretek_swarm.actors.sentinel.agent`).

The implementation is split across two modules:
  - :mod:`heretek_swarm_core.security.immune_types` — the pure
    value-object surface (enums, dataclasses).
  - :mod:`heretek_swarm_core.security.immune_engine` — the two engine
    classes (``ImmuneResponseBuilding`` and ``ImmuneResponseEngine``).

This module re-exports the public surface so existing
``from heretek_swarm_core.security.immune import …`` call sites keep
working. ``from heretek_swarm.consensus.immune import …`` is also
preserved as a backwards-compat shim — that file now re-exports
from here.
"""

from __future__ import annotations

from heretek_swarm_core.security.immune_engine import (
    ImmuneResponseBuilding,
    ImmuneResponseEngine,
)
from heretek_swarm_core.security.immune_types import (
    AnomalyResponse,
    ImmuneLearningResult,
    ImmunePattern,
    ImmuneQuorum,
    ImmuneResponse,
    ImmuneStatus,
    NovelPatternPreservation,
    PatternClassification,
    ResponseAction,
    ResponseOutcome,
)

__all__ = [
    "AnomalyResponse",
    "ImmuneLearningResult",
    "ImmunePattern",
    "ImmuneQuorum",
    "ImmuneResponse",
    "ImmuneResponseBuilding",
    "ImmuneResponseEngine",
    "ImmuneStatus",
    "NovelPatternPreservation",
    "PatternClassification",
    "ResponseAction",
    "ResponseOutcome",
]
