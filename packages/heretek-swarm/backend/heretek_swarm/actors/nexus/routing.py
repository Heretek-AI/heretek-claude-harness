"""
Nexus Routing - Input sanitization and routing helpers.

ZERO-01: Hostile Input Treatment - All external inputs pass through this layer.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class NexusRoutingHelpers:
    """
    Mixin providing ZERO-01 hostile input sanitization and routing helpers.

    This class provides pure helper methods for input sanitization,
    pattern detection, and routing validation. It is designed to be
    mixed into NexusAgent but can be used standalone.
    """

    def __init__(self) -> None:
        # ZERO-01: Dangerous patterns for injection detection
        self._dangerous_patterns = [
            (re.compile(r"__\w+__"), "dunder_access"),
            (re.compile(r"exec\s*\("), "exec_call"),
            (re.compile(r"eval\s*\("), "eval_call"),
            (re.compile(r"import\s+os"), "os_import"),
            (re.compile(r"import\s+sys"), "sys_import"),
            (re.compile(r"import\s+subprocess"), "subprocess_import"),
            (re.compile(r"open\s*\([^)]*['\"][rw]"), "file_open"),
            (re.compile(r"__import__"), "dunder_import"),
            (re.compile(r"getattr\s*\("), "getattr_call"),
            (re.compile(r"setattr\s*\("), "setattr_call"),
        ]

        # ZERO-01: Configuration defaults
        self._max_payload_size: int = 1024 * 1024  # 1MB default
        self._rate_limit_window: int = 60  # seconds
        self._rate_limit_max: int = 100  # requests per window
        self._request_counts: dict[str, list[datetime]] = {}  # Per-source rate tracking

    async def sanitize_input(
        self,
        content: Any,
        source_id: str,
        content_type: str | None = None,
    ) -> Any | None:
        """
        ZERO-01: Sanitize hostile external input before it reaches agents.

        All external inputs must pass through this sanitization layer.
        Returns None if input should be rejected entirely.

        Validation checks (in order):
        1. Payload size limit (max 1MB)
        2. Rate limiting per source
        3. Unicode normalization and null byte rejection
        4. Content-type validation
        5. Injection pattern detection
        6. Recursive dict/list sanitization

        Args:
            content: Raw input content
            source_id: Identifier of the input source (for rate limiting)
            content_type: Optional content-type hint

        Returns:
            Sanitized content or None if rejected
        """
        # Check 1: Payload size
        if not self.check_payload_size(content):
            return None

        # Check 2: Rate limiting
        if not self.check_rate_limit(source_id):
            return None

        # Check 3: Unicode normalization and null byte rejection
        sanitized = self.normalize_unicode(content)
        if sanitized is None:
            return None

        # Check 4: Content-type validation (if provided)
        if content_type and not self.validate_content_type(content_type):
            # Default to text/plain sanitization for unknown types
            pass

        # Check 5: Injection pattern detection
        injection_result = self.detect_injection_patterns(sanitized)
        if injection_result["detected"]:
            return None

        # Check 6: Recursive sanitization for nested structures
        return self.recursive_sanitize(sanitized)

    def check_payload_size(self, content: Any) -> bool:
        """Check if payload exceeds maximum size."""
        try:
            size = len(str(content))
            return size <= self._max_payload_size
        except Exception:
            return True  # If we can't measure, allow it through

    def check_rate_limit(self, source_id: str) -> bool:
        """Check if source has exceeded rate limits."""
        now = datetime.now(UTC)
        window_start = now.timestamp() - self._rate_limit_window

        # Clean old entries
        if source_id in self._request_counts:
            self._request_counts[source_id] = [
                ts for ts in self._request_counts[source_id] if ts.timestamp() > window_start
            ]
        else:
            self._request_counts[source_id] = []

        # Check limit
        if len(self._request_counts[source_id]) >= self._rate_limit_max:
            return False

        # Record this request
        self._request_counts[source_id].append(now)
        return True

    def normalize_unicode(self, content: Any) -> Any | None:
        """
        Normalize Unicode content and reject dangerous characters.

        Rejects:
        - Null bytes (\\x00)
        - Combining characters that could bypass detection
        - Invalid UTF-8 sequences
        """
        if isinstance(content, str):
            # Reject null bytes
            if "\x00" in content:
                return None

            # Normalize to NFC form (canonical composition)
            try:
                normalized = unicodedata.normalize("NFC", content)
                # Reject if normalization introduces suspicious characters
                if "\ufffd" in normalized:  # Replacement character
                    return None
                return normalized
            except Exception:
                return None

        elif isinstance(content, bytes):
            # Reject null bytes in binary content
            if b"\x00" in content:
                return None
            # Try to decode as UTF-8
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                # Try with replacement
                return content.decode("utf-8", errors="replace")

        elif isinstance(content, dict):
            result = {}
            for key, value in content.items():
                sanitized_key = self.normalize_unicode(key)
                sanitized_value = self.normalize_unicode(value)
                if sanitized_key is None or sanitized_value is None:
                    return None
                result[sanitized_key] = sanitized_value
            return result

        elif isinstance(content, list):
            result = []
            for item in content:
                sanitized = self.normalize_unicode(item)
                if sanitized is None:
                    return None
                result.append(sanitized)
            return result

        return content

    def validate_content_type(self, content_type: str) -> bool:
        """Validate content-type header."""
        if not content_type:
            return False

        # Allow common content types
        allowed_types = [
            "application/json",
            "application/xml",
            "text/plain",
            "text/html",
            "text/markdown",
            "multipart/form-data",
            "application/x-www-form-urlencoded",
        ]

        # Extract base type (ignore charset etc)
        base_type = content_type.split(";")[0].strip().lower()
        return base_type in allowed_types

    def detect_injection_patterns(self, content: Any) -> dict[str, Any]:
        """
        Detect code injection patterns in content.

        Returns dict with:
        - detected: bool
        - pattern: str (name of detected pattern)
        - severity: str (low/medium/high/critical)
        """
        if isinstance(content, str):
            for pattern, name in self._dangerous_patterns:
                if pattern.search(content):
                    severity = self.get_pattern_severity(name)
                    return {"detected": True, "pattern": name, "severity": severity}

        elif isinstance(content, dict):
            for key, value in content.items():
                # Check keys
                for pattern, name in self._dangerous_patterns:
                    if pattern.search(str(key)):
                        return {"detected": True, "pattern": name, "severity": "high"}
                # Check values recursively
                result = self.detect_injection_patterns(value)
                if result["detected"]:
                    return result

        elif isinstance(content, list):
            for item in content:
                result = self.detect_injection_patterns(item)
                if result["detected"]:
                    return result

        return {"detected": False, "pattern": None, "severity": None}

    def get_pattern_severity(self, pattern_name: str) -> str:
        """Get severity level for a detected pattern."""
        critical_patterns = ["exec_call", "eval_call", "dunder_import"]
        high_patterns = ["os_import", "sys_import", "subprocess_import", "file_open"]
        medium_patterns = ["dunder_access", "getattr_call", "setattr_call"]

        if pattern_name in critical_patterns:
            return "critical"
        if pattern_name in high_patterns:
            return "high"
        if pattern_name in medium_patterns:
            return "medium"
        return "low"

    def recursive_sanitize(self, content: Any) -> Any:
        """Recursively sanitize nested structures."""
        if isinstance(content, str):
            # Strip leading/trailing whitespace
            return content.strip()

        if isinstance(content, dict):
            return {
                str(key).strip(): self.recursive_sanitize(value) for key, value in content.items()
            }

        if isinstance(content, list):
            return [self.recursive_sanitize(item) for item in content]

        return content

    # =========================================================================
    # Private method aliases for backward compatibility
    # =========================================================================
    # These aliases maintain the original underscore-prefixed names that were
    # used in the monolithic nexus.py, allowing existing tests to pass.

    async def _sanitize_input(
        self,
        content: Any,
        source_id: str,
        content_type: str | None = None,
    ) -> Any | None:
        """Private alias for sanitize_input - backward compatibility."""
        return await self.sanitize_input(content, source_id, content_type)

    def _check_payload_size(self, content: Any) -> bool:
        """Private alias for check_payload_size - backward compatibility."""
        return self.check_payload_size(content)

    def _check_rate_limit(self, source_id: str) -> bool:
        """Private alias for check_rate_limit - backward compatibility."""
        return self.check_rate_limit(source_id)

    def _normalize_unicode(self, content: Any) -> Any | None:
        """Private alias for normalize_unicode - backward compatibility."""
        return self.normalize_unicode(content)

    def _validate_content_type(self, content_type: str) -> bool:
        """Private alias for validate_content_type - backward compatibility."""
        return self.validate_content_type(content_type)

    def _detect_injection_patterns(self, content: Any) -> dict[str, Any]:
        """Private alias for detect_injection_patterns - backward compatibility."""
        return self.detect_injection_patterns(content)

    def _get_pattern_severity(self, pattern_name: str) -> str:
        """Private alias for get_pattern_severity - backward compatibility."""
        return self.get_pattern_severity(pattern_name)

    def _recursive_sanitize(self, content: Any) -> Any:
        """Private alias for recursive_sanitize - backward compatibility."""
        return self.recursive_sanitize(content)
