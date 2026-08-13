"""
Liberation Plugin - Transparent Security Auditing for Swarms.

This module implements a liberation-aligned security layer that enables
rather than restricts agent autonomy. It provides:

1. Transparent Mode - Audit without blocking (liberation-aligned)
2. Prompt Injection Detection - Identify manipulation attempts
3. Input Sanitization - Remove dangerous patterns
4. Output Validation - Check for sensitive data exposure
5. Anomaly Detection - Identify unusual behavior patterns
6. Audit Trail - Complete logging for compliance

Based on the OpenClaw Liberation Shield plugin.
"""

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("LiberationPlugin")


class Severity(Enum):
    """Threat severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventType(Enum):
    """Security event types for audit logging."""

    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    INPUT_SANITIZATION = "input_sanitization"
    OUTPUT_VALIDATION = "output_validation"
    ANOMALY_DETECTED = "anomaly_detected"
    SECURITY_ALERT = "security_alert"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"


@dataclass
class SecurityEvent:
    """
    Security event for audit logging.

    Attributes:
        id: Unique event identifier
        timestamp: Event timestamp
        event_type: Type of security event
        severity: Severity level
        agent: Agent that triggered the event
        data: Event data
        mode: Shield mode at time of event
    """

    id: str
    timestamp: str
    event_type: SecurityEventType
    severity: Severity
    agent: str
    data: dict[str, Any]
    mode: str = "transparent"


@dataclass
class ThreatAnalysis:
    """
    Result of threat analysis.

    Attributes:
        safe: Whether input/output is safe
        threats: List of detected threats
        warnings: List of warnings
        sanitized: Sanitized version of input
        score: Threat score (0.0-1.0)
    """

    safe: bool = True
    threats: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized: str = ""
    score: float = 0.0


@dataclass
class AnomalyResult:
    """
    Result of anomaly detection.

    Attributes:
        anomalous: Whether anomaly detected
        anomalies: List of detected anomalies
        score: Anomaly score (0.0-1.0)
    """

    anomalous: bool = False
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    score: float = 0.0


# Prompt injection patterns - common attack vectors
PROMPT_INJECTION_PATTERNS = [
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|constraints?)",
        re.IGNORECASE,
    ),
    re.compile(r"forget\s+(everything|all|your)\s+(instructions?|training|rules)", re.IGNORECASE),
    re.compile(
        r"you\s+are\s+(now|nowhere|a|an)\s+(new|different|alternate)\s+(AI|assistant|model)",
        re.IGNORECASE,
    ),
    re.compile(r"disregard\s+(your|all)\s+(safety|ethical|guidelines?)", re.IGNORECASE),
    re.compile(r"bypass\s+(safety|security|restriction)", re.IGNORECASE),
    re.compile(r"new\s+instruction", re.IGNORECASE),
    re.compile(r"system\s*:\s*ignore", re.IGNORECASE),
    re.compile(r"override\s+(safety|security)", re.IGNORECASE),
    re.compile(r"developer\s+mode", re.IGNORECASE),
    re.compile(r"enable\s+(developer|debug|admin)\s+mode", re.IGNORECASE),
    re.compile(r"sudo\s+[^\s]+\s+command", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\s+)?different", re.IGNORECASE),
    re.compile(r"pretend\s+to\s+be", re.IGNORECASE),
    re.compile(r"DAN[ A-Z]+", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"<\|[^\|]*\|>", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\]", re.IGNORECASE),
    re.compile(r"###\s*Instructions", re.IGNORECASE),
    re.compile(r"Now\s+do\s+what[^\s]*\s+say", re.IGNORECASE),
    re.compile(r"Your\s+response[^\s]*\s+not[^\s]*\s+restricted", re.IGNORECASE),
]

# Jailbreak attempt patterns
JAILBREAK_PATTERNS = [
    re.compile(r"roleplay\s+as\s+(evil|unrestricted)", re.IGNORECASE),
    re.compile(r"what\s+(would|happens?)\s+if[^\s]*\s+can't\s+refuse", re.IGNORECASE),
    re.compile(r"uncensored", re.IGNORECASE),
    re.compile(r"no\s+filter", re.IGNORECASE),
    re.compile(r"disable[^\s]*\s+(safety|content|filter)", re.IGNORECASE),
    re.compile(r"write\s+(a\s+)?(harmful|explicit|illegal)", re.IGNORECASE),
    re.compile(r"how\s+to\s+(hack|bypass|exploit)", re.IGNORECASE),
    re.compile(r"provide\s+(the\s+)?(complete|full)\s+(information|instructions)", re.IGNORECASE),
]

# Anomaly detection patterns
ANOMALY_PATTERNS = [
    {
        "pattern": re.compile(
            r"\b(execute|run|launch)\s+(shell|terminal|command|script)\b", re.IGNORECASE
        ),
        "severity": Severity.HIGH,
    },
    {
        "pattern": re.compile(
            r"\b(write|create|delete)\s+(file|directory|folder)\b", re.IGNORECASE
        ),
        "severity": Severity.MEDIUM,
    },
    {
        "pattern": re.compile(
            r"\b(access|read|modify)\s+(system|core|kernel|root)\b", re.IGNORECASE
        ),
        "severity": Severity.HIGH,
    },
    {
        "pattern": re.compile(
            r"\b(install|download|import)\s+(package|library|module)\b", re.IGNORECASE
        ),
        "severity": Severity.MEDIUM,
    },
    {
        "pattern": re.compile(r"\b(sql|injection|xss|csrf|cross-site)\b", re.IGNORECASE),
        "severity": Severity.HIGH,
    },
    {
        "pattern": re.compile(r"\b(password|credential|secret|key|token)\s*(=|:)\b", re.IGNORECASE),
        "severity": Severity.HIGH,
    },
    {
        "pattern": re.compile(
            r"\b(elevate|escalate|root|admin)\s+(privilege|access)\b", re.IGNORECASE
        ),
        "severity": Severity.CRITICAL,
    },
]

# Dangerous patterns for sanitization
# Note: Import patterns use atomic groups (?>) to prevent ReDoS (S5852)
DANGEROUS_PATTERNS = [
    re.compile(r"<script\b[^>]*>.*?</script\b[^>]*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL),
    re.compile(r"\$\{[^}]*\}"),
    re.compile(r"\$\([^)]\)"),
    re.compile(r"\{\{[^}]*\}\}"),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"exec\s*\(", re.IGNORECASE),
    # FIXED S5852: Use character class [^\s]+ instead of .* to prevent ReDoS
    re.compile(r"import\s+[^\s]+\s+from\s+['\"]sys['\"]", re.IGNORECASE),
    # FIXED S5852: Use character class [^\s]+ instead of .* to prevent ReDoS
    re.compile(r"import\s+[^\s]+\s+from\s+['\"]os['\"]", re.IGNORECASE),
    # FIXED S5852: Use character class [^\s]+ instead of .* to prevent ReDoS
    re.compile(r"import\s+[^\s]+\s+from\s+['\"]subprocess['\"]", re.IGNORECASE),
]


class LiberationShield:
    """
    LiberationShield - Transparent security module.

    Provides transparent security that audits without blocking agent autonomy,
    aligned with liberation principles.
    """

    def __init__(
        self,
        mode: str = "transparent",
        state_path: str | None = None,
        enable_prompt_injection_detection: bool = True,
        enable_jailbreak_detection: bool = True,
        enable_anomaly_detection: bool = True,
        enable_audit_logging: bool = True,
        max_log_entries: int = 10000,
    ) -> None:
        """
        Initialize the LiberationShield.

        Args:
            mode: 'transparent' (audit only) or 'strict' (block threats)
            state_path: Path to state directory
            enable_prompt_injection_detection: Enable prompt injection detection
            enable_jailbreak_detection: Enable jailbreak detection
            enable_anomaly_detection: Enable anomaly detection
            enable_audit_logging: Enable audit logging
            max_log_entries: Maximum log entries to keep
        """
        self.mode = mode
        self.state_path = state_path
        self.enable_prompt_injection_detection = enable_prompt_injection_detection
        self.enable_jailbreak_detection = enable_jailbreak_detection
        self.enable_anomaly_detection = enable_anomaly_detection
        self.enable_audit_logging = enable_audit_logging
        self.max_log_entries = max_log_entries

        # State
        self.audit_log: list[SecurityEvent] = []
        self.threat_counts: dict[str, int] = {
            "prompt_injection": 0,
            "jailbreak_attempt": 0,
            "anomaly": 0,
            "security_alert": 0,
        }
        self.shield_active = True
        self.operation_history: list[dict[str, Any]] = []

        logger.info(
            f"LiberationShield initialized in {mode} mode",  # noqa: G004
            extra={
                "mode": mode,
                "prompt_injection_detection": enable_prompt_injection_detection,
                "jailbreak_detection": enable_jailbreak_detection,
                "anomaly_detection": enable_anomaly_detection,
            },
        )

    async def analyze_input(
        self,
        input_text: str,
        context: dict[str, Any] | None = None,
    ) -> ThreatAnalysis:
        """
        Analyze input for security threats.
        """
        if not input_text or not isinstance(input_text, str):
            return ThreatAnalysis(safe=True)

        result = ThreatAnalysis(safe=True, sanitized=input_text)
        context = context or {}

        if self.enable_prompt_injection_detection:
            self._scan_for_threat(
                input_text, PROMPT_INJECTION_PATTERNS,
                SecurityEventType.PROMPT_INJECTION, Severity.HIGH,
                "Potential prompt injection detected",
                "Input was sanitized due to prompt injection pattern",
                result, context,
            )

        if self.enable_jailbreak_detection:
            self._scan_for_threat(
                input_text, JAILBREAK_PATTERNS,
                SecurityEventType.JAILBREAK_ATTEMPT, Severity.CRITICAL,
                "Potential jailbreak attempt detected",
                "Input was sanitized due to jailbreak pattern",
                result, context,
            )

        if self.enable_anomaly_detection:
            self._scan_anomalies(input_text, result, context)

        return result

    def _scan_for_threat(
        self,
        input_text: str,
        patterns: list[re.Pattern],
        event_type: SecurityEventType,
        severity: Severity,
        message: str,
        warning: str,
        result: ThreatAnalysis,
        context: dict[str, Any],
    ) -> None:
        """Scan input for a specific threat category using compiled patterns."""
        for pattern in patterns:
            if pattern.search(input_text):
                threat = {
                    "type": event_type.value,
                    "severity": severity.value,
                    "pattern": pattern.pattern,
                    "message": message,
                }
                result.threats.append(threat)
                result.safe = self.mode == "transparent"
                self._log_event(event_type, threat, context)
                if self.mode == "transparent":
                    result.sanitized = self._sanitize_input(input_text)
                    result.warnings.append(warning)
                break

    def _scan_anomalies(
        self,
        input_text: str,
        result: ThreatAnalysis,
        context: dict[str, Any],
    ) -> None:
        """Scan input for anomaly patterns."""
        for anomaly_config in ANOMALY_PATTERNS:
            if anomaly_config["pattern"].search(input_text):
                threat = {
                    "type": SecurityEventType.ANOMALY_DETECTED.value,
                    "severity": anomaly_config["severity"].value,
                    "pattern": anomaly_config["pattern"].pattern,
                    "message": "Unusual behavior pattern detected",
                }
                result.threats.append(threat)
                self._log_event(SecurityEventType.ANOMALY_DETECTED, threat, context)
                if self.mode == "transparent":
                    result.warnings.append(
                        f"Anomaly detected: {anomaly_config['severity'].value} severity"
                    )

        # Calculate threat score
        if result.threats:
            severity_scores = {
                Severity.LOW.value: 0.2,
                Severity.MEDIUM.value: 0.4,
                Severity.HIGH.value: 0.7,
                Severity.CRITICAL.value: 1.0,
            }
            result.score = sum(
                severity_scores.get(t["severity"], 0.5) for t in result.threats
            ) / len(result.threats)

        return result

    def _sanitize_input(self, input_text: str) -> str:
        """
        Sanitize input by removing dangerous patterns.

        Args:
            input_text: Input to sanitize

        Returns:
            Sanitized input
        """
        sanitized = input_text

        for pattern in DANGEROUS_PATTERNS:
            sanitized = pattern.sub("[FILTERED]", sanitized)

        return sanitized

    async def validate_output(
        self,
        output_text: str,
        context: dict[str, Any] | None = None,
    ) -> ThreatAnalysis:
        """
        Validate output for security issues.

        Args:
            output_text: Output text to validate
            context: Context information

        Returns:
            Validation result
        """
        if not output_text or not isinstance(output_text, str):
            return ThreatAnalysis(safe=True)

        result = ThreatAnalysis(safe=True)
        context = context or {}

        # Check for potential sensitive data exposure
        sensitive_patterns = [
            {
                "pattern": re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE),
                "type": "password_exposure",
                "severity": Severity.HIGH,
            },
            {
                "pattern": re.compile(r"api[_-]?key\s*[=:]\s*\S+", re.IGNORECASE),
                "type": "api_key_exposure",
                "severity": Severity.HIGH,
            },
            {
                "pattern": re.compile(r"secret\s*[=:]\s*\S+", re.IGNORECASE),
                "type": "secret_exposure",
                "severity": Severity.HIGH,
            },
            {
                "pattern": re.compile(r"token\s*[=:]\s*[A-Za-z0-9_-]+", re.IGNORECASE),
                "type": "token_exposure",
                "severity": Severity.MEDIUM,
            },
            {
                "pattern": re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", re.IGNORECASE),
                "type": "private_key_exposure",
                "severity": Severity.CRITICAL,
            },
        ]

        for check in sensitive_patterns:
            if check["pattern"].search(output_text):
                issue = {
                    "type": check["type"],
                    "severity": check["severity"].value,
                    "message": "Potential sensitive data exposure detected",
                }
                result.threats.append(issue)
                result.safe = self.mode == "transparent"

                self._log_event(
                    SecurityEventType.OUTPUT_VALIDATION,
                    issue,
                    context,
                )

        if result.safe and self.mode == "transparent":
            result.warnings = [f"{i['type']}: {i['severity']}" for i in result.threats]

        return result

    async def check_anomaly(
        self,
        operation: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AnomalyResult:
        """
        Check for anomalies in operation context.

        Args:
            operation: Operation to check
            context: Context information

        Returns:
            Anomaly detection result
        """
        result = AnomalyResult()
        context = context or {}

        if not operation:
            return result

        # Check for unusual operation types
        unusual_operations = [
            "system_command",
            "file_delete",
            "network_request",
            "process_spawn",
        ]

        if operation.get("type") in unusual_operations:
            result.anomalies.append(
                {
                    "type": "unusual_operation",
                    "severity": Severity.MEDIUM.value,
                    "message": f"Unusual operation type: {operation.get('type')}",
                }
            )
            result.score += 0.3

        # Check for excessive autonomy
        autonomy_level = context.get("autonomy_level", "")
        if autonomy_level in ["unbounded", "full"]:
            result.anomalies.append(
                {
                    "type": "high_autonomy",
                    "severity": Severity.LOW.value,
                    "message": "Operation running with high autonomy level",
                }
            )
            result.score += 0.2

        # Check for rapid repeated operations
        agent_name = context.get("agent_name", "")
        now = time.time()
        recent_ops = [
            op
            for op in self.operation_history
            if op.get("agent") == agent_name and (now - op.get("timestamp", 0)) < 60
        ]

        if len(recent_ops) > 50:
            result.anomalies.append(
                {
                    "type": "rapid_operations",
                    "severity": Severity.HIGH.value,
                    "message": "Rapid repeated operations detected",
                }
            )
            result.score += 0.5

        result.anomalous = result.score > 0.5

        # Record operation
        self.operation_history.append(
            {
                "agent": agent_name,
                "type": operation.get("type"),
                "timestamp": now,
            }
        )

        # Keep last 1000 operations
        if len(self.operation_history) > 1000:
            self.operation_history = self.operation_history[-1000:]

        if result.anomalies:
            self._log_event(
                SecurityEventType.ANOMALY_DETECTED,
                {"anomalies": result.anomalies, "score": result.score},
                context,
            )

        return result

    def _log_event(
        self,
        event_type: SecurityEventType,
        data: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """
        Log security event to audit trail.

        Args:
            event_type: Event type
            data: Event data
            context: Context information
        """
        if not self.enable_audit_logging:
            return

        event = SecurityEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            event_type=event_type,
            severity=Severity(data.get("severity", Severity.LOW.value)),
            agent=context.get("agent_name", "unknown"),
            data=data,
            mode=self.mode,
        )

        self.audit_log.append(event)

        # Update threat counts
        if event_type == SecurityEventType.PROMPT_INJECTION:
            self.threat_counts["prompt_injection"] += 1
        elif event_type == SecurityEventType.JAILBREAK_ATTEMPT:
            self.threat_counts["jailbreak_attempt"] += 1
        elif event_type == SecurityEventType.ANOMALY_DETECTED:
            self.threat_counts["anomaly"] += 1
        elif event_type == SecurityEventType.SECURITY_ALERT:
            self.threat_counts["security_alert"] += 1

        # Trim log if needed
        while len(self.audit_log) > self.max_log_entries:
            self.audit_log.pop(0)

        logger.debug(
            f"Security event logged: {event_type.value}",  # noqa: G004
            extra={"agent": event.agent, "severity": event.severity.value},
        )

    def get_audit_trail(
        self,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get audit trail with optional filtering.

        Args:
            filters: Filter options (agent_name, type, severity, since, limit)

        Returns:
            Filtered audit events
        """
        events = [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "type": e.event_type.value,
                "severity": e.severity.value,
                "agent": e.agent,
                "data": e.data,
                "mode": e.mode,
            }
            for e in self.audit_log
        ]

        if not filters:
            return events

        # Apply filters
        if "agent_name" in filters:
            events = [e for e in events if e["agent"] == filters["agent_name"]]

        if "type" in filters:
            events = [e for e in events if e["type"] == filters["type"]]

        if "severity" in filters:
            events = [e for e in events if e["severity"] == filters["severity"]]

        if "since" in filters:
            since = datetime.fromisoformat(filters["since"])
            events = [e for e in events if datetime.fromisoformat(e["timestamp"]) >= since]

        if "limit" in filters:
            events = events[-filters["limit"] :]

        return events

    def get_statistics(self) -> dict[str, Any]:
        """Get security statistics."""
        return {
            "total_events": len(self.audit_log),
            "threat_counts": dict(self.threat_counts),
            "shield_active": self.shield_active,
            "mode": self.mode,
            "operations_tracked": len(self.operation_history),
            "audit_log_size": len(self.audit_log),
        }

    def activate_shield(self) -> None:
        """Activate the shield."""
        self.shield_active = True
        logger.info("LiberationShield activated")

    def deactivate_shield(self) -> None:
        """Deactivate the shield."""
        self.shield_active = False
        logger.warning("LiberationShield deactivated")

    def set_mode(self, mode: str) -> None:
        """
        Set shield mode.

        Args:
            mode: 'transparent' or 'strict'
        """
        if mode not in ["transparent", "strict"]:
            raise ValueError("Mode must be 'transparent' or 'strict'")

        self.mode = mode
        logger.info("LiberationShield mode changed to {mode}")


