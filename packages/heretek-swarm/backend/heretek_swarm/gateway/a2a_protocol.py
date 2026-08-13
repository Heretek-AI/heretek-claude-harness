"""
A2A (Agent-to-Agent) Protocol — backwards-compat re-export.

.. deprecated::
    The canonical A2A protocol implementation now lives in
    :mod:`heretek_swarm.infrastructure.a2a.protocol` (which
    contains the JSON-RPC 2.0-based ``A2AProtocol``,
    ``A2AMessageType`` enum, ``MessagePriority``, ``AgentCapability``,
    and the ``create_task_request`` / ``create_task_response`` /
    ``create_delegation_message`` / ``create_consensus_message``
    helper factories).

    The previous ``gateway/a2a_protocol.py`` had a different
    message vocabulary (``MessageType``, WebSocket-on-port-18789)
    that no other module in the codebase imported. Per the audit
    (§1.6 "Two A2A protocols — pick one; delete the other"), this
    file is now a thin re-export shim of the canonical
    implementation.

    New code should import from
    :mod:`heretek_swarm.infrastructure.a2a.protocol` (or the
    package-level re-export at :mod:`heretek_swarm.infrastructure.a2a`)
    directly.
"""

from __future__ import annotations

from heretek_swarm.infrastructure.a2a.protocol import (  # noqa: F401
    A2AMessage,
    A2AMessageType,
    A2AProtocol,
    AgentCapability,
    MessagePriority,
    get_protocol,
)

# Backwards-compat alias: the legacy gateway module exposed
# ``MessageType`` (StrEnum) which is a different vocabulary from the
# canonical ``A2AMessageType`` (Enum). Map to the canonical name so
# code that imported ``MessageType`` does not break at runtime — it
# will, however, see different values than before. Callers should
# migrate to ``A2AMessageType``.
MessageType = A2AMessageType


__all__ = [
    "A2AMessage",
    "A2AMessageType",
    "A2AProtocol",
    "AgentCapability",
    "MessagePriority",
    "MessageType",
    "get_protocol",
]
