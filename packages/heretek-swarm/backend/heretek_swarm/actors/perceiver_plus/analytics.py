"""
PerceiverPlus Analytics Mixin.

This module provides the PerceiverAnalyticsMixin containing all helper methods
for advanced multi-modal analytics. The mixin is designed to be inherited
cooperatively with other PerceiverPlus mixins.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.actors.perceiver_plus.types import (
    AnalyticsResult,
    AnalyticsType,
    CorrelationMatrix,
    TrendAnalysis,
)

logger = structlog.get_logger("PerceiverAnalyticsMixin")


class PerceiverAnalyticsMixin:
    """
    Analytics mixin for PerceiverPlusAgent.

    Provides all helper methods for performing advanced analytics including:
    - Descriptive, diagnostic, predictive, and statistical analysis
    - Correlation and trend analysis
    - Anomaly detection
    - Feature extraction
    - Signal processing
    """

    # Placeholder - actual mixin methods will be added by the agent
    # Methods are provided via cooperative inheritance with the actual mixin


class PerceiverAnalyticsMixinImpl:
    """
    Implementation of analytics methods for PerceiverPlusAgent.

    This class provides all the analytics helper methods that will be
    inherited by the PerceiverPlusAgent through cooperative multiple inheritance.
    """

    # State accessors (to be provided by agent class)
    _max_analyses: int
    _confidence_threshold: float
    _significance_level: float
    analysis_results: dict[str, AnalyticsResult]
    trend_analyses: dict[str, TrendAnalysis]
    correlation_matrices: dict[str, CorrelationMatrix]
    feature_cache: dict[str, dict[str, Any]]
    data_buffers: dict[str, list[float]]
    categorical_buffers: dict[str, list[str]]
    agent_id: str

    def _validate_data_input(self, content: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate data input for analysis.

        Args:
            content: Message content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if "data" not in content:
            return False, "Missing required field: data"

        data = content["data"]
        if not isinstance(data, (list, dict)):
            return False, "Field 'data' must be a list or dictionary"

        # Check data size
        if isinstance(data, list) and len(data) > 100000:
            return False, "Data exceeds maximum size (100000 elements)"

        return True, ""

    async def _perform_analysis(
        self,
        data: list | dict,
        analytics_type: AnalyticsType,
        analysis_id: str,
    ) -> AnalyticsResult:
        """
        Perform a specific type of analysis.

        Args:
            data: Data to analyze
            analytics_type: Type of analysis to perform
            analysis_id: Analysis identifier

        Returns:
            AnalyticsResult object
        """
        if analytics_type == AnalyticsType.DESCRIPTIVE:
            return await self._descriptive_analysis(data, analysis_id)
        if analytics_type == AnalyticsType.DIAGNOSTIC:
            return await self._diagnostic_analysis(data, analysis_id)
        if analytics_type == AnalyticsType.PREDICTIVE:
            return await self._predictive_analysis(data, analysis_id)
        if analytics_type == AnalyticsType.STATISTICAL:
            return await self._statistical_analysis(data, analysis_id)
        if analytics_type == AnalyticsType.CORRELATIONAL:
            return await self._correlational_analysis(data, analysis_id)
        if analytics_type == AnalyticsType.TREND:
            return await self._trend_analysis(data, analysis_id)
        if analytics_type == AnalyticsType.ANOMALY:
            return await self._anomaly_analysis(data, analysis_id)
        return AnalyticsResult(
            analysis_id=analysis_id,
            analytics_type=analytics_type,
            title=f"Unknown analysis type: {analytics_type.value}",
            findings=[],
            metrics={},
            confidence=0.0,
        )

    async def _descriptive_analysis(
        self, data: list | dict, analysis_id: str,
    ) -> AnalyticsResult:
        """Perform descriptive statistics analysis."""
        if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
            findings, metrics, confidence = self._numeric_descriptive_stats(data)
        else:
            findings, metrics, confidence = self._general_description(data)
        return AnalyticsResult(
            analysis_id=analysis_id, analytics_type=AnalyticsType.DESCRIPTIVE,
            title="Descriptive Statistics Analysis",
            findings=findings, metrics=metrics, confidence=confidence,
        )

    @staticmethod
    def _numeric_descriptive_stats(data: list[float]) -> tuple[list[str], dict[str, float], float]:
        n = len(data)
        if n == 0:
            return [], {}, 0.0
        mean = sum(data) / n
        variance = sum((x - mean) ** 2 for x in data) / n if n > 1 else 0
        std_dev = math.sqrt(variance)
        sorted_data = sorted(data)
        median = (
            sorted_data[n // 2] if n % 2 == 1
            else (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2
        )
        min_val, max_val = min(data), max(data)
        metrics = {
            "count": n, "mean": mean, "std_dev": std_dev, "median": median,
            "min": min_val, "max": max_val, "range": max_val - min_val, "variance": variance,
        }
        findings = [
            f"Dataset contains {n} numeric values",
            f"Mean: {mean:.4f}, Median: {median:.4f}",
            f"Standard deviation: {std_dev:.4f}",
            f"Range: [{min_val:.4f}, {max_val:.4f}]",
        ]
        return findings, metrics, 0.95

    @staticmethod
    def _general_description(data: list | dict) -> tuple[list[str], dict[str, int], float]:
        findings = [
            f"Data type: {type(data).__name__}",
            f"Data length/size: {len(data) if hasattr(data, '__len__') else 'N/A'}",
        ]
        metrics = {"size": len(data) if hasattr(data, "__len__") else 1}
        return findings, metrics, 0.7

    async def _diagnostic_analysis(
        self,
        data: list | dict,
        analysis_id: str,
    ) -> AnalyticsResult:
        """Perform diagnostic analysis to understand causes."""
        findings = []
        metrics = {}

        # Build prompt for LLM diagnostic analysis
        prompt = f"""Perform diagnostic analysis on this data:

