"""
Prism Agent Module - Multi-Perspective Analysis & Bias Detection.

This module provides the Prism agent for multi-perspective analysis and cognitive
bias detection. The module has been refactored into separate components:

- types.py: Type definitions (PerspectiveType, BiasType, etc.)
- transforms.py: Transformation and heuristic logic
- agent.py: Main PrismAgent class

For backward compatibility, all public exports from the original prism.py are
re-exported from this module.
"""

from __future__ import annotations

# Re-export agent from agent.py
from heretek_swarm.actors.prism.agent import PrismAgent

# Re-export transform utilities
from heretek_swarm.actors.prism.transforms import (
    PrismTransforms,
    apply_framework_fallback,
    detect_biases_heuristic,
    generate_heuristic_perspective,
    generate_reframe_fallback,
    generate_stakeholder_map_fallback,
    get_framework_prompt,
)

# Re-export types from types.py
from heretek_swarm.actors.prism.types import (
    AnalyticalFramework,
    BiasDetection,
    BiasType,
    Perspective,
    PerspectiveType,
)

__all__ = [
    "AnalyticalFramework",
    "BiasDetection",
    "BiasType",
    "Perspective",
    # Types
    "PerspectiveType",
    # Agent
    "PrismAgent",
    # Transforms
    "PrismTransforms",
    "apply_framework_fallback",
    "detect_biases_heuristic",
    "generate_heuristic_perspective",
    "generate_reframe_fallback",
    "generate_stakeholder_map_fallback",
    "get_framework_prompt",
]
