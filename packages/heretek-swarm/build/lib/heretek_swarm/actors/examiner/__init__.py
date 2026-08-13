"""
Examiner Module - Quality Assurance & Testing Specialist.

This module provides the ExaminerAgent for quality assurance and testing.
The module has been refactored into separate components:

- types.py: Type definitions (TestType, TestStatus, QualityMetric, SeverityLevel, TestCase, TestSuite, Bug, QualityReport)  # noqa: E501
- testing.py: Testing mixins (ExaminingTestingMixin, ExaminingValidationMixin)
- agent.py: Main ExaminerAgent class

For backward compatibility, all public exports from the original examiner.py
are re-exported from this module.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

# Re-export agent from agent.py
from heretek_swarm.actors.examiner.agent import ExaminerAgent

# Re-export mixins from testing.py
from heretek_swarm.actors.examiner.testing import (
    ExaminingTestingMixin,
    ExaminingValidationMixin,
)

# Re-export types from types.py
from heretek_swarm.actors.examiner.types import (
    Bug,
    QualityMetric,
    QualityReport,
    SeverityLevel,
    TestCase,
    TestStatus,
    TestSuite,
    TestType,
)

__all__ = [
    # Types (enums and data classes)
    "Bug",
    # Agent
    "ExaminerAgent",
    # Mixins
    "ExaminingTestingMixin",
    "ExaminingValidationMixin",
    "QualityMetric",
    "QualityReport",
    "SeverityLevel",
    "TestCase",
    "TestStatus",
    "TestSuite",
    "TestType",
]
