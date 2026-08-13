"""
Observability service stub — Phase 5.4 of PLAN.md.

In-process skeleton for the future observability sidecar.
The stub exposes the same surface the sidecar would
expose (track_metric, emit_span, fire_alert) but
delegates to the canonical observability stack
(OpenTelemetry for spans, structlog for alerts/metrics,
prometheus_native for time_block) so behavior matches
the in-process observability exactly.

The exit criterion for activating 5.4 is in
``docs/SOVEREIGN_SERVICES.md``: a load test shows the api
process's per-request latency drops by ≥10% when the
OTel exporter is moved to the sidecar.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import structlog
from opentelemetry import trace as _otel_trace
from opentelemetry.trace import Status, StatusCode

from heretek_swarm.observability.prometheus_native import record_external_call_duration

_logger = structlog.get_logger("observability_svc")


class ObservabilityServiceStub:
    """In-process skeleton for the future observability
    sidecar.
    """

    async def emit_span(
        self,
        name: str,
        *,
        tags: dict[str, str] | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> Any:
        """Emit an OTel span named ``name`` with the given attributes.

        Phase 2A.3 cutover: inlined from the deleted
        :func:`heretek_swarm.observability.opik_compat.log_span` shim.
        """
        attributes: dict[str, str] = dict(tags or {})
        if inputs:
            # Surface a small set of input keys as span attributes
            # for searchability in the OTel UI.
            for k, v in list(inputs.items())[:8]:
                attributes[f"input.{k}"] = str(v)[:200]
        tracer = _otel_trace.get_tracer(__name__)
        with tracer.start_as_current_span(name, attributes=attributes) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise

    def fire_alert(
        self,
        name: str,
        *,
        severity: str = "warning",
        message: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit a structlog ``error`` line. The existing alerting
        module picks it up.

        Phase 2A.3 cutover: inlined from the deleted
        :func:`heretek_swarm.observability.opik_compat.alert` shim.
        """
        _logger.error(
            "alert",
            alert_name=name,
            severity=severity,
            message=message,
            **(tags or {}),
        )

    def track_metric(
        self,
        name: str,
        *,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit a structlog ``info`` line for the metric. Prometheus
        ingestion happens at the call site via pre-declared
        ``prometheus_native`` metrics (the legacy shim's
        dynamic-Counter-on-the-fly was a workaround for missing
        native helpers; with Phase 2A.1 done, callers should use
        the canonical Counters directly).

        Phase 2A.3 cutover: inlined from the deleted
        :func:`heretek_swarm.observability.opik_compat.track_metric` shim.
        """
        _logger.info("metric", metric_name=name, value=value, **(tags or {}))

    def time_block(self, name: str, *, tags: dict[str, str] | None = None) -> Any:
        """Context manager that times a block and records into
        ``EXTERNAL_CALL_DURATION`` via ``record_external_call_duration``.

        Phase 2A.3 cutover: inlined from the deleted
        :func:`heretek_swarm.observability.opik_compat.timed` shim.
        The ``tags`` dict is not part of the prom-native schema and
        is dropped (callers should pass the relevant fields as
        ``call_type`` / ``method`` args instead).
        """

        @contextmanager
        def _ctx() -> Any:
            import time as _time

            start = _time.perf_counter()
            try:
                yield
            finally:
                record_external_call_duration(
                    call_type=name,
                    status=200,
                    duration_seconds=_time.perf_counter() - start,
                    method="INTERNAL",
                )

        return _ctx()


_singleton: ObservabilityServiceStub | None = None


def get_observability_svc() -> ObservabilityServiceStub:
    """Return the process-wide :class:`ObservabilityServiceStub`."""
    global _singleton
    if _singleton is None:
        _singleton = ObservabilityServiceStub()
    return _singleton


__all__ = [
    "ObservabilityServiceStub",
    "get_observability_svc",
]
