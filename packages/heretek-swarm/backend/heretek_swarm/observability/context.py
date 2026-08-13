"""
Unified OTel trace context propagation contract — FROZEN for Phase 2.

This module is the canonical, framework-agnostic API for distributed-trace
context propagation in Heretek Swarm. All Phase 2 telemetry work —
opik cutover, Prometheus bridge, NeMo Guardrails telemetry, AgentScope
observability, partysocket WS traces, Temporal workflow spans, and the
official ``mcp`` SDK integration — MUST use this contract to inject and
extract trace context across process, NATS, and HTTP boundaries.

Why a dedicated module
----------------------
The current OTel context propagation lives in
:mod:`heretek_swarm.infrastructure.otel.tracing` (1,091 LOC, mixed
concerns: httpx client, encryption, SQL timing, etc.). That module's
``get_trace_context()`` returns a ``dict[str, str]`` carrier that callers
must hand-roll, with no type safety, no dataclass, and no clean extract
path. The 4 framework picks (AgentScope, Temporal, Cerbos, official
``mcp`` SDK) all need the same propagator; freezing it once stops a
re-implementation cycle.

Stability policy
----------------
- ``TRACE_CONTEXT_INTERFACE_VERSION`` is bumped on any breaking change.
- Adding a new optional field on :class:`TraceContext` is NOT a breaking change.
- Removing or renaming a function, attribute, or class IS a breaking change
  and requires a major-version bump.
- Behavior changes to W3C TraceContext propagation (trace_id/span_id shape,
  flag layout) follow the W3C spec; non-W3C behavior is internal.

W3C TraceContext compliance
---------------------------
- ``trace_id`` is a 32-character lowercase hex string (128 bits).
- ``span_id`` is a 16-character lowercase hex string (64 bits).
- ``parent_span_id`` (when set) follows the same 16-hex-char format.
- ``trace_flags`` is a 1-byte value where bit 0 is the "sampled" flag.
  We expose it as a 2-character lowercase hex string in carriers.
- The propagator used is OpenTelemetry's ``TraceContextTextMapPropagator``
  (W3C TraceContext, RFC editor copy at https://www.w3.org/TR/trace-context/).
- B3 propagation is layered separately in
  :mod:`heretek_swarm.infrastructure.otel.tracing` (Phase 1.5 work) and
  does NOT replace this W3C contract.

Migration
---------
- Old code: ``from heretek_swarm.infrastructure.otel.tracing import
  get_trace_context`` and pass the resulting dict to NATS/HTTP headers.
- New code: ``from heretek_swarm.observability.context import
  get_current_trace_context`` and pass the dataclass to
  :func:`inject_trace_context` (or use the dataclass directly as a
  structured header). The :class:`TraceContext` dataclass is JSON-
  serializable for cross-language compatibility (e.g. external
  microservices that need to forward the context).

See also
--------
- :mod:`heretek_swarm.infrastructure.otel.tracing` — the underlying
  OpenTelemetry SDK setup. This module wraps it; it does not replace it.
- PLAN.md §1.6 "Two tracing systems" — the audit finding that
  motivated the consolidation.
- PLAN.md Phase 0 — the freeze that established this contract.
"""

from __future__ import annotations

import contextlib
import re
import uuid
from collections.abc import Iterator, Mapping, MutableMapping
from dataclasses import asdict, dataclass
from typing import Any, Final

# The single propagator we standardize on. W3C TraceContext is the
# default in OpenTelemetry; the project's PRIME_DIRECTIVE mandates
# zero-trust inter-service comms and W3C is the only IETF-track
# standard. B3 remains an opt-in via the lower-level tracing module.
_PROPAGATOR_HEADERS: Final[tuple[str, ...]] = ("traceparent", "tracestate")
_TRACEPARENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)
_TRACE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")
_FLAGS_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{2}$")

