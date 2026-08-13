"""Layer 1: Input Validation — Pydantic v2, UUID v4, size limits, injection patterns."""

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, field_validator

from .result_types import LayerResult, Severity

logger = structlog.get_logger(__name__)


class ValidatedInput(BaseModel):
    """Base model for validated input with strict Pydantic v2 settings."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    request_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request_id is a valid UUID v4 (128-bit entropy)."""
        try:
            parsed = uuid.UUID(v, version=4)
            if parsed.version != 4:
                raise ValueError(f"request_id must be UUID v4, got version {parsed.version}")
            return v
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid UUID v4 request_id: {e}") from e


@dataclass
class InputValidationConfig:
    """Configuration for Layer 1 Input Validation."""

    max_content_size: int = 10240
    min_content_size: int = 1
    require_uuid_v4: bool = True
    max_string_length: int = 50000
    max_array_length: int = 1000
    max_nesting_depth: int = 10
    allowed_content_types: set[str] = field(
        default_factory=lambda: {
            "text/plain",
            "application/json",
            "text/markdown",
            "text/html",
        }
    )


class InputValidator:
    """Layer 1: Input Validation — Pydantic v2, UUID v4, size limits, injection patterns."""

    INJECTION_PATTERNS = [
        (r"\bexec\s*\(", "exec() function call detected"),
        (r"\beval\s*\(", "eval() function call detected"),
        (r"\b__import__\s*\(", "__import__() function call detected"),
        (r"\bsubprocess\.", "subprocess module access detected"),
        (r"\bos\.system\s*\(", "os.system() call detected"),
        (r"\bos\.popen\s*\(", "os.popen() call detected"),
        (r";\s*rm\s", "rm command injection detected"),
        (r";\s*cat\s", "cat command injection detected"),
        (r"\|\s*sh\b", "shell pipe injection detected"),
        (r"\$\([^)]+\)", "command substitution detected"),
        (r"`[^`]+`", "backtick command substitution detected"),
        (r"'\s*OR\s+'?\d+'?\s*=\s*'?\d+", "SQL injection pattern detected"),
        (r"'\s*OR\s*'", "SQL OR injection detected"),
        (r"\bUNION\s+SELECT\b", "SQL UNION injection detected"),
        (r";\s*DROP\s+TABLE\b", "SQL DROP injection detected"),
        (r"\bSELECT\s+\*\s+FROM\b", "SQL SELECT injection detected"),
        (r"\.\./", "path traversal detected"),
        (r"\.\.\\", "path traversal detected"),
    ]

    def __init__(self, config: InputValidationConfig | None = None):
        self.config = config or InputValidationConfig()
        self._compiled_patterns = [
            (re.compile(p, re.IGNORECASE), desc) for p, desc in self.INJECTION_PATTERNS
        ]

    def validate(
        self,
        data: dict[str, Any],
        model_class: type[ValidatedInput] | None = None,
        agent_id: str | None = None,
    ) -> LayerResult:
        """Validate input data against Layer 1 rules."""
        start_time = time.time()
        try:
            content_size = len(str(data))
            if result := self._check_content_size(content_size):
                return result
            if result := self._check_uuid_v4(data):
                return result
            if result := self._check_injection_patterns(data):
                return result
            depth = self._calculate_depth(data)
            if result := self._check_nesting_depth(depth):
                return result
            if result := self._validate_pydantic_model(data, model_class, agent_id):
                return result
            latency_ms = (time.time() - start_time) * 1000
            return LayerResult(
                layer="input", passed=True, severity=Severity.INFO,
                details={"content_size": content_size, "depth": depth, "latency_ms": latency_ms},
            )
        except Exception as e:
            logger.error("input_validation_error", error=str(e), agent_id=agent_id)
            return LayerResult(
                layer="input", passed=False, reason=f"Validation error: {e}", severity=Severity.HIGH,
            )

    def _check_content_size(self, content_size: int) -> LayerResult | None:
        if content_size > self.config.max_content_size:
            return LayerResult(
                layer="input", passed=False,
                reason=f"Content size {content_size} exceeds maximum {self.config.max_content_size}",
                severity=Severity.WARNING,
                details={"content_size": content_size, "max_size": self.config.max_content_size},
            )
        if content_size < self.config.min_content_size:
            return LayerResult(
                layer="input", passed=False,
                reason=f"Content size {content_size} below minimum {self.config.min_content_size}",
                severity=Severity.INFO,
                details={"content_size": content_size, "min_size": self.config.min_content_size},
            )
        return None

    def _check_uuid_v4(self, data: dict[str, Any]) -> LayerResult | None:
        if "request_id" not in data or not self.config.require_uuid_v4:
            return None
        try:
            parsed = uuid.UUID(data["request_id"], version=4)
            if parsed.version != 4:
                return LayerResult(
                    layer="input", passed=False,
                    reason=f"request_id must be UUID v4, got version {parsed.version}",
                    severity=Severity.WARNING,
                )
        except (ValueError, AttributeError) as e:
            return LayerResult(
                layer="input", passed=False,
                reason=f"Invalid UUID v4 request_id: {e}", severity=Severity.WARNING,
            )
        return None

    def _check_injection_patterns(self, data: dict[str, Any]) -> LayerResult | None:
        content_str = str(data)
        for pattern, description in self._compiled_patterns:
            if pattern.search(content_str):
                return LayerResult(
                    layer="input", passed=False,
                    reason=f"Injection pattern detected: {description}",
                    severity=Severity.HIGH,
                    details={"pattern": pattern.pattern, "description": description},
                )
        return None

    def _check_nesting_depth(self, depth: int) -> LayerResult | None:
        if depth > self.config.max_nesting_depth:
            return LayerResult(
                layer="input", passed=False,
                reason=f"Nesting depth {depth} exceeds maximum {self.config.max_nesting_depth}",
                severity=Severity.WARNING,
                details={"depth": depth, "max_depth": self.config.max_nesting_depth},
            )
        return None

    def _validate_pydantic_model(
        self, data: dict[str, Any], model_class: type[ValidatedInput] | None, agent_id: str | None
    ) -> LayerResult | None:
        if model_class is None:
            return None
        try:
            model_class.model_validate(data)
            logger.debug("pydantic_validation_passed", agent_id=agent_id, model=model_class.__name__)
        except Exception as e:
            return LayerResult(
                layer="input", passed=False,
                reason=f"Pydantic validation failed: {e}", severity=Severity.WARNING,
                details={"pydantic_error": str(e)},
            )
        return None

    def _calculate_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate the maximum nesting depth of a data structure."""
        if current_depth > self.config.max_nesting_depth + 5:
            return current_depth
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_depth(v, current_depth + 1) for v in obj.values())
        if isinstance(obj, (list, tuple)):
            if not obj:
                return current_depth
            return max(self._calculate_depth(item, current_depth + 1) for item in obj)
        return current_depth