DATA: {str(data)[:5000]}

Identify:
1. Key patterns and relationships
2. Potential causal factors
3. Contributing variables
4. Root causes of observed outcomes

Respond in JSON:
{{
    "findings": ["...", "..."],
    "causal_factors": ["...", "..."],
    "key_relationships": ["...", "..."],
    "confidence": 0.0
}}"""

        try:
            if self.pydantic_ai_agent:
                result = await self.run_with_llm(prompt=prompt, timeout=60)
                import json

                start_idx = result.find("{")
                end_idx = result.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    parsed = json.loads(result[start_idx:end_idx])
                    findings = parsed.get("findings", [])
                    metrics = {
                        "causal_factors_count": len(parsed.get("causal_factors", [])),
                    }
                    confidence = float(parsed.get("confidence", 0.7))
                else:
                    raise ValueError("No JSON found")
            else:
                raise RuntimeError("LLM not available")
        except Exception as e:
            logger.debug("perceiver_plus_diagnostic_failed", error=str(e))
            findings = ["Diagnostic analysis requires LLM capabilities"]
            confidence = 0.3

        return AnalyticsResult(
            analysis_id=analysis_id,
            analytics_type=AnalyticsType.DIAGNOSTIC,
            title="Diagnostic Analysis",
            findings=findings,
            metrics=metrics,
            confidence=confidence,
        )

    async def _predictive_analysis(
        self,
        data: list | dict,
        analysis_id: str,
    ) -> AnalyticsResult:
        """Perform predictive analysis and forecasting."""
        findings = []
        metrics = {}

        prompt = f"""Perform predictive analysis on this data:

DATA: {str(data)[:5000]}

Generate:
1. Predictions for future values/outcomes
2. Confidence intervals
3. Key predictive factors
4. Risk indicators

