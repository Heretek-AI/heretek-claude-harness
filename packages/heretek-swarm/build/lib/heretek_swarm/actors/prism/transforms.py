"""
Prism Transforms - Transformation and heuristic logic.

This module contains transformation logic for the Prism agent:
- Heuristic perspective generation
- Pattern-based bias detection
- Framework-specific prompts and processing

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from typing import Any

import structlog

from heretek_swarm.actors.prism.types import (
    AnalyticalFramework,
    BiasDetection,
    BiasType,
    Perspective,
    PerspectiveType,
)

logger = structlog.get_logger(__name__)

# Perspective-specific heuristic templates
VIEWPOINT_TEMPLATES: dict[PerspectiveType, str] = {
    PerspectiveType.TECHNICAL: "From a technical standpoint, this issue involves implementation considerations...",  # noqa: E501
    PerspectiveType.USER: "From a user perspective, the key concerns are usability and experience...",  # noqa: E501
    PerspectiveType.BUSINESS: "From a business perspective, we must consider cost-benefit and ROI...",  # noqa: E501
    PerspectiveType.SECURITY: "From a security perspective, we need to evaluate risks and vulnerabilities...",  # noqa: E501
    PerspectiveType.ETHICAL: "From an ethical perspective, we should consider moral implications...",  # noqa: E501
    PerspectiveType.LONG_TERM: "From a long-term perspective, we need to consider future impacts...",  # noqa: E501
    PerspectiveType.SHORT_TERM: "From a short-term perspective, immediate concerns include...",
    PerspectiveType.STAKEHOLDER: "From a stakeholder perspective, multiple parties are affected...",
    PerspectiveType.SYSTEMS: "From a systems perspective, we must analyze interconnections...",
    PerspectiveType.FIRST_PRINCIPLES: "From first principles, we break this down to fundamental truths...",  # noqa: E501
}


# Framework-specific prompts for LLM processing
FRAMEWORK_PROMPTS: dict[AnalyticalFramework, str] = {
    AnalyticalFramework.FIRST_PRINCIPLES: """Break down this issue to first principles:

ISSUE: {issue}

Identify:
1. Fundamental truths that are certain
2. Assumptions that can be questioned
3. Core components without analogy
4. Reconstruction from basics

Respond in JSON:
{{
    "fundamental_truths": ["...", "..."],
    "questionable_assumptions": ["...", "..."],
    "core_components": ["...", "..."],
    "reconstruction": "..."
}}""",
    AnalyticalFramework.SYSTEMS_THINKING: """Analyze this issue using systems thinking:

ISSUE: {issue}

Identify:
1. System elements and components
2. Interconnections and relationships
3. Feedback loops (reinforcing/balancing)
4. System boundaries
5. Leverage points for intervention

Respond in JSON:
{{
    "elements": ["...", "..."],
    "interconnections": ["...", "..."],
    "feedback_loops": ["...", "..."],
    "boundaries": "...",
    "leverage_points": ["...", "..."]
}}""",
    AnalyticalFramework.PRE_MORTEM: """Conduct a pre-mortem analysis for this issue:

ISSUE: {issue}

Imagine the solution has failed spectacularly. Identify:
1. What caused the failure
2. Early warning signs that were missed
3. Prevention strategies
4. Mitigation plans

Respond in JSON:
{{
    "failure_causes": ["...", "..."],
    "warning_signs": ["...", "..."],
    "prevention_strategies": ["...", "..."],
    "mitigation_plans": ["...", "..."]
}}""",
    AnalyticalFramework.STAKEHOLDER_IMPACT: """Analyze stakeholder impacts for this issue:

ISSUE: {issue}

Identify:
1. All affected stakeholders
2. Impact on each stakeholder (positive/negative)
3. Stakeholder interests and concerns
4. Trade-offs between stakeholders

