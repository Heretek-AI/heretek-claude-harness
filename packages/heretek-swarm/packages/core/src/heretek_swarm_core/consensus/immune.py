"""
Backwards-compat shim. The immune-response engine moved to
:mod:`heretek_swarm_core.security.immune` per Phase 2.11 of PLAN.md
(§1.12 — "4 consensus algorithms + immune" — immune is misfiled).

New code should import from ``heretek_swarm_core.security.immune``
directly. This module remains so existing
``from heretek_swarm_core.consensus.immune import …`` call sites
keep working unchanged.
"""

from __future__ import annotations

from heretek_swarm_core.security.immune import (  # noqa: F401
    AnomalyResponse,
    ImmuneLearningResult,
    ImmunePattern,
    ImmuneQuorum,
    ImmuneResponse,
    ImmuneResponseBuilding,
    ImmuneResponseEngine,
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
