"""
OpenTelemetry Logging for Heretek Swarm.

Provides structured logging with OpenTelemetry context propagation.
Integrates structlog with trace context for unified observability.

Note: structlog configuration is delegated to
``heretek_swarm.swarm_logging.config.setup_logging()`` (the canonical config path).
This module's ``init_logging()`` maps its ``LoggingConfig`` fields to
``setup_logging()`` parameters and calls it, ensuring only one code path ever
calls ``structlog.configure()``.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

from heretek_swarm.swarm_logging.config import setup_logging as _setup_logging

logger = structlog.get_logger(__name__)


class LogLevel(Enum):
    """Log levels."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LoggingConfig:
    """Configuration for structured logging."""

    service_name: str = "heretek-swarm"
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format: str = "json"  # json, console
    include_trace_context: bool = True
    include_thread_info: bool = True
    timestamp_format: str = "iso"  # iso, epoch
    enrich_fields: dict[str, Any] | None = None


_log_config: LoggingConfig | None = None


def init_logging(config: LoggingConfig | None = None) -> LoggingConfig:
    """
    Initialize structured logging with OpenTelemetry context.

    Delegates structlog configuration to
    ``heretek_swarm.swarm_logging.config.setup_logging()``, the canonical single
    source of truth for log configuration.  The ``LoggingConfig`` dataclass
    fields are mapped to ``setup_logging()`` parameters.

    Args:
        config: Logging configuration

    Returns:
        The logging configuration
    """
    global _log_config
    _log_config = config or LoggingConfig()

    # Map LoggingConfig → setup_logging() parameters
    json_output = _log_config.format == "json"
    include_caller_info = _log_config.include_trace_context

    _setup_logging(
        log_level=_log_config.log_level,
        json_output=json_output,
        include_caller_info=include_caller_info,
    )

    logger.info(
        "logging_initialized",
        service_name=_log_config.service_name,
        log_level=_log_config.log_level,
        format=_log_config.format,
    )

    return _log_config


def get_log_config() -> LoggingConfig | None:
    """Get the current logging configuration."""
    return _log_config


def _add_trace_context(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add trace context to log entries."""
    # Try to get active span context
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            event_dict["trace_id"] = ctx.trace_id
            event_dict["span_id"] = ctx.span_id
    except ImportError:
        logger.debug("OpenTelemetry import unavailable, using standard logging fallback")

    # Add service name
    if _log_config:
        event_dict["service"] = _log_config.service_name

    # Add custom enrich fields
    if _log_config and _log_config.enrich_fields:
        event_dict.update(_log_config.enrich_fields)

    return event_dict


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name (e.g., "heretek-swarm.agent")

    Returns:
        Configured structlog logger
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


class StructuredLogger:
    """
    Structured logger wrapper for consistent logging patterns.

    Provides helper methods for common logging patterns:
    - Agent lifecycle events
    - Task lifecycle events
    - Consensus events
    - Consciousness metric events
    """

    def __init__(self, name: str):
        self._logger = structlog.get_logger(name)

    def agent_started(self, agent_id: str, agent_type: str, **kwargs: Any) -> None:
        """Log agent startup."""
        self._logger.info(
            "agent_started",
            agent_id=agent_id,
            agent_type=agent_type,
            **kwargs,
        )

    def agent_stopped(
        self,
        agent_id: str,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log agent shutdown."""
        self._logger.info(
            "agent_stopped",
            agent_id=agent_id,
            reason=reason,
            **kwargs,
        )

    def task_submitted(
        self,
        task_id: str,
        agent_id: str,
        task_type: str,
        **kwargs: Any,
    ) -> None:
        """Log task submission."""
        self._logger.info(
            "task_submitted",
            task_id=task_id,
            agent_id=agent_id,
            task_type=task_type,
            **kwargs,
        )

    def task_completed(
        self,
        task_id: str,
        agent_id: str,
        duration_ms: float,
        **kwargs: Any,
    ) -> None:
        """Log task completion."""
        self._logger.info(
            "task_completed",
            task_id=task_id,
            agent_id=agent_id,
            duration_ms=duration_ms,
            **kwargs,
        )

    def task_failed(
        self,
        task_id: str,
        agent_id: str,
        error: str,
        **kwargs: Any,
    ) -> None:
        """Log task failure."""
        self._logger.error(
            "task_failed",
            task_id=task_id,
            agent_id=agent_id,
            error=error,
            **kwargs,
        )

    def consensus_started(
        self,
        topic: str,
        proposer: str,
        **kwargs: Any,
    ) -> None:
        """Log consensus initiation."""
        self._logger.info(
            "consensus_started",
            topic=topic,
            proposer=proposer,
            **kwargs,
        )

    def consensus_decided(
        self,
        topic: str,
        outcome: str,
        participants: int,
        **kwargs: Any,
    ) -> None:
        """Log consensus decision."""
        self._logger.info(
            "consensus_decided",
            topic=topic,
            outcome=outcome,
            participants=participants,
            **kwargs,
        )

    def consciousness_measured(
        self,
        agent_id: str,
        metric_type: str,
        score: float,
        **kwargs: Any,
    ) -> None:
        """Log consciousness measurement."""
        self._logger.info(
            "consciousness_measured",
            agent_id=agent_id,
            metric_type=metric_type,
            score=score,
            **kwargs,
        )


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger for a specific component."""
    return StructuredLogger(name)


__all__ = [
    "LoggingConfig",
    "StructuredLogger",
    "get_log_config",
    "get_logger",
    "get_structured_logger",
    "init_logging",
]
