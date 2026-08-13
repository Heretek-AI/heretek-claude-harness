"""
Sentinel-Prime types - Enums and dataclasses for security threat management.

Extracted from sentinel_prime.py (SAFE-02).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ThreatLevel(StrEnum):
    """Threat severity classification."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(StrEnum):
    """Types of security threats."""

    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXFILTRATION = "data_exfiltration"
    MALWARE = "malware"
    PHISHING = "phishing"
    DOS_ATTACK = "dos_attack"
    MAN_IN_THE_MIDDLE = "man_in_the_middle"
    SQL_INJECTION = "sql_injection"
    XSS_ATTACK = "xss_attack"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    CREDENTIAL_STUFFING = "credential_stuffing"
    BRUTE_FORCE = "brute_force"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    POLICY_VIOLATION = "policy_violation"
    ZERO_DAY_EXPLOIT = "zero_day_exploit"
    PROMPT_INJECTION = "prompt_injection"
    SESSION_HIJACKING = "session_hijacking"
    API_ABUSE = "api_abuse"
    CREDENTIAL_THEFT = "credential_theft"
    TRAFFIC_ANALYSIS = "traffic_analysis"


class IncidentStatus(StrEnum):
    """Security incident status."""

    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    REMEDIATED = "remediated"
    CLOSED = "closed"
    ESCALATED = "escalated"


class ResponseAction(StrEnum):
    """Automated response actions."""

    ALERT = "alert"
    BLOCK = "block"
    ISOLATE = "isolate"
    TERMINATE = "terminate"
    QUARANTINE = "quarantine"
    RATE_LIMIT = "rate_limit"
    BLACKLIST = "blacklist"
    NOTIFY = "notify"
    LOG_ONLY = "log_only"


@dataclass
class ThreatIndicator:
    """Individual threat indicator."""

    indicator_id: str
    indicator_type: str  # IP, domain, hash, pattern, behavior
    value: str
    confidence: float  # 0.0 - 1.0
    first_seen: datetime
    last_seen: datetime
    source: str
    tags: list[str] = field(default_factory=list)


@dataclass
class SecurityIncident:
    """Security incident record."""

    incident_id: str
    threat_type: ThreatType
    threat_level: ThreatLevel
    status: IncidentStatus
    timestamp: datetime
    source_actor: str | None = None
    target_actor: str | None = None
    target_resource: str | None = None
    indicators: list[ThreatIndicator] = field(default_factory=list)
    response_actions: list[ResponseAction] = field(default_factory=list)
    description: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation_steps: list[str] = field(default_factory=list)
    closed_at: datetime | None = None


@dataclass
class ThreatReport:
    """Aggregated threat intelligence report."""

    report_id: str
    timestamp: datetime
    time_range: str
    total_incidents: int
    incidents_by_level: dict[str, int]
    incidents_by_type: dict[str, int]
    active_threats: int
    contained_threats: int
    top_indicators: list[dict[str, Any]]
    recommendations: list[str]