# Bumped on breaking changes. See module docstring.
TRACE_CONTEXT_INTERFACE_VERSION: Final[str] = "1.0.0"


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TraceContext:
    """A self-contained, framework-agnostic distributed-trace context.

    Attributes:
        trace_id: 32-character lowercase hex string (W3C trace-id).
        span_id: 16-character lowercase hex string for the current span.
        parent_span_id: Optional 16-character lowercase hex string for
            the parent span. ``None`` means this is a root context.
        trace_flags: 2-character lowercase hex string. The W3C spec
            defines only bit 0 (``01`` = sampled). We accept any 2-hex
            value but treat the low bit as the "is this span sampled?"
            flag for downstream exporters.
        tracestate: Optional W3C ``tracestate`` vendor entry. Stored
            verbatim; not interpreted.

    The dataclass is frozen so it can be hashed, used as a dict key,
    and shared across coroutines without locking. New optional fields
    require a minor-version bump; see module docstring.
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    trace_flags: str = "01"
    tracestate: str | None = None

    def __post_init__(self) -> None:
        # Validate once at construction so downstream code can trust
        # the shape. Failures here are programming errors, not
        # runtime conditions; raise ``ValueError`` rather than silently
        # corrupt trace data.
        if not _TRACE_ID_RE.match(self.trace_id):
            raise ValueError(
                f"trace_id must be 32 lowercase hex chars, got {self.trace_id!r}"
            )
        if not _SPAN_ID_RE.match(self.span_id):
            raise ValueError(
                f"span_id must be 16 lowercase hex chars, got {self.span_id!r}"
            )
        if self.parent_span_id is not None and not _SPAN_ID_RE.match(self.parent_span_id):
            raise ValueError(
                f"parent_span_id must be 16 lowercase hex chars or None, "
                f"got {self.parent_span_id!r}"
            )
        if not _FLAGS_RE.match(self.trace_flags):
            raise ValueError(
                f"trace_flags must be 2 lowercase hex chars, got {self.trace_flags!r}"
            )

    @property
    def is_sampled(self) -> bool:
        """Return True if the W3C sampled flag is set."""
        return bool(int(self.trace_flags, 16) & 0x01)

    def to_traceparent(self) -> str:
        """Serialize to a W3C ``traceparent`` header value.

        Format: ``<version>-<trace-id>-<parent-id>-<flags>``
        Per W3C, the parent-id field is the parent of the *current*
        span. We emit our ``parent_span_id`` if set, else our own
        ``span_id`` (which marks a root span when extracted).
        """
        parent = self.parent_span_id or "0000000000000000"
        return f"00-{self.trace_id}-{parent}-{self.trace_flags}"

    def to_headers(self) -> dict[str, str]:
        """Serialize to the standard ``traceparent`` / ``tracestate`` dict.

        Empty ``tracestate`` is omitted. This is the canonical format
        for placing the context into NATS message headers, HTTP
        request headers, and the structured-log ``extra`` dict.
        """
        out: dict[str, str] = {"traceparent": self.to_traceparent()}
        if self.tracestate:
            out["tracestate"] = self.tracestate
        return out

    def child(self, span_id: str | None = None, *, sampled: bool | None = None) -> TraceContext:
        """Return a new :class:`TraceContext` for a child span.

        The new context's ``parent_span_id`` is set to this context's
        ``span_id``, preserving the trace lineage. ``trace_id`` is
        preserved. ``trace_flags`` is preserved unless ``sampled`` is
        explicitly provided.
        """
        if span_id is None:
            span_id = _new_span_id()
        elif not _SPAN_ID_RE.match(span_id):
            raise ValueError(
                f"child span_id must be 16 lowercase hex chars, got {span_id!r}"
            )
        flags = self.trace_flags if sampled is None else ("01" if sampled else "00")
        return TraceContext(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=self.span_id,
            trace_flags=flags,
            tracestate=self.tracestate,
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dict (None fields dropped)."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: MutableMapping[str, Any]) -> TraceContext:
        """Inverse of :meth:`to_dict`; tolerates extra keys."""
        return cls(
            trace_id=str(data["trace_id"]),
            span_id=str(data["span_id"]),
            parent_span_id=data.get("parent_span_id"),
            trace_flags=str(data.get("trace_flags", "01")),
            tracestate=data.get("tracestate"),
        )


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def _new_trace_id() -> str:
    """Return a fresh W3C-compliant 32-hex-char trace id."""
    return uuid.uuid4().hex


def _new_span_id() -> str:
    """Return a fresh W3C-compliant 16-hex-char span id."""
    # uuid4 gives 32 hex; truncate to 16 (W3C: "the right-most 8 bytes").
    return uuid.uuid4().hex[:16]


def new_trace_context(*, sampled: bool = True) -> TraceContext:
    """Build a brand-new root :class:`TraceContext`.

    Use this when starting a brand-new operation with no parent. For
    a child span of an existing context, prefer
    :meth:`TraceContext.child`.
    """
    return TraceContext(
        trace_id=_new_trace_id(),
        span_id=_new_span_id(),
        parent_span_id=None,
        trace_flags="01" if sampled else "00",
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def is_valid_trace_id(value: object) -> bool:
    """Return True if ``value`` is a W3C-compliant 32-hex trace id."""
    return isinstance(value, str) and bool(_TRACE_ID_RE.match(value))


def is_valid_span_id(value: object) -> bool:
    """Return True if ``value`` is a W3C-compliant 16-hex span id."""
    return isinstance(value, str) and bool(_SPAN_ID_RE.match(value))


# ---------------------------------------------------------------------------
# Inject / extract
# ---------------------------------------------------------------------------


def inject_trace_context(
    context: TraceContext,
    carrier: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Inject a :class:`TraceContext` into a header carrier.

    Args:
        context: The trace context to inject.
        carrier: Optional mutable mapping to receive the headers. If
            ``None`` a fresh ``dict`` is created. NATS message
            headers, ``httpx.Headers``, and FastAPI ``Request.headers``
            all satisfy the mutable-mapping protocol.

    Returns:
        The carrier (same instance if provided, else a new dict).
    """
    target: MutableMapping[str, str] = carrier if carrier is not None else {}
    for k, v in context.to_headers().items():
        target[k] = v
    return target


