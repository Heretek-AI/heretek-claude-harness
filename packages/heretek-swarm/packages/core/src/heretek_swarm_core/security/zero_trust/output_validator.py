"""Layer 3: Output Validation — PII detection, sensitive data filtering, response sanitization."""

import re
import time
from dataclasses import dataclass
from typing import Any

import structlog

from .result_types import LayerResult, Severity

logger = structlog.get_logger(__name__)


@dataclass
class OutputValidationConfig:
    """Configuration for Layer 3 Output Validation."""

    enable_pii_detection: bool = True
    enable_sensitive_data_filtering: bool = True
    enable_response_sanitization: bool = True
    redact_pii: bool = True
    max_output_size: int = 100000


class OutputValidator:
    """Layer 3: Output Validation — PII detection, sensitive data filtering, response sanitization."""

    PII_PATTERNS = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]"),
        (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE_REDACTED]"),
        (r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b", "[SSN_REDACTED]"),
        (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "[CC_REDACTED]"),
        (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_REDACTED]"),
        (r'\b(?:api[_-]?key|apikey|token|secret|password)\s*[=:]\s*["\']?[a-zA-Z0-9_-]{16,}["\']?', "[API_KEY_REDACTED]"),
    ]

    SENSITIVE_PATTERNS = [
        (r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", "[PRIVATE_KEY_REDACTED]"),
        (r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}", "[AWS_KEY_REDACTED]"),
        (r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*", "[JWT_REDACTED]"),
    ]

    def __init__(self, config: OutputValidationConfig | None = None):
        self.config = config or OutputValidationConfig()
        self._compiled_pii = [
            (re.compile(p, re.IGNORECASE), replacement) for p, replacement in self.PII_PATTERNS
        ]
        self._compiled_sensitive = [
            (re.compile(p, re.IGNORECASE), replacement) for p, replacement in self.SENSITIVE_PATTERNS
        ]

    def validate(self, output: Any, agent_id: str | None = None) -> LayerResult:
        """Validate output data against Layer 3 rules."""
        start_time = time.time()
        output_str = str(output) if not isinstance(output, str) else output
        sanitized_output = output_str
        detected_pii: list[str] = []
        detected_sensitive: list[str] = []

        try:
            size_result = self._check_output_size(output_str)
            if size_result:
                return size_result

            if self.config.enable_pii_detection:
                detected_pii = self._scan_patterns(
                    self._compiled_pii, output_str, sanitized_output
                )
                if detected_pii and self.config.redact_pii:
                    sanitized_output = self._apply_redactions(
                        self._compiled_pii, sanitized_output
                    )

            if self.config.enable_sensitive_data_filtering:
                detected_sensitive = self._scan_patterns(
                    self._compiled_sensitive, output_str, sanitized_output
                )
                if detected_sensitive and self.config.redact_pii:
                    sanitized_output = self._apply_redactions(
                        self._compiled_sensitive, sanitized_output
                    )

            latency_ms = (time.time() - start_time) * 1000
            passed = True
            reason = None
            if (detected_pii or detected_sensitive) and not self.config.redact_pii:
                passed = False
                reason = f"PII or sensitive data detected: {detected_pii + detected_sensitive}"

            return LayerResult(
                layer="output",
                passed=passed,
                reason=reason,
                severity=Severity.WARNING if detected_pii or detected_sensitive else Severity.INFO,
                details={
                    "latency_ms": latency_ms,
                    "pii_detected": detected_pii,
                    "sensitive_detected": detected_sensitive,
                    "sanitized": self.config.redact_pii and (bool(detected_pii) or bool(detected_sensitive)),
                    "sanitized_output": sanitized_output,
                },
            )

        except Exception as e:
            logger.error("output_validation_error", error=str(e), agent_id=agent_id)
            return LayerResult(
                layer="output",
                passed=False,
                reason=f"Output validation error: {e}",
                severity=Severity.HIGH,
            )

    def _check_output_size(self, output_str: str) -> LayerResult | None:
        """Check if output exceeds max size; return LayerResult if too large."""
        if len(output_str) > self.config.max_output_size:
            return LayerResult(
                layer="output",
                passed=False,
                reason=f"Output size {len(output_str)} exceeds maximum {self.config.max_output_size}",
                severity=Severity.WARNING,
                details={"output_size": len(output_str), "max_size": self.config.max_output_size},
            )
        return None

    @staticmethod
    def _scan_patterns(
        compiled: list[tuple[re.Pattern, str]], text: str, _sanitized: str
    ) -> list[str]:
        """Scan text for compiled patterns, return list of matched pattern strings."""
        detected: list[str] = []
        for pattern, _replacement in compiled:
            if pattern.findall(text):
                detected.append(pattern.pattern)
        return detected

    @staticmethod
    def _apply_redactions(
        compiled: list[tuple[re.Pattern, str]], text: str
    ) -> str:
        """Apply all redaction patterns to text."""
        result = text
        for pattern, replacement in compiled:
            result = pattern.sub(replacement, result)
        return result

    def sanitize(self, output: str) -> str:
        """Sanitize output by redacting PII and sensitive data."""
        sanitized = output
        for pattern, replacement in self._compiled_pii:
            sanitized = pattern.sub(replacement, sanitized)
        for pattern, replacement in self._compiled_sensitive:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized
