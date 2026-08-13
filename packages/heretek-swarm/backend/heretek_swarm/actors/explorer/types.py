"""
Explorer Types - Data Models and Enums for Intelligence Gathering

Contains all type definitions extracted from explorer.py.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class OpportunityType(StrEnum):
    """Types of opportunities Explorer can identify."""

    API_INTEGRATION = "api_integration"
    FRAMEWORK = "framework"
    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    SECURITY_ENHANCEMENT = "security_enhancement"
    COST_REDUCTION = "cost_reduction"
    CAPABILITY_ADDITION = "capability_addition"


class ThreatLevel(StrEnum):
    """Threat severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(StrEnum):
    """Types of anomalies Explorer can detect."""

    PERFORMANCE = "performance"
    SECURITY = "security"
    BEHAVIORAL = "behavioral"
    INTEGRATION = "integration"
    DATA = "data"


class ResearchState(StrEnum):
    """States for the research workflow state machine."""

    IDLE = "idle"
    RESEARCHING = "researching"
    ANALYZING = "analyzing"
    CONTRADICTION = "contradiction"
    VALIDATING = "validating"
    DELIVERING = "delivering"


@dataclass
class Opportunity:
    """Discovered opportunity record."""

    id: str
    type: OpportunityType
    title: str
    description: str
    source: str
    confidence: float  # 0-1 confidence score
    impact_score: float  # 0-1 impact potential
    effort_estimate: str  # low/medium/high
    discovered_at: datetime
    status: str = "new"  # new/under_review/approved/rejected
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Anomaly:
    """Detected anomaly record."""

    id: str
    type: AnomalyType
    description: str
    source: str
    severity: ThreatLevel
    detected_at: datetime
    affected_components: list[str]
    evidence: dict[str, Any]
    status: str = "new"  # new/investigating/escalated/resolved
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntelligenceReport:
    """Consolidated intelligence report."""

    id: str
    generated_at: datetime
    opportunities: list[Opportunity]
    anomalies: list[Anomaly]
    summary: str
    recommendations: list[str]
    sources_monitored: list[str]
    time_range_hours: int


@dataclass
class ResearchProgress:
    """Tracks progress of an active research operation."""

    query_id: str
    topic: str
    state: ResearchState
    sources_consulted: int = 0
    findings_count: int = 0
    contradictions_found: int = 0
    elapsed_seconds: float = 0.0
    percent_complete: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)


@dataclass
class Pattern:
    """Detected pattern from research findings."""

    pattern_id: str
    pattern_type: str
    confidence: float
    supporting_findings: list[str]
    description: str
    detected_at: datetime = field(default_factory=datetime.now)
