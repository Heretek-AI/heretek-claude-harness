"""
Dreamer Types - Data Models and Enums for Creative Solution Generation.

Contains all type definitions extracted from dreamer.py:
- CreativityTechnique: Creative thinking techniques
- IdeaCategory: Categories of generated ideas
- NoveltyLevel: Levels of idea novelty
- CreativeIdea: Generated creative idea record
- CreativeSession: Record of a creative thinking session
- InnovationReport: Consolidated innovation report

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)


class CreativityTechnique(StrEnum):
    """Creative thinking techniques Dreamer employs."""

    BRAINSTORMING = "brainstorming"
    MIND_MAPPING = "mind_mapping"
    SCAMPER = "scamper"  # Substitute, Combine, Adapt, Modify, Put to other use, Eliminate, Reverse
    SIX_THINKING_HATS = "six_thinking_hats"
    TRIZ = "triz"  # Theory of Inventive Problem Solving
    LATERAL_THINKING = "lateral_thinking"
    ANALOGICAL_THINKING = "analogical_thinking"
    FIRST_PRINCIPLES = "first_principles"


class IdeaCategory(StrEnum):
    """Categories of generated ideas."""

    PRODUCT = "product"
    PROCESS = "process"
    ARCHITECTURE = "architecture"
    ALGORITHM = "algorithm"
    USER_EXPERIENCE = "user_experience"
    BUSINESS = "business"
    SECURITY = "security"
    OPTIMIZATION = "optimization"


class NoveltyLevel(StrEnum):
    """Levels of idea novelty."""

    INCREMENTAL = "incremental"  # Small improvement
    SUBSTANTIAL = "substantial"  # Significant enhancement
    BREAKTHROUGH = "breakthrough"  # Paradigm-shifting


@dataclass
class CreativeIdea:
    """Generated creative idea record."""

    id: str
    title: str
    description: str
    category: IdeaCategory
    novelty: NoveltyLevel
    technique_used: CreativityTechnique
    feasibility_score: float  # 0-1 feasibility estimate
    impact_score: float  # 0-1 impact potential
    originality_score: float  # 0-1 originality measure
    generated_at: datetime
    related_to: str | None = None  # Reference to problem/task
    metadata: dict[str, Any] = field(default_factory=dict)
    variations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert idea to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "novelty": self.novelty.value,
            "technique_used": self.technique_used.value,
            "feasibility_score": self.feasibility_score,
            "impact_score": self.impact_score,
            "originality_score": self.originality_score,
            "generated_at": self.generated_at.isoformat(),
            "related_to": self.related_to,
            "metadata": self.metadata,
            "variations": self.variations,
        }


@dataclass
class CreativeSession:
    """Record of a creative thinking session."""

    id: str
    problem_statement: str
    technique: CreativityTechnique
    ideas_generated: list[str]  # Idea IDs
    started_at: datetime
    completed_at: datetime | None = None
    constraints: list[str] = field(default_factory=list)
    inspiration_sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "id": self.id,
            "problem_statement": self.problem_statement,
            "technique": self.technique.value,
            "ideas_generated": self.ideas_generated,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "constraints": self.constraints,
            "inspiration_sources": self.inspiration_sources,
            "metadata": self.metadata,
        }


@dataclass
class InnovationReport:
    """Consolidated innovation report."""

    id: str
    generated_at: datetime
    problem_area: str
    ideas: list[CreativeIdea]
    sessions: list[CreativeSession]
    top_recommendations: list[str]
    innovation_score: float  # 0-100 overall innovation potential
    implementation_roadmap: list[dict[str, Any]]
    risks: list[str]
    opportunities: list[str]