Respond in JSON:
{{
    "predictions": ["...", "..."],
    "confidence_intervals": {{}},
    "predictive_factors": ["...", "..."],
    "risk_indicators": ["...", "..."],
    "confidence": 0.0
}}"""

        try:
            if self.pydantic_ai_agent:
                result = await self.run_with_llm(prompt=prompt, timeout=60)
                import json

                start_idx = result.find("{")
                end_idx = result.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    parsed = json.loads(result[start_idx:end_idx])
                    findings = parsed.get("predictions", [])
                    metrics = {
                        "factors_count": len(parsed.get("predictive_factors", [])),
                    }
                    confidence = float(parsed.get("confidence", 0.6))
                else:
                    raise ValueError("No JSON found")
            else:
                raise RuntimeError("LLM not available")
        except Exception as e:
            logger.debug("perceiver_plus_predictive_failed", error=str(e))
            findings = ["Predictive analysis requires LLM capabilities"]
            confidence = 0.3

        return AnalyticsResult(
            analysis_id=analysis_id,
            analytics_type=AnalyticsType.PREDICTIVE,
            title="Predictive Analysis",
            findings=findings,
            metrics=metrics,
            confidence=confidence,
            recommendations=metrics.get("risk_indicators", []),
        )

    async def _statistical_analysis(
        self,
        data: list | dict,
        analysis_id: str,
    ) -> AnalyticsResult:
        """Perform statistical analysis."""
        findings = []
        metrics = {}

        if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
            n = len(data)
            if n >= 2:
                # Basic statistical tests
                mean = sum(data) / n
                variance = sum((x - mean) ** 2 for x in data) / (n - 1)
                std_dev = math.sqrt(variance)
                se = std_dev / math.sqrt(n)  # Standard error

                # 95% confidence interval
                ci_margin = 1.96 * se
                ci_lower = mean - ci_margin
                ci_upper = mean + ci_margin

                metrics = {
                    "sample_size": n,
                    "mean": mean,
                    "std_dev": std_dev,
                    "std_error": se,
                    "ci_95_lower": ci_lower,
                    "ci_95_upper": ci_upper,
                }

                findings = [
                    f"Sample size: {n}",
                    f"Mean: {mean:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}])",
                    f"Standard deviation: {std_dev:.4f}",
                    f"Standard error: {se:.4f}",
                ]

                confidence = 0.95
            else:
                findings = ["Insufficient data for statistical analysis (minimum n=2)"]
                confidence = 0.0
        else:
            findings = ["Statistical analysis requires numeric list data"]
            confidence = 0.0

        return AnalyticsResult(
            analysis_id=analysis_id,
            analytics_type=AnalyticsType.STATISTICAL,
            title="Statistical Analysis",
            findings=findings,
            metrics=metrics,
            confidence=confidence,
        )

    async def _correlational_analysis(
        self,
        data: list | dict,
        analysis_id: str,
    ) -> AnalyticsResult:
        """Perform correlational analysis between variables."""
        findings = []
        metrics = {}

        # Expect dict of variables: {var_name: [values]}
        if isinstance(data, dict):
            variables = list(data.keys())
            if len(variables) >= 2:
                correlations = {}
                significant_pairs = []

                for var in variables:
                    correlations[var] = {}

                for i, var1 in enumerate(variables):
                    for var2 in variables[i + 1 :]:
                        corr = self._calculate_correlation(
                            data.get(var1, []),
                            data.get(var2, []),
                        )
                        correlations[var1][var2] = corr
                        correlations[var2][var1] = corr

                        if abs(corr) > 0.5:
                            significant_pairs.append((var1, var2, corr))

                # Store correlation matrix
                matrix = CorrelationMatrix(
                    matrix_id=f"corr_{analysis_id}",
                    variables=variables,
                    correlations=correlations,
                    significant_pairs=significant_pairs,
                )
                self.correlation_matrices[matrix.matrix_id] = matrix

                findings = [
                    f"Analyzed {len(variables)} variables",
                    f"Found {len(significant_pairs)} significant correlations (|r| > 0.5)",
                ] + [f"{p[0]} ↔ {p[1]}: r = {p[2]:.3f}" for p in significant_pairs[:5]]

                metrics = {
                    "variables_count": len(variables),
                    "significant_correlations": len(significant_pairs),
                    "strongest_correlation": max([abs(p[2]) for p in significant_pairs])
                    if significant_pairs
                    else 0,
                }

                confidence = 0.85
            else:
                findings = ["Need at least 2 variables for correlation analysis"]
                confidence = 0.0
        else:
            findings = ["Correlational analysis requires dict of variables"]
            confidence = 0.0

        return AnalyticsResult(
            analysis_id=analysis_id,
            analytics_type=AnalyticsType.CORRELATIONAL,
            title="Correlational Analysis",
            findings=findings,
            metrics=metrics,
            confidence=confidence,
        )

    def _calculate_correlation(self, x: list[float], y: list[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0

        x = x[:n]
        y = y[:n]

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        if denom_x * denom_y == 0:
            return 0.0

        return numerator / (denom_x * denom_y)

    async def _trend_analysis(
        self,
        data: list | dict,
        analysis_id: str,
    ) -> AnalyticsResult:
        """Perform trend analysis on time series data."""
        findings = []
        metrics = {}

        # Perform linear regression for trend
        if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
            n = len(data)
            if n >= 3:
                # Simple linear regression
                x_mean = (n - 1) / 2
                y_mean = sum(data) / n

                numerator = sum((i - x_mean) * (data[i] - y_mean) for i in range(n))
                denominator = sum((i - x_mean) ** 2 for i in range(n))

                if denominator != 0:
                    slope = numerator / denominator
                    intercept = y_mean - slope * x_mean

                    # Calculate R-squared
                    y_pred = [slope * i + intercept for i in range(n)]
                    ss_res = sum((data[i] - y_pred[i]) ** 2 for i in range(n))
                    ss_tot = sum((data[i] - y_mean) ** 2 for i in range(n))
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

                    # Determine direction
                    if slope > 0.01:
                        direction = "upward"
                    elif slope < -0.01:
                        direction = "downward"
                    else:
                        direction = "stable"

                    # Store trend analysis
                    trend = TrendAnalysis(
                        trend_id=f"trend_{analysis_id}",
                        direction=direction,
                        strength=abs(slope),
                        slope=slope,
                        r_squared=r_squared,
                    )
                    self.trend_analyses[trend.trend_id] = trend

                    findings = [
                        f"Trend direction: {direction}",
                        f"Slope: {slope:.4f} units per time period",
                        f"R-squared: {r_squared:.4f} ({r_squared * 100:.1f}% variance explained)",
                    ]

                    metrics = {
                        "slope": slope,
                        "intercept": intercept,
                        "r_squared": r_squared,
                        "trend_strength": abs(slope),
                    }

                    confidence = min(r_squared + 0.3, 1.0)
                else:
                    findings = ["Cannot compute trend (zero variance in time)"]
                    confidence = 0.0
            else:
                findings = ["Need at least 3 data points for trend analysis"]
                confidence = 0.0
        else:
            findings = ["Trend analysis requires numeric time series data"]
            confidence = 0.0

        return AnalyticsResult(
            analysis_id=analysis_id,
            analytics_type=AnalyticsType.TREND,
            title="Trend Analysis",
            findings=findings,
            metrics=metrics,
            confidence=confidence,
        )

    async def _anomaly_analysis(
        self,
        data: list | dict,
        analysis_id: str,
    ) -> AnalyticsResult:
        """Detect anomalies in data."""
        findings = []
        metrics = {}

        if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
            n = len(data)
            if n >= 3:
                mean = sum(data) / n
                std_dev = math.sqrt(sum((x - mean) ** 2 for x in data) / (n - 1)) if n > 1 else 0

                # Find anomalies (values beyond 2 standard deviations)
                threshold = 2.0 * std_dev
                anomalies = []
                for i, value in enumerate(data):
                    if abs(value - mean) > threshold:
                        anomalies.append(
                            {
                                "index": i,
                                "value": value,
                                "deviation": abs(value - mean) / std_dev if std_dev > 0 else 0,
                            }
                        )

                findings = [
                    f"Analyzed {n} data points",
                    f"Detection threshold: ±{threshold:.4f} from mean ({mean:.4f})",
                    f"Found {len(anomalies)} anomalies",
                ] + [
                    f"Index {a['index']}: value={a['value']:.4f} ({a['deviation']:.1f}σ)"
                    for a in anomalies[:5]
                ]

                metrics = {
                    "anomalies_count": len(anomalies),
                    "anomaly_rate": len(anomalies) / n,
                    "threshold_sigma": 2.0,
                }

                confidence = 0.8
            else:
                findings = ["Need at least 3 data points for anomaly detection"]
                confidence = 0.0
        else:
            findings = ["Anomaly detection requires numeric list data"]
            confidence = 0.0

        return AnalyticsResult(
            analysis_id=analysis_id,
            analytics_type=AnalyticsType.ANOMALY,
            title="Anomaly Detection",
            findings=findings,
            metrics=metrics,
            confidence=confidence,
            recommendations=["Review detected anomalies for data quality issues"]
            if metrics.get("anomalies_count", 0) > 0
            else [],
        )

    async def _extract_features_from_data(self, data: list | dict) -> dict[str, Any]:
        """Extract features from data."""
        features = {
            "timestamp": datetime.now(UTC).isoformat(),
            "data_type": type(data).__name__,
        }

        if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
            n = len(data)
            if n > 0:
                mean = sum(data) / n
                features.update(
                    {
                        "count": n,
                        "mean": mean,
                        "min": min(data),
                        "max": max(data),
                        "sum": sum(data),
                    }
                )
                if n > 1:
                    variance = sum((x - mean) ** 2 for x in data) / (n - 1)
                    features["variance"] = variance
                    features["std_dev"] = math.sqrt(variance)

        return features

    async def _forecast_values(self, data: list[float], periods: int) -> list[dict[str, Any]]:
        """Generate forecast values."""
        forecast = []

        if len(data) >= 2:
            # Simple linear extrapolation
            n = len(data)
            x_mean = (n - 1) / 2
            y_mean = sum(data) / n

            numerator = sum((i - x_mean) * (data[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))

            if denominator != 0:
                slope = numerator / denominator
                intercept = y_mean - slope * x_mean

                for i in range(periods):
                    future_x = n + i
                    predicted = slope * future_x + intercept
                    forecast.append(
                        {
                            "period": i + 1,
                            "predicted_value": predicted,
                            "confidence": max(0.5 - (i * 0.05), 0.1),  # Decreasing confidence
                        }
                    )
            else:
                # Flat forecast
                for i in range(periods):
                    forecast.append(
                        {
                            "period": i + 1,
                            "predicted_value": y_mean,
                            "confidence": 0.3,
                        }
                    )
        else:
            forecast = [{"error": "Insufficient data for forecasting"}]

        return forecast

    def _process_signal(self, data: list[float], method: str, window: int) -> list[float]:
        """Process signal with specified method."""
        if method == "moving_average":
            result = []
            for i in range(len(data) - window + 1):
                result.append(sum(data[i : i + window]) / window)
            return result
        if method == "median_filter":
            result = []
            for i in range(len(data) - window + 1):
                sorted_window = sorted(data[i : i + window])
                result.append(sorted_window[window // 2])
            return result
        return data  # No processing


__all__ = [
    "PerceiverAnalyticsMixin",
    "PerceiverAnalyticsMixinImpl",
]
