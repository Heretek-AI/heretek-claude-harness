"""Layer 4: Audit Logging — structured logging, severity levels, event tracking."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from .result_types import LayerResult, Severity, ZeroTrustResult

logger = structlog.get_logger(__name__)


@dataclass
class AuditLogConfig:
    """Configuration for Layer 4 Audit Logging."""

    enable_logging: bool = True
    log_all_events: bool = True
    log_level: str = "INFO"
    retention_days: int = 30
    include_request_body: bool = False
    include_response_body: bool = False
    structured_format: bool = True


class AuditLogger:
    """Layer 4: Audit Logging — structured logging, severity levels, event tracking."""

    def __init__(self, config: AuditLogConfig | None = None):
        self.config = config or AuditLogConfig()
        self._event_counts: dict[str, int] = defaultdict(int)
        self._high_severity_events: list[dict[str, Any]] = []

    def log(
        self,
        event_type: str,
        result: ZeroTrustResult,
        additional_context: dict[str, Any] | None = None,
    ) -> LayerResult:
        """Log a security event."""
        try:
            context = additional_context or {}

            log_entry: dict[str, Any] = {
                "event_type": event_type,
                "request_id": result.request_id,
                "agent_id": result.agent_id,
                "passed": result.passed,
                "total_latency_ms": result.total_latency_ms,
                "timestamp": datetime.now(UTC).isoformat(),
                **context,
            }

            severity = Severity.INFO
            if not result.passed:
                if result.layer1.severity in (Severity.HIGH, Severity.CRITICAL):
                    severity = result.layer1.severity
                elif result.layer2.severity in (Severity.HIGH, Severity.CRITICAL):
                    severity = result.layer2.severity
                elif result.layer3.severity in (Severity.HIGH, Severity.CRITICAL):
                    severity = result.layer3.severity
                else:
                    severity = Severity.WARNING

            log_entry["severity"] = severity.value

            self._event_counts[event_type] += 1
            self._event_counts[f"{event_type}:{severity.value}"] += 1

            if severity in (Severity.HIGH, Severity.CRITICAL):
                self._high_severity_events.append(log_entry)
                if len(self._high_severity_events) > 1000:
                    self._high_severity_events = self._high_severity_events[-1000:]

            log_method = {
                Severity.INFO: logger.info,
                Severity.WARNING: logger.warning,
                Severity.HIGH: logger.error,
                Severity.CRITICAL: logger.critical,
            }.get(severity, logger.info)

            log_method(f"security_event_{event_type}", **log_entry)

            return LayerResult(
                layer="audit",
                passed=True,
                severity=severity,
                details={"logged": True, "event_type": event_type, "severity": severity.value},
            )

        except Exception as e:
            logger.error("audit_logging_error", error=str(e))
            return LayerResult(
                layer="audit",
                passed=False,
                reason=f"Audit logging error: {e}",
                severity=Severity.WARNING,
            )

    def get_event_counts(self) -> dict[str, int]:
        return dict(self._event_counts)

    def get_high_severity_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._high_severity_events[-limit:]
