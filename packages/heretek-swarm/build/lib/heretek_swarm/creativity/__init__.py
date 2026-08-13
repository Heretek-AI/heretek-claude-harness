"""
Creativity Module for Heretek Swarm.

Provides creative thinking and lateral thinking capabilities:
- NovelConnectionEngine: Generates novel connections between concepts
- LateralThinkingMetricsTracker: Tracks lateral thinking metrics
- HarmfulContentFilter: Beta validation integration for content safety
"""

from heretek_swarm.creativity.novel_connections import (
    AssociationDistance,
    ConnectionTechnique,
    HarmfulContentFilter,
    LateralThinkingMetrics,
    LateralThinkingMetricsTracker,
    NovelConnection,
    NovelConnectionEngine,
    NoveltyLevel,
)

__all__ = [
    "AssociationDistance",
    "ConnectionTechnique",
    "HarmfulContentFilter",
    "LateralThinkingMetrics",
    "LateralThinkingMetricsTracker",
    "NovelConnection",
    "NovelConnectionEngine",
    "NoveltyLevel",
]