def extract_trace_context(
    carrier: Mapping[str, str] | None,
) -> TraceContext | None:
    """Extract a :class:`TraceContext` from a header carrier.

    Supports W3C ``traceparent`` (mandatory) and ``tracestate``
    (optional). Headers are matched case-insensitively. Returns
    ``None`` if the carrier is missing, empty, or contains a malformed
    ``traceparent``.

    Per W3C TraceContext, the ``parent-id`` field in ``traceparent`` is
    the id of the *caller's* span, i.e. the parent of the operation
    about to start. We surface that as ``parent_span_id`` and generate
    a fresh ``span_id`` for the local root span. If the caller wants
    to keep the upstream span_id (e.g. for an outbound-only call),
    use :func:`extract_trace_context_remote` instead.

    Per W3C: a parent-id of all zeros means the upstream was a root
    span; we surface that as ``parent_span_id=None`` (i.e. a root
    context from the receiver's perspective).
    """
    if not carrier:
        return None
    normalized = {_normalize_header_key(k): v for k, v in carrier.items() if isinstance(v, str)}
    traceparent = normalized.get("traceparent")
    if not traceparent:
        return None
    match = _TRACEPARENT_RE.match(traceparent.strip())
    if not match:
        # Malformed carrier; do not raise (the upstream service is
        # outside our trust boundary) — just return None and let the
        # caller decide whether to start a fresh root context.
        return None
    _version, trace_id, parent_id, flags = match.groups()
    parent = None if parent_id == "0" * 16 else parent_id
    return TraceContext(
        trace_id=trace_id,
        span_id=_new_span_id(),
        parent_span_id=parent,
        trace_flags=flags,
        tracestate=normalized.get("tracestate"),
    )


