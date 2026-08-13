"""
PerceiverPlus Module - Advanced Analytics Specialist.

This module provides the PerceiverPlusAgent for advanced multi-modal analytics
and pattern recognition. The module has been refactored into separate components:

- types.py: Type definitions (AnalyticsType, DataModality, StatisticalTest, AnalyticsResult, TrendAnalysis, CorrelationMatrix)  # noqa: E501
- analytics.py: Analytics mixin with helper methods (PerceiverAnalyticsMixinImpl)
- agent.py: Main PerceiverPlusAgent class

For backward compatibility, all public exports from the original perceiver_plus.py
are re-exported from this module.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

# Re-export agent from agent.py
from heretek_swarm.actors.perceiver_plus.agent import PerceiverPlusAgent

# Re-export analytics mixin from analytics.py
from heretek_swarm.actors.perceiver_plus.analytics import (
    PerceiverAnalyticsMixin,
    PerceiverAnalyticsMixinImpl,
)

# Re-export types from types.py
from heretek_swarm.actors.perceiver_plus.types import (
    AnalyticsResult,
    AnalyticsType,
    CorrelationMatrix,
    DataModality,
    StatisticalTest,
    TrendAnalysis,
)

__all__ = [
    # Types (enums and data classes)
    "AnalyticsResult",
    "AnalyticsType",
    "CorrelationMatrix",
    "DataModality",
    # Mixins
    "PerceiverAnalyticsMixin",
    "PerceiverAnalyticsMixinImpl",
    # Agent
    "PerceiverPlusAgent",
    "StatisticalTest",
    "TrendAnalysis",
]
