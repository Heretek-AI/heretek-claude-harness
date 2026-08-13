"""
Examiner Types - Data Models and Enums for Quality Assurance.

Contains all type definitions extracted from examiner.py:
- TestType, TestStatus, QualityMetric, SeverityLevel: Enums
- TestCase, TestSuite, Bug, QualityReport: Data classes

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TestType(StrEnum):
    """Types of tests Examiner can execute."""

    UNIT = "unit"
    INTEGRATION = "integration"
    END_TO_END = "end_to_end"
    PERFORMANCE = "performance"
    SECURITY = "security"
    ACCESSIBILITY = "accessibility"
    REGRESSION = "regression"


class TestStatus(StrEnum):
    """Test execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class QualityMetric(StrEnum):
    """Quality metrics Examiner tracks."""

    CODE_COVERAGE = "code_coverage"
    CYCLOMATIC_COMPLEXITY = "cyclomatic_complexity"
    TECHNICAL_DEBT = "technical_debt"
    SECURITY_VULNERABILITIES = "security_vulnerabilities"
    PERFORMANCE_SCORE = "performance_score"
    ACCESSIBILITY_SCORE = "accessibility_score"
    DOCUMENTATION_COVERAGE = "documentation_coverage"


class SeverityLevel(StrEnum):
    """Bug/issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class TestCase:
    """Test case definition and result."""

    id: str
    name: str
    test_type: TestType
    description: str
    status: TestStatus
    execution_time_ms: float | None = None
    error_message: str | None = None
    assertions_passed: int = 0
    assertions_total: int = 0
    coverage_percent: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSuite:
    """Collection of test cases with aggregate results."""

    id: str
    name: str
    test_cases: list[TestCase]
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0
    execution_time_ms: float = 0.0
    coverage_percent: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Bug:
    """Detected bug or issue record."""

    id: str
    title: str
    description: str
    severity: SeverityLevel
    component: str
    steps_to_reproduce: list[str]
    expected_behavior: str
    actual_behavior: str
    detected_at: datetime
    status: str = "new"  # new/open/fixed/closed/wontfix
    assignee: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    """Comprehensive quality assessment report."""

    id: str
    generated_at: datetime
    target: str  # What was examined (code/decision/component)
    test_suites: list[TestSuite]
    bugs: list[Bug]
    metrics: dict[QualityMetric, float]
    overall_score: float  # 0-100 quality score
    summary: str
    recommendations: list[str]
    pass_threshold: float = 80.0
    passed: bool = True
