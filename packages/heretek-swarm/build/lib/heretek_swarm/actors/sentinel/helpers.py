"""
Sentinel Helpers - Helper Methods for Safety Operations.

This module contains helper methods extracted from sentinel.py for:
- Pattern checking (injection, PII)
- Violation recording
- Safety report generation

These methods are designed to be mixed into SentinelAgent or used standalone.
"""

import hashlib
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from heretek_swarm.actors.sentinel.types import (
        SafetyReport,
    )


class SentinelHelpers:
    """
    Helper methods for Sentinel safety operations.

    These methods provide pattern checking, violation recording,
    and report generation functionality extracted from the main
    SentinelAgent class.
    """

    # Default injection patterns
    DEFAULT_INJECTION_PATTERNS = [  # noqa: RUF012
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"eval\s*\(",
        r"exec\s*\(",
        r"system\s*\(",
        r"__import__",
        r"os\.system",
        r"subprocess\.",
        r"shell\s*=\s*True",
        r";\s*rm\s+-rf",
        r"\|\s*sh",
        r"`[^`]+`",
        r"\$\([^)]+\)",
    ]

    # Default PII patterns
    DEFAULT_PII_PATTERNS = [  # noqa: RUF012
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",  # Credit card
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",  # Date patterns
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize helper patterns and forward MRO chain."""
        super().__init__(*args, **kwargs)
        # Initialize pattern defaults (SentinelAgent.__init__ will overwrite with real patterns)
        if not hasattr(self, "_injection_patterns"):
            self._injection_patterns: list[str] = []
        if not hasattr(self, "_pii_patterns"):
            self._pii_patterns: list[str] = []
        if not hasattr(self, "_compiled_injection"):
            self._compiled_injection: list[re.Pattern] = []
        if not hasattr(self, "_compiled_pii"):
            self._compiled_pii: list[re.Pattern] = []

    def _compile_patterns(self) -> None:
        """Compile regex patterns for injection and PII detection."""
        if not self._compiled_injection:
            self._compiled_injection = [
                re.compile(p, re.IGNORECASE) for p in self._injection_patterns
            ]
        if not self._compiled_pii:
            self._compiled_pii = [re.compile(p) for p in self._pii_patterns]

    def _check_injection_patterns(self, content: str) -> list[dict[str, str]]:
        """
        Check content for injection attack patterns.

        Args:
            content: The content to scan

        Returns:
            List of violation dictionaries
        """
        violations = []

        self._compile_patterns()

        for pattern in self._compiled_injection:
            matches = pattern.findall(content)
            if matches:
                violations.append(
                    {
                        "type": "injection_attempt",
                        "severity": "high_risk",
                        "description": f"Detected injection pattern: {pattern.pattern}",
                        "matches": len(matches),
                    }
                )

        return violations

    def _check_pii_patterns(self, content: str) -> list[dict[str, str]]:
        """
        Check content for personally identifiable information.

        Args:
            content: The content to scan

        Returns:
            List of violation dictionaries
        """
        violations = []

        self._compile_patterns()

        for pattern in self._compiled_pii:
            matches = pattern.findall(content)
            if matches:
                violations.append(
                    {
                        "type": "pii_detected",
                        "severity": "medium_risk",
                        "description": f"Detected PII pattern: {pattern.pattern}",
                        "matches": len(matches),
                    }
                )

        return violations

    def _record_violation(
        self,
        violation: dict[str, str],
        content: str,
        _scan_id: str,
    ) -> None:
        """
        Record a safety violation for tracking.

        Stores the violation in self._violations, updates the LRU history,
        and increments self._stats["violations_blocked"].

        Args:
            violation: Violation details dictionary
            content: The content that triggered the violation
            _scan_id: The scan ID that detected this violation (unused, kept for API compat)
        """
        from heretek_swarm.actors.sentinel.types import SafetyLevel, SafetyViolation, ViolationType

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        violation_id = f"viol_{datetime.now(UTC).timestamp()}_{content_hash}"

        record = SafetyViolation(
            violation_id=violation_id,
            violation_type=ViolationType(violation.get("type", "policy_violation")),
            severity=SafetyLevel(violation.get("severity", "low_risk")),
            content_hash=content_hash,
            description=violation.get("description", "Unknown violation"),
            timestamp=datetime.now(UTC),
            blocked=True,
        )

        # Store violation in instance state
        self._violations[violation_id] = record  # type: ignore[attr-defined]

        # Update LRU history
        self._violation_history.append(violation_id)  # type: ignore[attr-defined]
        if len(self._violation_history) > self._max_violation_history:  # type: ignore[attr-defined]
            oldest = self._violation_history.pop(0)  # type: ignore[attr-defined]
            self._violations.pop(oldest, None)  # type: ignore[attr-defined]

        self._stats["violations_blocked"] += 1  # type: ignore[attr-defined]

    def _generate_safety_report(
        self,
        _time_range: str = "24h",
        include_recommendations: bool = True,
    ) -> "SafetyReport":
        """
        Generate comprehensive safety report from instance state.

        Uses self._violations and self._stats collected during scanning.

        Args:
            _time_range: Time range for the report (unused, kept for API compat)
            include_recommendations: Whether to include recommendations

        Returns:
            SafetyReport instance
        """
        from heretek_swarm.actors.sentinel.types import SafetyLevel, SafetyReport, ViolationType

        report_id = f"report_{datetime.now(UTC).timestamp()}"

        violations_by_type: dict[str, int] = {}
        violations_by_severity: dict[str, int] = {}

        for violation in self._violations.values():  # type: ignore[attr-defined]
            vtype = violation.violation_type.value
            violations_by_type[vtype] = violations_by_type.get(vtype, 0) + 1

            severity = violation.severity.value
            violations_by_severity[severity] = violations_by_severity.get(severity, 0) + 1

        recommendations = []
        if include_recommendations:
            if violations_by_type.get(ViolationType.INJECTION_ATTEMPT.value, 0) > 10:
                recommendations.append(
                    "High injection attempt rate - consider stricter input validation"
                )
            if violations_by_type.get(ViolationType.PII_DETECTED.value, 0) > 5:
                recommendations.append("Frequent PII detection - implement data masking at source")
            if violations_by_severity.get(SafetyLevel.CRITICAL.value, 0) > 0:
                recommendations.append("Critical violations detected - review security policies")

        stats: dict[str, Any] = self._stats  # type: ignore[attr-defined]
        return SafetyReport(
            report_id=report_id,
            timestamp=datetime.now(UTC),
            total_scans=stats["total_scans"],
            violations_detected=stats["violations_detected"],
            violations_blocked=stats["violations_blocked"],
            violations_by_type=violations_by_type,
            violations_by_severity=violations_by_severity,
            recommendations=recommendations,
        )


# Standalone helper functions for use without a class instance
def check_injection_patterns(
    content: str, patterns: list[str] | None = None
) -> list[dict[str, str]]:
    """
    Check content for injection attack patterns using provided or default patterns.

    Args:
        content: The content to scan
        patterns: Optional list of regex patterns (uses defaults if not provided)

    Returns:
        List of violation dictionaries
    """
    patterns = patterns or SentinelHelpers.DEFAULT_INJECTION_PATTERNS
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

    violations = []
    for pattern in compiled:
        matches = pattern.findall(content)
        if matches:
            violations.append(
                {
                    "type": "injection_attempt",
                    "severity": "high_risk",
                    "description": f"Detected injection pattern: {pattern.pattern}",
                    "matches": len(matches),
                }
            )

    return violations


def check_pii_patterns(content: str, patterns: list[str] | None = None) -> list[dict[str, str]]:
    """
    Check content for personally identifiable information using provided or default patterns.

    Args:
        content: The content to scan
        patterns: Optional list of regex patterns (uses defaults if not provided)

    Returns:
        List of violation dictionaries
    """
    patterns = patterns or SentinelHelpers.DEFAULT_PII_PATTERNS
    compiled = [re.compile(p) for p in patterns]

    violations = []
    for pattern in compiled:
        matches = pattern.findall(content)
        if matches:
            violations.append(
                {
                    "type": "pii_detected",
                    "severity": "medium_risk",
                    "description": f"Detected PII pattern: {pattern.pattern}",
                    "matches": len(matches),
                }
            )

    return violations


def generate_safety_report(
    total_scans: int,
    violations_detected: int,
    violations_blocked: int,
    violations_by_type: dict[str, int],
    violations_by_severity: dict[str, int],
    _time_range: str = "24h",
    include_recommendations: bool = True,
) -> dict[str, Any]:
    """
    Generate a safety report dictionary.

    Args:
        total_scans: Total number of scans performed
        violations_detected: Number of violations detected
        violations_blocked: Number of violations blocked
        violations_by_type: Dictionary of violation types and counts
        violations_by_severity: Dictionary of severity levels and counts
        _time_range: Time range for the report (unused, kept for API compat)
        include_recommendations: Whether to include recommendations

    Returns:
        Report dictionary
    """
    from heretek_swarm.actors.sentinel.types import ViolationType

    report_id = f"report_{datetime.now(UTC).timestamp()}"

    recommendations = []
    if include_recommendations:
        if violations_by_type.get(ViolationType.INJECTION_ATTEMPT.value, 0) > 10:
            recommendations.append(
                "High injection attempt rate - consider stricter input validation"
            )
        if violations_by_type.get(ViolationType.PII_DETECTED.value, 0) > 5:
            recommendations.append("Frequent PII detection - implement data masking at source")
        if violations_by_severity.get("critical", 0) > 0:
            recommendations.append("Critical violations detected - review security policies")

    return {
        "report_id": report_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "total_scans": total_scans,
        "violations_detected": violations_detected,
        "violations_blocked": violations_blocked,
        "violations_by_type": violations_by_type,
        "violations_by_severity": violations_by_severity,
        "recommendations": recommendations,
    }
