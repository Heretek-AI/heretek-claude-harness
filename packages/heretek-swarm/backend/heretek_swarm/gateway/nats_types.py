"""
Type definitions for the NATS event mesh.

The data classes and enums here are pure value objects used by
``NATSEventMesh``, ``NATSEventMeshWithJetStream``, and
``NATStoActorBridge`` (all in ``nats_event_mesh.py``). They were
extracted as part of Phase 2.5 of PLAN.md — the event mesh itself
remains a 1,700-LOC file but its pure value-object surface is no
longer interleaved with the connection / JetStream / pub-sub /
request-reply / mTLS / in-mem fallback / backoff code.

The types module imports nothing from the event mesh. New code
that only needs the value objects (e.g. a UI that displays a
``NATSMessage``) can import from here to avoid the heavier
transitive dependency on the event mesh and its async runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    pass  # NATSEventMesh is referenced only in Subscription.callback type


class ConnectionState(Enum):
    """NATS connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class Subscription:
    """NATS subscription wrapper."""

    subject: str
    callback: Callable[..., Any]
    sid: str
    active: bool = True


@dataclass
class NATSMessage:
    """NATS message wrapper."""

    subject: str
    data: dict[str, Any]
    reply: str | None = None
    sid: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


__all__ = ["ConnectionState", "NATSMessage", "Subscription"]
