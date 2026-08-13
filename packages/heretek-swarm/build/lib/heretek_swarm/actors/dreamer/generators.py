"""
Dreamer Generators - Creative Idea and Session Generation Helpers.

Contains generation and calculation helpers extracted from dreamer.py:
- DreamerGeneratorsMixin: Mixin providing creative generation methods

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

import structlog

from heretek_swarm.actors.dreamer.types import (
    CreativeIdea,
    CreativeSession,
    CreativityTechnique,
    NoveltyLevel,
)

logger = structlog.get_logger(__name__)


class DreamerGeneratorsMixin:
    """
    Mixin providing creative generation and calculation helpers.

    Extracted from DreamerAgent to reduce class complexity and improve
    modularity. Provides idea generation prompts, technique application,
    and innovation score calculation.
    """

    # ========================================================================
    # Technique Prompt Generation
    # ========================================================================

    def _build_technique_prompt(self, technique: CreativityTechnique) -> str:
        """Build prompt for specific creativity technique."""
        prompts = {
            CreativityTechnique.BRAINSTORMING: "Generate diverse ideas through free-flowing brainstorming. Quantity over quality initially.",  # noqa: E501
            CreativityTechnique.MIND_MAPPING: "Create ideas by mapping related concepts and exploring branches.",  # noqa: E501
            CreativityTechnique.SCAMPER: "Apply SCAMPER technique: Substitute, Combine, Adapt, Modify, Put to other use, Eliminate, Reverse.",  # noqa: E501
            CreativityTechnique.SIX_THINKING_HATS: "Apply Six Thinking Hats: White (facts), Red (emotions), Black (caution), Yellow (optimism), Green (creativity), Blue (process).",  # noqa: E501
            CreativityTechnique.TRIZ: "Apply TRIZ principles to resolve contradictions and find inventive solutions.",  # noqa: E501
            CreativityTechnique.LATERAL_THINKING: "Use lateral thinking to approach the problem from unexpected angles.",  # noqa: E501
            CreativityTechnique.ANALOGICAL_THINKING: "Draw analogies from unrelated domains to inspire solutions.",  # noqa: E501
            CreativityTechnique.FIRST_PRINCIPLES: "Break down to first principles and rebuild from fundamental truths.",  # noqa: E501
        }
        return prompts.get(technique, "Generate creative ideas.")

    # ========================================================================
    # Innovation Score Calculation
    # ========================================================================

    def _calculate_innovation_score(
        self, ideas: list[CreativeIdea], sessions: list[CreativeSession]
    ) -> float:
        """Calculate overall innovation score."""
        if not ideas and not sessions:
            return 0.0

        scores = []

        # Idea quality score
        if ideas:
            avg_originality = sum(i.originality_score for i in ideas) / len(ideas)
            avg_impact = sum(i.impact_score for i in ideas) / len(ideas)
            breakthrough_count = len([i for i in ideas if i.novelty == NoveltyLevel.BREAKTHROUGH])

            idea_score = (
                avg_originality * 0.4 + avg_impact * 0.4 + min(breakthrough_count / 5, 1) * 0.2
            ) * 100
            scores.append(idea_score)

        # Session activity score
        if sessions:
            session_score = min(len(sessions) / 10, 1) * 100
            scores.append(session_score)

        return sum(scores) / len(scores) if scores else 0.0


# ========================================================================
# Standalone Helper Functions
# ========================================================================


def get_technique_prompt(technique: CreativityTechnique) -> str:
    """Get prompt string for a creativity technique."""
    prompts = {
        CreativityTechnique.BRAINSTORMING: "Generate diverse ideas through free-flowing brainstorming. Quantity over quality initially.",  # noqa: E501
        CreativityTechnique.MIND_MAPPING: "Create ideas by mapping related concepts and exploring branches.",  # noqa: E501
        CreativityTechnique.SCAMPER: "Apply SCAMPER technique: Substitute, Combine, Adapt, Modify, Put to other use, Eliminate, Reverse.",  # noqa: E501
        CreativityTechnique.SIX_THINKING_HATS: "Apply Six Thinking Hats: White (facts), Red (emotions), Black (caution), Yellow (optimism), Green (creativity), Blue (process).",  # noqa: E501
        CreativityTechnique.TRIZ: "Apply TRIZ principles to resolve contradictions and find inventive solutions.",  # noqa: E501
        CreativityTechnique.LATERAL_THINKING: "Use lateral thinking to approach the problem from unexpected angles.",  # noqa: E501
        CreativityTechnique.ANALOGICAL_THINKING: "Draw analogies from unrelated domains to inspire solutions.",  # noqa: E501
        CreativityTechnique.FIRST_PRINCIPLES: "Break down to first principles and rebuild from fundamental truths.",  # noqa: E501
    }
    return prompts.get(technique, "Generate creative ideas.")


def calculate_innovation_score(ideas: list[CreativeIdea], sessions: list[CreativeSession]) -> float:
    """Calculate overall innovation score from ideas and sessions."""
    if not ideas and not sessions:
        return 0.0

    scores = []

    if ideas:
        avg_originality = sum(i.originality_score for i in ideas) / len(ideas)
        avg_impact = sum(i.impact_score for i in ideas) / len(ideas)
        breakthrough_count = len([i for i in ideas if i.novelty == NoveltyLevel.BREAKTHROUGH])

        idea_score = (
            avg_originality * 0.4 + avg_impact * 0.4 + min(breakthrough_count / 5, 1) * 0.2
        ) * 100
        scores.append(idea_score)

    if sessions:
        session_score = min(len(sessions) / 10, 1) * 100
        scores.append(session_score)

    return sum(scores) / len(scores) if scores else 0.0
