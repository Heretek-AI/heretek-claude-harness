"""
Heretek Swarm - Observability Module

Provides comprehensive observability for the Heretek Swarm:
- Prometheus metrics
- OpenTelemetry tracing
- Loki log aggregation
- Health checks
- Alert management

This module ties together the existing Prometheus metrics, tracing, and adds
structured logging integration for ELK/Loki.

Reference: Prometheus metrics at prometheus_metrics.py
Reference: Tracing at observability/tracing.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

logger = structlog.get_logger("observability")

# Phase 0 freeze: unified trace context propagation contract.
# See heretek_swarm.observability.context for the full module docstring
# describing the W3C-compliant contract that Phase 2 telemetry work
# (opik cutover, prometheus bridge, AgentScope observability,
# partysocket WS traces, Temporal workflow spans) will all bind to.
# Explicit re-exports so ruff F401 (suppressed per-file) treats these
# as intentional public API.
from .context import TRACE_CONTEXT_INTERFACE_VERSION as TRACE_CONTEXT_INTERFACE_VERSION  # noqa: E402
from .context import TraceContext as TraceContext  # noqa: E402
from .context import extract_trace_context as extract_trace_context  # noqa: E402
from .context import inject_trace_context as inject_trace_context  # noqa: E402
from .context import new_trace_context as new_trace_context  # noqa: E402
from .prometheus_native import (  # noqa: E402
    export_prometheus,
    record_api_request,
    record_consensus_round,
    record_free_energy,
    record_message,
    record_phi_score,
    record_task_completed,
    record_task_failed,
    record_uptime,
)
from .prometheus_native import (  # noqa: E402
    record_agent_active as record_agent_active,
)
from .prometheus_native import (  # noqa: E402
    record_agent_registration as record_agent_registration,
)
from .tracing import initialize_tracing, span_context  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable

# ============================================================================
# Configuration
# ============================================================================

HERETEK_DATA_DIR = Path(os.environ.get("HERETEK_HOME", Path.home() / ".heretek-swarm"))
HERETEK_LOGS_DIR = HERETEK_DATA_DIR / "logs"

try:
    HERETEK_LOGS_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    # Container / restricted environment - use /tmp fallback
    HERETEK_DATA_DIR = Path("/tmp/.heretek-swarm")
    HERETEK_LOGS_DIR = HERETEK_DATA_DIR / "logs"
    HERETEK_LOGS_DIR.mkdir(parents=True, exist_ok=True)


class LogLevel(StrEnum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ServiceStatus(StrEnum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    STARTING = "starting"
    STOPPED = "stopped"


# ============================================================================
# Structured Log Entry
# ============================================================================


@dataclass
class LogEntry:
    """Structured log entry for Loki/ELK integration."""

    timestamp: str
    level: str
    logger: str
    message: str
    module: str | None = None
    function: str | None = None
    line: int | None = None
    trace_id: str | None = None
    span_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# ============================================================================
# Loki Log Handler
# ============================================================================


class LokiHandler(logging.Handler):
    """
    Custom logging handler that sends logs to Loki.

    Also writes to local JSON files for ELK filebeat pickup.
    """

    def __init__(
        self,
        loki_url: str = "http://localhost:3100/loki/api/v1/push",
        log_dir: Path = HERETEK_LOGS_DIR,
        service_name: str = "heretek-swarm",
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ):
        """
        Initialize Loki handler.

        Args:
            loki_url: Loki push API URL
            log_dir: Directory for local JSON log files
            service_name: Service name for log labels
            batch_size: Number of logs to batch before sending
            flush_interval: Seconds between flushes
        """
        super().__init__()
        self.loki_url = loki_url
        self.log_dir = Path(log_dir)
        self.service_name = service_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._buffer: list[dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._last_flush = time.time()
        self._flush_task: asyncio.Task | None = None
        self._http_client: Any | None = None

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create current log file
        self._current_file = (
            self.log_dir / f"{service_name}-{datetime.now().strftime('%Y%m%d')}.jsonl"
        )

    async def _get_client(self):
        """Get or create HTTP client."""
        if self._http_client is None:
            import httpx

            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _flush_buffer(self) -> None:
        """Flush buffered logs to Loki and local file."""
        async with self._buffer_lock:
            if not self._buffer:
                return

            logs_to_send = self._buffer.copy()
            self._buffer.clear()
            self._last_flush = time.time()

        # Write to local JSON file
        try:
            with open(self._current_file, "a") as f:
                for log_entry in logs_to_send:
                    f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.debug("observability_file_log_failed", error=str(e))

        # Send to Loki
        if self.loki_url:
            try:
                client = await self._get_client()

                # Format for Loki (Promtail compatible)
                streams = {}
                for log_entry in logs_to_send:
                    labels = f'{{service="{self.service_name}",level="{log_entry["level"]}"}}'
                    if labels not in streams:
                        streams[labels] = []
                    streams[labels].append(
                        {
                            "ts": log_entry["timestamp"],
                            "v": 0,
                            "msg": log_entry["message"],
                            **log_entry,
                        }
                    )

                payload = {
                    "streams": [
                        {"labels": labels, "entries": entries}
                        for labels, entries in streams.items()
                    ]
                }

                await client.post(self.loki_url, json=payload)
            except Exception as e:
                logger.debug("observability_loki_push_failed", error=str(e))

    async def _periodic_flush(self) -> None:
        """Periodically flush the buffer."""
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush_buffer()

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record."""
        try:
            # Parse log record
            log_entry = self._format_record(record)

            # Add to buffer
            asyncio.create_task(self._add_to_buffer(log_entry))

        except Exception as e:
            logger.debug("observability_emit_failed", error=str(e))
            self.handleError(record)

    async def _add_to_buffer(self, log_entry: dict[str, Any]) -> None:
        """Add log entry to buffer."""
        async with self._buffer_lock:
            self._buffer.append(log_entry)

            # Flush if batch size reached
            if len(self._buffer) >= self.batch_size:
                await self._flush_buffer()

    def _format_record(self, record: logging.LogRecord) -> dict[str, Any]:
        """Format a log record."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "service": self.service_name,
        }

        # Add extra fields
        if hasattr(record, "agent_id"):
            log_entry["agent_id"] = record.agent_id
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id
        if hasattr(record, "session_id"):
            log_entry["session_id"] = record.session_id
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id

        # Add exception info
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return log_entry

    async def start(self) -> None:
        """Start the handler."""
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self) -> None:
        """Stop the handler and flush remaining logs."""
        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        await self._flush_buffer()
        if self._http_client:
            await self._http_client.aclose()


# ============================================================================
# Observability Manager
# ============================================================================


class ObservabilityManager:
    """
    Centralized observability management for Heretek Swarm.

    Provides:
    - Unified metrics collection (Prometheus)
    - Distributed tracing (OpenTelemetry)
    - Log aggregation (Loki)
    - Health monitoring
    - Alert management

    Example:
        obs = ObservabilityManager()
        await obs.initialize()

        # Record metrics
        obs.metrics.record_task_completed("agent_1", "executor", "analysis")

        # Trace operations
        with obs.trace_span("agent.process", agent_id="agent_1"):
            await process_agent_task()

        # Check health
        health = await obs.check_health()
    """

    def __init__(
        self,
        service_name: str = "heretek-swarm",
        service_version: str = "1.0.0",
        loki_url: str | None = None,
        otlp_endpoint: str | None = None,
        prometheus_port: int = 9090,
    ):
        """
        Initialize the observability manager.

        Args:
            service_name: Name of the service
            service_version: Version of the service
            loki_url: Loki push URL (default: http://localhost:3100/loki/api/v1/push)
            otlp_endpoint: OpenTelemetry collector endpoint
            prometheus_port: Port for Prometheus metrics endpoint
        """
        self.service_name = service_name
        self.service_version = service_version
        self.loki_url = loki_url or os.getenv("LOKI_URL", "http://localhost:3100/loki/api/v1/push")
        self.otlp_endpoint = otlp_endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        self.prometheus_port = prometheus_port

        self._loki_handler: LokiHandler | None = None
        self._initialized = False
        self._start_time = time.time()

        # Health checks
        self._health_checks: dict[str, Callable[[], Any]] = {}

        # Service status
        self._status = ServiceStatus.STARTING

    async def initialize(self) -> None:
        """Initialize all observability components."""
        if self._initialized:
            return

        # Initialize tracing
        try:
            initialize_tracing(
                service_name=self.service_name,
                service_version=self.service_version,
                otlp_endpoint=self.otlp_endpoint,
            )
            self.logger.info("OpenTelemetry tracing initialized")
        except Exception:
            self.logger.warning("Failed to initialize tracing: {e}")

        # Initialize Loki handler
        try:
            self._loki_handler = LokiHandler(
                loki_url=self.loki_url,
                service_name=self.service_name,
            )
            await self._loki_handler.start()
            self.logger.info("Loki logging initialized")
        except Exception:
            self.logger.warning("Failed to initialize Loki handler: {e}")

        # Record startup
        record_uptime(time.time() - self._start_time)

        self._initialized = True
        self._status = ServiceStatus.HEALTHY
        self.logger.info(
            "Observability manager initialized",
            service=self.service_name,
            version=self.service_version,
        )

    async def shutdown(self) -> None:
        """Shutdown all observability components."""
        if self._loki_handler:
            await self._loki_handler.stop()

        self._status = ServiceStatus.STOPPED
        self._initialized = False
        self.logger.info("Observability manager shutdown complete")

    @property
    def logger(self):
        """Get structlog logger."""
        return structlog.get_logger("observability")

    # =========================================================================
    # Metrics
    # =========================================================================

    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format."""
        body, _ctype = export_prometheus()
        return body

    def get_metrics_content_type(self) -> str:
        """Get Prometheus metrics content type."""
        # Use the native export to derive the content type (single source of truth).
        _body, ctype = export_prometheus()
        return ctype

    def record_agent_registration(self, agent_id: str, agent_type: str) -> None:
        """Record agent registration."""
        record_agent_registration(agent_id, agent_type)

    def record_agent_active(self, agent_id: str, agent_type: str) -> None:
        """Record agent activity."""
        record_agent_active(agent_id, agent_type)

    def record_task_completed(self, agent_id: str, agent_type: str, task_type: str) -> None:
        """Record task completion."""
        record_task_completed(agent_id, agent_type, task_type)

    def record_task_failed(self, agent_id: str, agent_type: str, task_type: str) -> None:
        """Record task failure."""
        record_task_failed(agent_id, agent_type, task_type)

    def record_message(self, direction: str, message_type: str) -> None:
        """Record message processing."""
        record_message(direction, message_type)

    def record_consensus_round(self, consensus_type: str, outcome: str) -> None:
        """Record consensus round."""
        record_consensus_round(consensus_type, outcome)

    def record_phi_score(self, agent_id: str, phi_score: float) -> None:
        """Record consciousness phi score."""
        record_phi_score(agent_id, phi_score)

    def record_free_energy(self, agent_id: str, free_energy: float) -> None:
        """Record free energy level."""
        record_free_energy(agent_id, free_energy)

    def record_api_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
    ) -> None:
        """Record API request."""
        record_api_request(method, endpoint, status, duration)

    def record_uptime(self, uptime_seconds: float) -> None:
        """Record service uptime."""
        record_uptime(uptime_seconds)

    # =========================================================================
    # Tracing
    # =========================================================================

    def trace_span(
        self,
        name: str,
        agent_id: str | None = None,
        task_id: str | None = None,
        **attributes,
    ):
        """Create a trace span context manager."""
        span_attributes = {**attributes}
        if agent_id:
            span_attributes["agent_id"] = agent_id
        if task_id:
            span_attributes["task_id"] = task_id

        return span_context(name, attributes=span_attributes)

    async def traced(
        self,
        name: str,
        agent_id: str | None = None,
        task_id: str | None = None,
        **attributes,
    ):
        """Async context manager for tracing."""
        from .tracing import span_context

        span_attributes = {**attributes}
        if agent_id:
            span_attributes["agent_id"] = agent_id
        if task_id:
            span_attributes["task_id"] = task_id

        async with span_context(name, attributes=span_attributes):
            yield

    # =========================================================================
    # Health Checks
    # =========================================================================

    def register_health_check(self, name: str, check_fn: Callable[[], Any]) -> None:
        """
        Register a health check.

        Args:
            name: Name of the health check
            check_fn: Async function that returns health status
        """
        self._health_checks[name] = check_fn

    async def check_health(self) -> dict[str, Any]:
        """
        Check overall system health.

        Returns:
            Dictionary with health status and individual check results
        """
        check_results = {}
        overall_healthy = True
        any_degraded = False

        for name, check_fn in self._health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_fn):
                    result = await check_fn()
                else:
                    result = check_fn()

                check_results[name] = {
                    "status": ServiceStatus.HEALTHY.value
                    if result
                    else ServiceStatus.UNHEALTHY.value,
                    "healthy": result,
                }

                if not result:
                    overall_healthy = False
            except Exception as e:
                check_results[name] = {
                    "status": ServiceStatus.UNHEALTHY.value,
                    "healthy": False,
                    "error": str(e),
                }
                overall_healthy = False

        # Determine overall status
        if overall_healthy:
            status = ServiceStatus.HEALTHY
        elif any_degraded:
            status = ServiceStatus.DEGRADED
        else:
            status = ServiceStatus.UNHEALTHY

        return {
            "status": status.value,
            "healthy": overall_healthy,
            "service": self.service_name,
            "version": self.service_version,
            "uptime_seconds": time.time() - self._start_time,
            "checks": check_results,
        }

    # =========================================================================
    # Structured Logging
    # =========================================================================

    def log(
        self,
        level: LogLevel,
        message: str,
        agent_id: str | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
        **metadata,
    ) -> None:
        """
        Log with structured metadata.
        """
        log_dict = {
            "message": message,
            "agent_id": agent_id,
            "task_id": task_id,
            "session_id": session_id,
            **metadata,
        }
        log_func = getattr(structlog.get_logger(), level.value.lower())
        log_func(**log_dict)


# ============================================================================
# Global Instance
# ============================================================================

_observability: ObservabilityManager | None = None


def get_observability() -> ObservabilityManager:
    """Get the global observability manager instance."""
    global _observability
    if _observability is None:
        _observability = ObservabilityManager()
    return _observability


async def initialize_observability() -> ObservabilityManager:
    """Initialize and return the global observability manager."""
    global _observability
    _observability = ObservabilityManager()
    await _observability.initialize()
    return _observability


# ============================================================================
# Example Usage
# ============================================================================


async def main():
    """Example usage of observability."""
    # Initialize
    obs = await initialize_observability()

    # Register health check
    async def check_api():
        return True  # Replace with actual check

    obs.register_health_check("api", check_api)

    # Record metrics
    obs.record_agent_registration("agent_1", "executor")
    obs.record_task_completed("agent_1", "executor", "analysis")
    obs.record_phi_score("agent_1", 0.75)

    # Trace an operation
    async with obs.trace_span("process_task", agent_id="agent_1", task_id="task_123"):
        await asyncio.sleep(0.1)  # Simulate work

    # Check health
    await obs.check_health()

    # Get metrics
    obs.get_metrics()

    # Shutdown
    await obs.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
