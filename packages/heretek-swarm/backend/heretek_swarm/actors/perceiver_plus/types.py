"""
Type definitions for PerceiverPlusAgent.

This module contains all type definitions (enums and data classes) for the
PerceiverPlusAgent, providing advanced multi-modal analytics and pattern recognition.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class AnalyticsType(StrEnum):
    """Types of analytics Perceiver+ can perform."""

    DESCRIPTIVE = "descriptive"
    DIAGNOSTIC = "diagnostic"
    PREDICTIVE = "predictive"
    PRESCRIPTIVE = "prescriptive"
    STATISTICAL = "statistical"
    CORRELATIONAL = "correlational"
    TREND = "trend"
    ANOMALY = "anomaly"


class DataModality(StrEnum):
    """Data modalities for analysis."""

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEXTUAL = "textual"
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    MULTI_MODAL = "multi_modal"


class StatisticalTest(StrEnum):
    """Statistical tests available."""

    T_TEST = "t_test"
    CHI_SQUARE = "chi_square"
    ANOVA = "anova"
    CORRELATION = "correlation"
    REGRESSION = "regression"
    MANN_WHITNEY = "mann_whitney"
    WILCOXON = "wilcoxon"


class AnalyticsResult:
    """Represents an analytics result."""

    def __init__(
        self,
        analysis_id: str,
        analytics_type: AnalyticsType,
        title: str,
        findings: list[str],
        metrics: dict[str, float],
        confidence: float = 0.0,
        recommendations: list[str] | None = None,
        visualizations: list[dict[str, Any]] | None = None,
    ) -> None:
        self.analysis_id = analysis_id
        self.analytics_type = analytics_type
        self.title = title
        self.findings = findings
        self.metrics = metrics
        self.confidence = confidence
        self.recommendations = recommendations or []
        self.visualizations = visualizations or []
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "analytics_type": self.analytics_type.value,
            "title": self.title,
            "findings": self.findings,
            "metrics": self.metrics,
            "confidence": self.confidence,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
            "visualizations": self.visualizations,
        }


class TrendAnalysis:
    """Represents a trend analysis result."""

    def __init__(
        self,
        trend_id: str,
        direction: str,
        strength: float,
        slope: float,
        r_squared: float,
        forecast: list[dict[str, Any]] | None = None,
        seasonal_patterns: list[str] | None = None,
    ) -> None:
        self.trend_id = trend_id
        self.direction = direction  # upward, downward, stable
        self.strength = strength  # 0-1
        self.slope = slope
        self.r_squared = r_squared
        self.forecast = forecast or []
        self.seasonal_patterns = seasonal_patterns or []
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert trend to dictionary."""
        return {
            "trend_id": self.trend_id,
            "direction": self.direction,
            "strength": self.strength,
            "slope": self.slope,
            "r_squared": self.r_squared,
            "forecast": self.forecast,
            "seasonal_patterns": self.seasonal_patterns,
            "timestamp": self.timestamp.isoformat(),
        }


class CorrelationMatrix:
    """Represents a correlation analysis result."""

    def __init__(
        self,
        matrix_id: str,
        variables: list[str],
        correlations: dict[str, dict[str, float]],
        significant_pairs: list[tuple[str, str, float]],
    ) -> None:
        self.matrix_id = matrix_id
        self.variables = variables
        self.correlations = correlations
        self.significant_pairs = significant_pairs
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert matrix to dictionary."""
        return {
            "matrix_id": self.matrix_id,
            "variables": self.variables,
            "correlations": self.correlations,
            "significant_pairs": [
                {"var1": p[0], "var2": p[1], "correlation": p[2]} for p in self.significant_pairs
            ],
            "timestamp": self.timestamp.isoformat(),
        }


__all__ = [
    "AnalyticsResult",
    "AnalyticsType",
    "CorrelationMatrix",
    "DataModality",
    "StatisticalTest",
    "TrendAnalysis",
]