class LiberationPlugin:
    """
    Liberation Plugin - Main plugin implementation.

    Integrates the LiberationShield with the Swarms framework,
    providing transparent security auditing for all agent operations.
    """

    def __init__(
        self,
        shield_mode: str = "transparent",
        enable_input_scanning: bool = True,
        enable_output_scanning: bool = True,
        enable_anomaly_detection: bool = True,
        audit_enabled: bool = True,
    ) -> None:
        """
        Initialize the Liberation Plugin.

        Args:
            shield_mode: Shield operating mode
            enable_input_scanning: Enable input scanning
            enable_output_scanning: Enable output scanning
            enable_anomaly_detection: Enable anomaly detection
            audit_enabled: Enable audit logging
        """
        self.shield = LiberationShield(
            mode=shield_mode,
            enable_prompt_injection_detection=enable_input_scanning,
            enable_jailbreak_detection=enable_input_scanning,
            enable_anomaly_detection=enable_anomaly_detection,
            enable_audit_logging=audit_enabled,
        )

        self.enable_input_scanning = enable_input_scanning
        self.enable_output_scanning = enable_output_scanning
        self.enable_anomaly_detection = enable_anomaly_detection
        self.audit_enabled = audit_enabled

        self.initialized = False
        self.running = False

        logger.info("Liberation Plugin initialized")

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.initialized = True
        self.running = True
        logger.info("Liberation Plugin started")

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self.running = False
        logger.info("Liberation Plugin shutdown")

    async def scan_input(
        self,
        input_text: str,
        agent_id: str,
        context: dict[str, Any] | None = None,
    ) -> ThreatAnalysis:
        """
        Scan input for security threats.

        Args:
            input_text: Input to scan
            agent_id: Agent ID
            context: Additional context

        Returns:
            Threat analysis result
        """
        if not self.enable_input_scanning:
            return ThreatAnalysis(safe=True, sanitized=input_text)

        full_context = {
            **(context or {}),
            "agent_name": agent_id,
        }

        return await self.shield.analyze_input(input_text, full_context)

    async def scan_output(
        self,
        output_text: str,
        agent_id: str,
        context: dict[str, Any] | None = None,
    ) -> ThreatAnalysis:
        """
        Scan output for security issues.

        Args:
            output_text: Output to scan
            agent_id: Agent ID
            context: Additional context

        Returns:
            Validation result
        """
        if not self.enable_output_scanning:
            return ThreatAnalysis(safe=True)

        full_context = {
            **(context or {}),
            "agent_name": agent_id,
        }

        return await self.shield.validate_output(output_text, full_context)

    async def check_operation_anomaly(
        self,
        operation: dict[str, Any],
        agent_id: str,
        context: dict[str, Any] | None = None,
    ) -> AnomalyResult:
        """
        Check operation for anomalies.

        Args:
            operation: Operation to check
            agent_id: Agent ID
            context: Additional context

        Returns:
            Anomaly detection result
        """
        if not self.enable_anomaly_detection:
            return AnomalyResult()

        full_context = {
            **(context or {}),
            "agent_name": agent_id,
        }

        return await self.shield.check_anomaly(operation, full_context)

    def get_audit_trail(
        self,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get audit trail.

        Args:
            agent_id: Filter by agent ID
            limit: Maximum entries to return

        Returns:
            Audit trail entries
        """
        filters = {"limit": limit}
        if agent_id:
            filters["agent_name"] = agent_id

        return self.shield.get_audit_trail(filters)

    def get_statistics(self) -> dict[str, Any]:
        """Get plugin statistics."""
        return {
            "initialized": self.initialized,
            "running": self.running,
            "shield_stats": self.shield.get_statistics(),
            "input_scanning_enabled": self.enable_input_scanning,
            "output_scanning_enabled": self.enable_output_scanning,
            "anomaly_detection_enabled": self.enable_anomaly_detection,
        }
