"""
Sentinel Types - Safety Enums and Data Classes.

This module contains the type definitions extracted from sentinel.py:
- SafetyLevel: Safety violation severity levels
- ViolationType: Types of safety violations
- ContentCategory: Content classification categories
- SafetyViolation: Record of a detected safety violation
- SafetyReport: Aggregated safety report
- AnomalyAlert: Alert for a detected behavioral anomaly
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import structlog

from heretek_swarm_core.security.anomaly_detection import (
    AnomalySeverity,
    AnomalyType,
    ResponseStatus,
)

logger = structlog.get_logger(__name__)


class SafetyLevel(StrEnum):
    """Safety violation severity levels."""

    SAFE = "safe"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"


class ViolationType(StrEnum):
    """Types of safety violations."""

    INJECTION_ATTEMPT = "injection_attempt"
    MALICIOUS_CONTENT = "malicious_content"
    PII_DETECTED = "pii_detected"
    HATE_SPEECH = "hate_speech"
    HARASSMENT = "harassment"
    SELF_HARM = "self_harm"
    VIOLENCE = "violence"
    SEXUAL_CONTENT = "sexual_content"
    DANGEROUS_ACTIVITY = "dangerous_activity"
    MISINFORMATION = "misinformation"
    SPAM = "spam"
    POLICY_VIOLATION = "policy_violation"
    # SAFE-01: Behavioral anomaly types
    BEHAVIORAL_ANOMALY = "behavioral_anomaly"
    AGENT_RATE_VIOLATION = "agent_rate_violation"
    AGENT_RESPONSE_TIME_VIOLATION = "agent_response_time_violation"
    AGENT_VALIDATION_FAILURE = "agent_validation_failure"


class ContentCategory(StrEnum):
    """Content classification categories."""

    TEXT = "text"
    CODE = "code"
    URL = "url"
    FILE_PATH = "file_path"
    COMMAND = "command"
    API_CALL = "api_call"
    UNKNOWN = "unknown"


@dataclass
class SafetyViolation:
    """Record of a detected safety violation."""

    violation_id: str
    violation_type: ViolationType
    severity: SafetyLevel
    content_hash: str
    description: str
    timestamp: datetime
    source_agent: str | None = None
    target_agent: str | None = None
    blocked: bool = True
    remediation_action: str | None = None


@dataclass
class SafetyReport:
    """Aggregated safety report."""

    report_id: str
    timestamp: datetime
    total_scans: int
    violations_detected: int
    violations_blocked: int
    violations_by_type: dict[str, int]
    violations_by_severity: dict[str, int]
    recommendations: list[str]


@dataclass
class AnomalyAlert:
    """Alert for a detected behavioral anomaly."""

    alert_id: str
    anomaly_id: str
    agent_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    timestamp: datetime
    response_status: ResponseStatus
    response_latency_ms: float
    sentinel_prime_escalated: bool
    false_positive: bool