Respond in JSON:
{{
    "stakeholders": ["...", "..."],
    "impacts": {{"stakeholder": "impact"}},
    "interests": {{"stakeholder": "interest"}},
    "trade_offs": ["...", "..."]
}}""",
}


# Bias pattern indicators for heuristic detection
BIAS_PATTERNS: dict[BiasType, list[str]] = {
    BiasType.CONFIRMATION: [
        "clearly shows",
        "obviously proves",
        "as expected",
        "confirms our",
    ],
    BiasType.ANCHORING: ["initial", "starting with", "base case", "original"],
    BiasType.SUNK_COST: [
        "already invested",
        "we've come so far",
        "can't stop now",
        "previous commitment",
    ],
    BiasType.OVERCONFIDENCE: [
        "definitely",
        "certainly",
        "without doubt",
        "guaranteed",
        "always",
    ],
    BiasType.GROUP_THINK: ["everyone agrees", "consensus is", "we all think", "unanimous"],
}


def generate_heuristic_perspective(
    issue: str,
    perspective_type: PerspectiveType,
) -> Perspective:
    """
    Generate a heuristic perspective when LLM is unavailable.

    Args:
        issue: The issue to analyze
        perspective_type: Type of perspective

    Returns:
        Perspective object with heuristic analysis
    """
    base_viewpoint = VIEWPOINT_TEMPLATES.get(
        perspective_type, f"From a {perspective_type.value} perspective..."
    )

    return Perspective(
        perspective_type=perspective_type,
        viewpoint=base_viewpoint,
        key_insights=[f"Heuristic insight for {perspective_type.value} perspective"],
        assumptions=["Based on general domain knowledge"],
        blind_spots=["May miss context-specific factors"],
        confidence=0.5,  # Lower confidence for heuristic
    )


def detect_biases_heuristic(content: str) -> list[BiasDetection]:
    """
    Detect biases using pattern matching when LLM unavailable.

    Args:
        content: Text content to analyze

    Returns:
        List of detected biases
    """
    biases = []
    content_lower = content.lower()

    for bias_type, patterns in BIAS_PATTERNS.items():
        for pattern in patterns:
            if pattern in content_lower:
                biases.append(
                    BiasDetection(
                        bias_type=bias_type,
                        description=f"Potential {bias_type.value} detected based on language patterns",  # noqa: E501
                        evidence=[f"Found pattern: '{pattern}'"],
                        severity="low",
                        recommendation="Consider alternative viewpoints and seek disconfirming evidence",  # noqa: E501
                    )
                )
                break  # One detection per bias type

    return biases


def get_framework_prompt(framework: AnalyticalFramework, issue: str) -> str:
    """
    Get the framework-specific prompt for LLM processing.

    Args:
        framework: The analytical framework to use
        issue: The issue to analyze

    Returns:
        Formatted prompt string
    """
    template = FRAMEWORK_PROMPTS.get(framework)
    if template:
        return template.format(issue=issue)
    return f"Analyze this issue: {issue}"


def apply_framework_fallback(
    framework: AnalyticalFramework,
    error: str | None = None,
) -> dict[str, Any]:
    """
    Generate fallback result when framework application fails.

    Args:
        framework: The framework that was attempted
        error: Optional error message

    Returns:
        Fallback result dictionary
    """
    result: dict[str, Any] = {
        "framework": framework.value,
        "note": "LLM unavailable - limited analysis",
    }
    if error:
        result["error"] = error
    return result


def generate_stakeholder_map_fallback(error: str | None = None) -> dict[str, Any]:
    """
    Generate fallback stakeholder map when LLM unavailable.

    Args:
        error: Optional error message

    Returns:
        Fallback result dictionary
    """
    result: dict[str, Any] = {
        "stakeholders": [],
        "note": "Stakeholder mapping requires LLM capabilities",
    }
    if error:
        result["error"] = error
    return result


def generate_reframe_fallback() -> list[dict[str, Any]]:
    """
    Generate fallback reframes when LLM unavailable.

    Returns:
        List of fallback reframes
    """
    return [
        {
            "reframe": "Reframe 1: Consider the opposite assumption",
            "type": "assumption_challenge",
            "insights_revealed": ["Challenges core assumptions"],
        },
        {
            "reframe": "Reframe 2: View from a different stakeholder",
            "type": "perspective_shift",
            "insights_revealed": ["Reveals stakeholder impacts"],
        },
    ]


class PrismTransforms:
    """
    Mixin class providing transformation and heuristic methods for Prism agent.

    This class extracts all transformation logic that was previously embedded
    in the PrismAgent class, enabling cleaner separation of concerns and
    improved testability.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize transforms - passes through to next class in MRO."""
        super().__init__(*args, **kwargs)

    def heuristic_perspective(
        self,
        issue: str,
        perspective_type: PerspectiveType,
    ) -> Perspective:
        """Generate a heuristic perspective."""
        return generate_heuristic_perspective(issue, perspective_type)

    def _heuristic_perspective(
        self,
        issue: str,
        perspective_type: PerspectiveType,
    ) -> Perspective:
        """Alias for backward compatibility."""
        return generate_heuristic_perspective(issue, perspective_type)

    def pattern_bias_detection(self, content: str) -> list[BiasDetection]:
        """Detect biases using pattern matching."""
        return detect_biases_heuristic(content)

    def _heuristic_bias_detection(self, content: str) -> list[BiasDetection]:
        """Alias for backward compatibility."""
        return detect_biases_heuristic(content)

    def get_prompt(self, framework: AnalyticalFramework, issue: str) -> str:
        """Get framework-specific prompt."""
        return get_framework_prompt(framework, issue)

    def fallback_framework(
        self,
        framework: AnalyticalFramework,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Generate framework fallback result."""
        return apply_framework_fallback(framework, error)

    def fallback_stakeholder_map(self, error: str | None = None) -> dict[str, Any]:
        """Generate stakeholder map fallback."""
        return generate_stakeholder_map_fallback(error)

    def fallback_reframes(self) -> list[dict[str, Any]]:
        """Generate reframe fallback."""
        return generate_reframe_fallback()


__all__ = [
    "BIAS_PATTERNS",
    "FRAMEWORK_PROMPTS",
    "VIEWPOINT_TEMPLATES",
    "PrismTransforms",
    "apply_framework_fallback",
    "detect_biases_heuristic",
    "generate_heuristic_perspective",
    "generate_reframe_fallback",
    "generate_stakeholder_map_fallback",
    "get_framework_prompt",
]