def extract_trace_context_remote(
    carrier: Mapping[str, str] | None,
) -> TraceContext | None:
    """Like :func:`extract_trace_context` but preserves the upstream span_id.

    Use this when forwarding a context to a downstream service
    unchanged (e.g. an outbound HTTP call from an event-mesh consumer
    that should not introduce a new local span). The returned
    :class:`TraceContext` has ``span_id`` set to the upstream
    parent_id and ``parent_span_id`` set to ``None`` — i.e. it
    represents the same span the caller was operating under.
    """
    if not carrier:
        return None
    normalized = {_normalize_header_key(k): v for k, v in carrier.items() if isinstance(v, str)}
    traceparent = normalized.get("traceparent")
    if not traceparent:
        return None
    match = _TRACEPARENT_RE.match(traceparent.strip())
    if not match:
        return None
    _version, trace_id, parent_id, flags = match.groups()
    return TraceContext(
        trace_id=trace_id,
        span_id=parent_id,
        parent_span_id=None,
        trace_flags=flags,
        tracestate=normalized.get("tracestate"),
    )


# ---------------------------------------------------------------------------
# Live OTel context integration
# ---------------------------------------------------------------------------


def get_current_trace_context() -> TraceContext | None:
    """Return a :class:`TraceContext` reflecting the active OTel context.

    If no OTel tracer is configured, returns ``None``. The
    returned context is a *snapshot*; starting child spans after
    this call does not mutate it. Use :func:`use_trace_context` to
    bind a context for the duration of a code block.
    """
    try:
        from opentelemetry import trace as _otel_trace
        from opentelemetry.trace import SpanContext as _OtelSpanContext
    except ImportError:
        return None
    span = _otel_trace.get_current_span()
    if span is None:
        return None
    sc = span.get_span_context()
    if not sc or not isinstance(sc, _OtelSpanContext) or not sc.is_valid:
        return None
    flags = f"{sc.trace_flags:02x}"
    return TraceContext(
        trace_id=_format_otel_id(sc.trace_id, 32),
        span_id=_format_otel_id(sc.span_id, 16),
        parent_span_id=None,  # OTel Span does not expose parent_id; use child() to derive.
        trace_flags=flags,
    )


@contextlib.contextmanager
def use_trace_context(context: TraceContext) -> Iterator[TraceContext]:
    """Bind a :class:`TraceContext` as the active OTel context for the block.

    Yields the bound context. On exit, restores the previous OTel
    context. If OTel is not installed, this is a no-op (the yielded
    context is still usable for header inject/extract).
    """
    try:
        from opentelemetry import context as _otel_context
        from opentelemetry.trace import (
            NonRecordingSpan,
            set_span_in_context,
        )
        from opentelemetry.trace import (
            SpanContext as _OtelSpanContext,
        )
    except ImportError:
        # No OTel available — yield a passthrough so callers can
        # use the context for header propagation regardless.
        yield context
        return

    try:
        trace_id_int = int(context.trace_id, 16)
        span_id_int = int(context.span_id, 16)
        flags_int = int(context.trace_flags, 16)
    except ValueError:
        # Malformed context — refuse to bind a garbage span. Yield
        # the original context so callers can still serialize it.
        yield context
        return

    span_context = _OtelSpanContext(
        trace_id=trace_id_int,
        span_id=span_id_int,
        is_remote=False,
        trace_flags=flags_int,
    )
    span = NonRecordingSpan(span_context)
    otel_ctx = set_span_in_context(span)
    token = _otel_context.attach(otel_ctx)
    try:
        yield context
    finally:
        _otel_context.detach(token)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_header_key(key: str) -> str:
    """Lower-case a header key. RFC 7230 says header names are
    case-insensitive; the W3C spec mandates lowercase."""
    return key.strip().lower()


def _format_otel_id(value: int, width: int) -> str:
    """Format an OTel integer id (trace_id or span_id) as lowercase hex.

    OTel exposes trace_id / span_id as Python ints; the W3C wire
    format is fixed-width lowercase hex. Invalid (zero) ids are
    returned as zero-strings so callers can detect "no real span"
    by checking :func:`is_valid_trace_id`.
    """
    if value == 0:
        return "0" * width
    return format(value, f"0{width}x")


__all__ = [
    "TRACE_CONTEXT_INTERFACE_VERSION",
    "TraceContext",
    "extract_trace_context",
    "extract_trace_context_remote",
    "get_current_trace_context",
    "inject_trace_context",
    "is_valid_span_id",
    "is_valid_trace_id",
    "new_trace_context",
    "use_trace_context",
]
