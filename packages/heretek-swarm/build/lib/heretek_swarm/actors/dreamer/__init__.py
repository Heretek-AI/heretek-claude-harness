"""
Dreamer Module - Creative Solution Generation & Divergent Thinking.

This module provides the DreamerAgent for creative ideation and divergent thinking.
The module has been refactored into separate components:

- types.py: Type definitions (CreativityTechnique, IdeaCategory, NoveltyLevel, etc.)
- generators.py: DreamerGeneratorsMixin for generation helpers
- agent.py: Main DreamerAgent class

For backward compatibility, all public exports from the original dreamer.py
are re-exported from this module.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

# Re-export agent from agent.py
from heretek_swarm.actors.dreamer.agent import DreamerAgent

# Re-export mixins and helpers from generators.py
from heretek_swarm.actors.dreamer.generators import (
    DreamerGeneratorsMixin,
    calculate_innovation_score,
    get_technique_prompt,
)

# Re-export types from types.py
from heretek_swarm.actors.dreamer.types import (
    CreativeIdea,
    CreativeSession,
    CreativityTechnique,
    IdeaCategory,
    InnovationReport,
    NoveltyLevel,
)

__all__ = [
    "CreativeIdea",
    "CreativeSession",
    # Types (enums and data classes)
    "CreativityTechnique",
    "DreamerAgent",
    "DreamerGeneratorsMixin",
    "IdeaCategory",
    "InnovationReport",
    "NoveltyLevel",
    # Generator helpers
    "calculate_innovation_score",
    "get_technique_prompt",
]
