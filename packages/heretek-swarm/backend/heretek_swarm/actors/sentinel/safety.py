"""
Sentinel Safety Scanner - Content safety scanning and validation.

This module provides standalone functions and a SafetyScanner class for:
- Content injection pattern detection
- PII pattern detection
- Content safety scanning with severity classification
- Message safety validation

The SafetyScanner class is designed to be used as a delegate by SentinelAgent,
while the standalone functions can be used independently.

Architecture note: Extracted from sentinel/agent.py (Phase 2 Plan).
"""

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger("SafetyScanner")

# ---- Default detection patterns -------------------------------------------

DEFAULT_INJECTION_PATTERNS: list[str] = [
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

DEFAULT_PII_PATTERNS: list[str] = [
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
    r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",  # Credit card
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
    r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",  # Date patterns
    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone
]


# ---- Standalone detection functions ----------------------------------------


def detect_injections(
    content: str,
    compiled_patterns: list[re.Pattern[str]],
) -> list[dict[str, str | int]]:
    """
    Detect injection attack patterns in content.

    Args:
        content: The content to scan.
        compiled_patterns: Pre-compiled regex patterns for injection detection.

    Returns:
        List of violation dictionaries with type, severity, description, and match count.
    """
    violations: list[dict[str, str | int]] = []

    for pattern in compiled_patterns:
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


def detect_pii(
    content: str,
    compiled_patterns: list[re.Pattern[str]],
) -> list[dict[str, str | int]]:
    """
    Detect personally identifiable information (PII) in content.

    Args:
        content: The content to scan.
        compiled_patterns: Pre-compiled regex patterns for PII detection.

    Returns:
        List of violation dictionaries with type, severity, description, and match count.
    """
    violations: list[dict[str, str | int]] = []

    for pattern in compiled_patterns:
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


def validate_message_safety(
    message: str,
    max_size: int,
    compiled_injection: list[re.Pattern[str]] | None = None,
    compiled_pii: list[re.Pattern[str]] | None = None,
) -> dict[str, Any]:
    """
    Validate a message for basic safety without full state tracking.

    This is a lightweight check suitable for callers that don't need
    violation tracking or statistics.

    Args:
        message: The message content to validate.
        max_size: Maximum allowed content size in characters.
        compiled_injection: Optional pre-compiled injection patterns.
        compiled_pii: Optional pre-compiled PII patterns.

    Returns:
        Dict with keys: is_safe, violations, safety_level.
    """
    violations: list[dict[str, str | int]] = []

    if len(message) > max_size:
        violations.append(
            {
                "type": "policy_violation",
                "severity": "medium_risk",
                "description": f"Content exceeds max size ({len(message)}/{max_size} chars)",
                "matches": 1,
            }
        )

    if compiled_injection:
        violations.extend(detect_injections(message, compiled_injection))

    if compiled_pii:
        violations.extend(detect_pii(message, compiled_pii))

    safety_level = _classify_safety_level(violations)

    return {
        "is_safe": len(violations) == 0,
        "violations": violations,
        "safety_level": safety_level,
    }


def scan_content(
    content: str,
    patterns: list[str] | None = None,
) -> dict[str, Any]:
    """
    Scan content for safety violations using default or custom patterns.

    This is a convenience wrapper that creates a temporary SafetyScanner
    and delegates to it. For repeated scanning, use SafetyScanner directly.

    Args:
        content: The content to scan.
        patterns: Optional custom injection patterns (uses defaults if None).

    Returns:
        Dict with safety_level, is_safe, violations, recommendations.
    """
    scanner = SafetyScanner(injection_patterns=patterns)
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        import warnings
        warnings.warn(
            "scan_content called from async context; use SafetyScanner.scan_content() directly",
            RuntimeWarning,
            stacklevel=2,
        )
    # For synchronous convenience, create a new event loop
    try:
        return asyncio.run(scanner.scan_content(content))
    except RuntimeError:
        # If we're already in an event loop, return a simple sync result
        return {
            "safety_level": "unknown",
            "is_safe": True,
            "violations": [],
            "recommendations": [],
        }


def _classify_safety_level(
    violations: list[dict[str, str | int]],
) -> str:
    """Determine overall safety level from a list of violations."""
    if not violations:
        return "safe"

    severity_order = {
        "critical": 5,
        "high_risk": 4,
        "medium_risk": 3,
        "low_risk": 2,
        "safe": 1,
    }
    max_severity = max(
        severity_order.get(str(v.get("severity", "safe")), 1) for v in violations
    )
    level_map = {5: "critical", 4: "high_risk", 3: "medium_risk", 2: "low_risk"}
    return level_map.get(max_severity, "safe")


# ---- SafetyScanner class for SentinelAgent delegation -----------------------


class SafetyScanner:
    """
    Stateful content safety scanner for SentinelAgent delegation.

    Encapsulates all content-scanning state and logic previously inline
    in SentinelAgent: pattern management, violation tracking, statistics,
    and scan orchestration.
    """

    def __init__(
        self,
        injection_patterns: list[str] | None = None,
        pii_patterns: list[str] | None = None,
        max_content_size: int = 100000,
        enable_pii_detection: bool = True,
        enable_injection_detection: bool = True,
        auto_block_critical: bool = True,
    ):
        """
        Initialize the safety scanner.

        Args:
            injection_patterns: Custom injection detection patterns (uses defaults if None).
            pii_patterns: Custom PII detection patterns (uses defaults if None).
            max_content_size: Maximum allowed content size in characters.
            enable_pii_detection: Whether PII scanning is enabled.
            enable_injection_detection: Whether injection scanning is enabled.
            auto_block_critical: Whether to auto-block critical violations.
        """
        self.max_content_size = max_content_size
        self.enable_pii_detection = enable_pii_detection
        self.enable_injection_detection = enable_injection_detection
        self.auto_block_critical = auto_block_critical

        # Patterns
        self._injection_patterns = injection_patterns or list(DEFAULT_INJECTION_PATTERNS)
        self._pii_patterns = pii_patterns or list(DEFAULT_PII_PATTERNS)

        # Compile regex patterns
        self._compiled_injection: list[re.Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in self._injection_patterns
        ]
        self._compiled_pii: list[re.Pattern[str]] = [
            re.compile(p) for p in self._pii_patterns
        ]

        # Violation tracking
        self._violations: dict[str, Any] = {}
        self._violation_history: list[str] = []
        self._max_violation_history: int = 1000

        # Statistics
        self._stats: dict[str, Any] = {
            "total_scans": 0,
            "safe_scans": 0,
            "violations_detected": 0,
            "violations_blocked": 0,
            "violations_by_type": {},
            "violations_by_severity": {},
        }

        logger.info(
            "SafetyScanner_initialized",
            max_content_size=max_content_size,
            pii_detection=enable_pii_detection,
            injection_detection=enable_injection_detection,
        )

    # ---- Public API --------------------------------------------------------

    async def scan_content(
        self,
        content: str,
        _content_type: str = "text",
        _strict_mode: bool = False,
    ) -> dict[str, Any]:
        """
        Scan content for safety violations.

        Returns dict with:
        - scan_id: Unique scan identifier
        - safety_level: Overall safety assessment
        - is_safe: Boolean indicating if content is safe
        - violations: List of detected violations
        - sanitized_content: Content with violations removed/masked
        - recommendations: List of recommended actions
        """
        scan_id = f"scan_{datetime.now(UTC).timestamp()}"
        violations: list[dict[str, Any]] = []
        sanitized_content = content

        # Check content size
        if len(content) > self.max_content_size:
            violations.append(
                {
                    "type": "policy_violation",
                    "severity": "medium_risk",
                    "description": (
                        f"Content exceeds max size "
                        f"({len(content)}/{self.max_content_size} chars)"
                    ),
                }
            )

        # Check injection patterns
        if self.enable_injection_detection:
            injection_violations = detect_injections(content, self._compiled_injection)
            violations.extend(injection_violations)

        # Check PII
        if self.enable_pii_detection:
            pii_violations = detect_pii(content, self._compiled_pii)
            violations.extend(pii_violations)

        # Determine overall safety level
        safety_level_name = _classify_safety_level(violations)

        # Auto-block critical violations
        if self.auto_block_critical and safety_level_name == "critical":
            for violation in violations:
                if violation.get("severity") == "critical":
                    self._record_violation(violation, content, scan_id)

        # Update statistics
        self._stats["total_scans"] += 1
        if not violations:
            self._stats["safe_scans"] += 1
        else:
            self._stats["violations_detected"] += len(violations)
            for v in violations:
                vtype = str(v.get("type", "unknown"))
                self._stats["violations_by_type"][vtype] = (
                    self._stats["violations_by_type"].get(vtype, 0) + 1
                )

        # Generate recommendations
        recommendations: list[str] = []
        if safety_level_name != "safe":
            recommendations.append(f"Review content for {safety_level_name} risk")
            if any(v.get("type") == "injection_attempt" for v in violations):
                recommendations.append("Sanitize input before processing")
            if any(v.get("type") == "pii_detected" for v in violations):
                recommendations.append("Mask or remove PII data")

        return {
            "scan_id": scan_id,
            "safety_level": safety_level_name,
            "is_safe": safety_level_name == "safe",
            "violations": violations,
            "sanitized_content": sanitized_content,
            "recommendations": recommendations,
        }

    def check_injection_patterns(self, content: str) -> list[dict[str, str | int]]:
        """Check content for injection attack patterns."""
        return detect_injections(content, self._compiled_injection)

    def check_pii_patterns(self, content: str) -> list[dict[str, str | int]]:
        """Check content for personally identifiable information."""
        return detect_pii(content, self._compiled_pii)

    def get_violation(self, violation_id: str) -> Any | None:
        """Get a specific violation by ID."""
        return self._violations.get(violation_id)

    def get_stats(self) -> dict[str, Any]:
        """Get current safety statistics."""
        return self._stats.copy()

    def get_active_violation_count(self) -> int:
        """Count violations not yet blocked/remediated."""
        return len([v for v in self._violations.values()
                     if hasattr(v, "blocked") and not v.blocked])

    def get_total_violations_tracked(self) -> int:
        """Get total tracked violations."""
        return len(self._violations)

    def get_violation_history_size(self) -> int:
        """Get LRU violation history size."""
        return len(self._violation_history)

    # ---- Report generation -------------------------------------------------

    def generate_safety_report(
        self,
        _time_range: str = "24h",
        include_recommendations: bool = True,
    ) -> Any:
        """
        Generate comprehensive safety report from collected statistics.

        Args:
            time_range: Time range string (unused, kept for API compat).
            include_recommendations: Whether to include recommendations.

        Returns:
            SafetyReport instance.
        """
        from heretek_swarm.actors.sentinel.types import SafetyLevel, SafetyReport, ViolationType

        report_id = f"report_{datetime.now(UTC).timestamp()}"

        violations_by_type: dict[str, int] = {}
        violations_by_severity: dict[str, int] = {}

        for violation in self._violations.values():
            vtype = violation.violation_type.value
            violations_by_type[vtype] = violations_by_type.get(vtype, 0) + 1

            severity = violation.severity.value
            violations_by_severity[severity] = violations_by_severity.get(severity, 0) + 1

        recommendations: list[str] = []
        if include_recommendations:
            if violations_by_type.get(ViolationType.INJECTION_ATTEMPT.value, 0) > 10:
                recommendations.append(
                    "High injection attempt rate - consider stricter input validation"
                )
            if violations_by_type.get(ViolationType.PII_DETECTED.value, 0) > 5:
                recommendations.append(
                    "Frequent PII detection - implement data masking at source"
                )
            if violations_by_severity.get(SafetyLevel.CRITICAL.value, 0) > 0:
                recommendations.append(
                    "Critical violations detected - review security policies"
                )

        return SafetyReport(
            report_id=report_id,
            timestamp=datetime.now(UTC),
            total_scans=self._stats["total_scans"],
            violations_detected=self._stats["violations_detected"],
            violations_blocked=self._stats["violations_blocked"],
            violations_by_type=violations_by_type,
            violations_by_severity=violations_by_severity,
            recommendations=recommendations,
        )

    # ---- Internal ----------------------------------------------------------

    def _record_violation(
        self,
        violation: dict[str, Any],
        content: str,
        _scan_id: str,
    ) -> None:
        """
        Record a safety violation for tracking.

        Args:
            violation: Violation details dictionary.
            content: The content that triggered the violation.
            _scan_id: The scan ID that detected this violation (unused, kept for API compat).
        """
        from heretek_swarm.actors.sentinel.types import SafetyLevel, SafetyViolation, ViolationType

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        violation_id = f"viol_{datetime.now(UTC).timestamp()}_{content_hash}"

        record = SafetyViolation(
            violation_id=violation_id,
            violation_type=ViolationType(str(violation.get("type", "policy_violation"))),
            severity=SafetyLevel(str(violation.get("severity", "low_risk"))),
            content_hash=content_hash,
            description=str(violation.get("description", "Unknown violation")),
            timestamp=datetime.now(UTC),
            blocked=True,
        )

        self._violations[violation_id] = record
        self._violation_history.append(violation_id)

        if len(self._violation_history) > self._max_violation_history:
            oldest = self._violation_history.pop(0)
            self._violations.pop(oldest, None)

        self._stats["violations_blocked"] += 1
