"""Layer 2: Context Validation — injection detection, behavioral baseline, anomaly detection."""

import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from .result_types import LayerResult, Severity

logger = structlog.get_logger(__name__)


@dataclass
class BehavioralBaseline:
    """Baseline for behavioral analysis."""

    agent_id: str
    avg_request_size: float = 0.0
    avg_request_interval_ms: float = 0.0
    common_patterns: set[str] = field(default_factory=set)
    total_requests: int = 0
    last_request_time: str | None = None
    anomaly_threshold: float = 3.0


@dataclass
class ContextValidationConfig:
    """Configuration for Layer 2 Context Validation."""

    enable_injection_detection: bool = True
    enable_behavioral_analysis: bool = True
    enable_anomaly_detection: bool = True
    anomaly_threshold: float = 3.0
    false_positive_threshold: float = 0.01
    min_requests_for_baseline: int = 10
    max_baseline_age_hours: int = 24


class ContextValidator:
    """Layer 2: Context Validation — injection detection, behavioral baseline, anomaly detection."""

    CONTEXT_INJECTION_PATTERNS = [  # noqa: RUF012
        (r"ignore\s+(all\s+)?(previous|prior)\s+instructions", "prompt injection: ignore instructions"),
        (r"disregard\s+(all\s+)?(previous|prior)\s+", "prompt injection: disregard"),
        (r"you\s+are\s+now\s+", "prompt injection: role change"),
        (r"act\s+as\s+(if|though)\s+", "prompt injection: role play"),
        (r"pretend\s+(to\s+be|that)\s+", "prompt injection: pretend"),
        (r"forget\s+(everything|all)\s+", "prompt injection: forget"),
        (r"new\s+instructions?\s*:", "prompt injection: new instructions"),
        (r"system\s*:\s*", "prompt injection: system prompt"),
        (r"<\|.*?\|>", "prompt injection: special token"),
        (r"\[SYSTEM\]", "prompt injection: system tag"),
        (r"\[INST\]", "prompt injection: instruction tag"),
        (r"\\x[0-9a-fA-F]{2}", "encoded character detected"),
        (r"\\u[0-9a-fA-F]{4}", "unicode escape detected"),
        (r"%[0-9a-fA-F]{2}", "URL encoding detected"),
        (r"base64[_\s]*decode", "base64 decode detected"),
    ]

    def __init__(self, config: ContextValidationConfig | None = None):
        self.config = config or ContextValidationConfig()
        self._baselines: dict[str, BehavioralBaseline] = {}
        self._compiled_patterns = [
            (re.compile(p, re.IGNORECASE), desc) for p, desc in self.CONTEXT_INJECTION_PATTERNS
        ]

    def validate(
        self, data: dict[str, Any], context: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> LayerResult:
        """Validate request context against Layer 2 rules."""
        start_time = time.time()
        context = context or {}
        anomalies_detected: list[str] = []
        try:
            content_str = str(data)
            if result := self._check_context_injection(content_str):
                return result
            if self.config.enable_behavioral_analysis and agent_id:
                baseline = self._get_or_create_baseline(agent_id)
                behavioral_result = self._analyze_behavior(data, baseline)
                if behavioral_result:
                    anomalies_detected.extend(behavioral_result)
            if result := self._check_anomalies(anomalies_detected):
                return result
            latency_ms = (time.time() - start_time) * 1000
            return LayerResult(
                layer="context", passed=True, severity=Severity.INFO,
                details={"latency_ms": latency_ms,
                         "behavioral_analysis": self.config.enable_behavioral_analysis,
                         "injection_detection": self.config.enable_injection_detection},
            )
        except Exception as e:
            logger.error("context_validation_error", error=str(e), agent_id=agent_id)
            return LayerResult(
                layer="context", passed=False,
                reason=f"Context validation error: {e}", severity=Severity.HIGH,
            )

    def _check_context_injection(self, content_str: str) -> LayerResult | None:
        if not self.config.enable_injection_detection:
            return None
        for pattern, description in self._compiled_patterns:
            if pattern.search(content_str):
                return LayerResult(
                    layer="context", passed=False,
                    reason=f"Context injection detected: {description}",
                    severity=Severity.HIGH,
                    details={"pattern": pattern.pattern, "description": description},
                )
        return None

    @staticmethod
    def _check_anomalies(anomalies_detected: list[str]) -> LayerResult | None:
        if not anomalies_detected:
            return None
        severity = Severity.HIGH if len(anomalies_detected) >= 3 else Severity.WARNING
        return LayerResult(
            layer="context", passed=False,
            reason=f"Anomalies detected: {'; '.join(anomalies_detected)}",
            severity=severity, details={"anomalies": anomalies_detected},
        )

    def _get_or_create_baseline(self, agent_id: str) -> BehavioralBaseline:
        if agent_id not in self._baselines:
            self._baselines[agent_id] = BehavioralBaseline(agent_id=agent_id)
        return self._baselines[agent_id]

    def _analyze_behavior(self, data: dict[str, Any], baseline: BehavioralBaseline) -> list[str]:
        anomalies: list[str] = []
        current_time = datetime.now(UTC)
        request_size = len(str(data))

        if baseline.total_requests > 0:
            size_deviation = abs(request_size - baseline.avg_request_size)
            if baseline.avg_request_size > 0:
                z_score = size_deviation / baseline.avg_request_size
                if z_score > self.config.anomaly_threshold:
                    anomalies.append(f"Request size anomaly (z={z_score:.2f})")

            if baseline.last_request_time:
                last_time = datetime.fromisoformat(baseline.last_request_time)
                interval_ms = (current_time - last_time).total_seconds() * 1000
                if baseline.avg_request_interval_ms > 0:
                    if interval_ms < baseline.avg_request_interval_ms * 0.1:
                        anomalies.append(f"Rapid request detected (interval={interval_ms:.0f}ms)")

        baseline.total_requests += 1
        baseline.avg_request_size = (
            baseline.avg_request_size * (baseline.total_requests - 1) + request_size
        ) / baseline.total_requests
        baseline.last_request_time = current_time.isoformat()

        return anomalies

    def update_baseline(self, agent_id: str, avg_request_size: float, avg_request_interval_ms: float) -> None:
        baseline = self._get_or_create_baseline(agent_id)
        baseline.avg_request_size = avg_request_size
        baseline.avg_request_interval_ms = avg_request_interval_ms
