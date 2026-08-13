"""Zero-Trust result types: Severity, LayerResult, ZeroTrustResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Security event severity levels for audit logging."""

    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class LayerResult:
    """Result from a single validation layer."""

    layer: str
    passed: bool
    reason: str | None = None
    severity: Severity = Severity.INFO
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ZeroTrustResult:
    """Aggregated result from all 4 validation layers."""

    passed: bool
    layer1: LayerResult
    layer2: LayerResult
    layer3: LayerResult
    layer4: LayerResult
    request_id: str
    agent_id: str | None = None
    total_latency_ms: float = 0.0
    sanitized_output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "passed": self.passed,
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "total_latency_ms": self.total_latency_ms,
            "layers": {
                "layer1_input": {
                    "passed": self.layer1.passed,
                    "reason": self.layer1.reason,
                    "severity": self.layer1.severity.value,
                },
                "layer2_context": {
                    "passed": self.layer2.passed,
                    "reason": self.layer2.reason,
                    "severity": self.layer2.severity.value,
                },
                "layer3_output": {
                    "passed": self.layer3.passed,
                    "reason": self.layer3.reason,
                    "severity": self.layer3.severity.value,
                },
                "layer4_audit": {
                    "passed": self.layer4.passed,
                    "severity": self.layer4.severity.value,
                },
            },
        }
