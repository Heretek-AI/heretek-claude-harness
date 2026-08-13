"""
Explorer Module - Intelligence Gathering Specialist

This module provides the ExplorerAgent for intelligence gathering,
opportunity discovery, and anomaly detection.

For backward compatibility, this module re-exports from the new package structure.
Import paths like `from heretek_swarm.actors.explorer import ExplorerAgent` continue to work.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

# Re-export agent class for backward compatibility
from heretek_swarm.actors.explorer.agent import ExplorerAgent

# Re-export pathfinding mixins
from heretek_swarm.actors.explorer.pathfinding import ExplorerPathfindingMixins

# Re-export types for backward compatibility
from heretek_swarm.actors.explorer.types import (
    Anomaly,
    AnomalyType,
    IntelligenceReport,
    Opportunity,
    OpportunityType,
    Pattern,
    ResearchProgress,
    ResearchState,
    ThreatLevel,
)

__all__ = [
    "Anomaly",
    "AnomalyType",
    # Main agent class
    "ExplorerAgent",
    # Mixin for pathfinding
    "ExplorerPathfindingMixins",
    "IntelligenceReport",
    "Opportunity",

    "OpportunityType",
    "Pattern",
    "ResearchProgress",
    "ResearchState",
    "ThreatLevel",
]
