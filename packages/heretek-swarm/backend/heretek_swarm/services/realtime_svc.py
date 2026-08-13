"""
Realtime service stub — Phase 5.3 of PLAN.md.

In-process skeleton for the future WebSocket fan-out
sidecar. The stub exposes the same shape the sidecar
would expose (broadcast_a2a, broadcast_dashboard,
broadcast_external_call) but delegates to the canonical
``ConnectionManager`` (Phase 3.4) so behavior matches
the in-process WebSocket router exactly.

The exit criterion for activating 5.3 is in
``docs/SOVEREIGN_SERVICES.md``: F-010 from
``PRIME_DIRECTIVE.md`` is fixed AND the sidecar handles
≥10k concurrent WebSocket clients without backpressure
on the api process.
"""

from __future__ import annotations

from typing import Any

from heretek_swarm_api.realtime import ConnectionManager, manager as _default_manager


class RealtimeServiceStub:
    """In-process skeleton for the future WebSocket fan-out
    sidecar.
    """

    def __init__(self, manager: ConnectionManager | None = None) -> None:
        self._manager = manager or _default_manager

    async def broadcast_dashboard(self, payload: dict[str, Any]) -> None:
        await self._manager.broadcast_dashboard(payload)

    async def broadcast_a2a(self, payload: dict[str, Any]) -> None:
        await self._manager.broadcast_a2a(payload)

    async def broadcast_external_call(self, payload: dict[str, Any]) -> None:
        await self._manager.broadcast_external_call(payload)

    async def broadcast_agent_update(self, payload: dict[str, Any]) -> None:
        await self._manager.broadcast_agent_update(payload)


_singleton: RealtimeServiceStub | None = None


def get_realtime_svc() -> RealtimeServiceStub:
    """Return the process-wide :class:`RealtimeServiceStub`."""
    global _singleton
    if _singleton is None:
        _singleton = RealtimeServiceStub()
    return _singleton


__all__ = [
    "RealtimeServiceStub",
    "get_realtime_svc",
]
