"""
Memory service stub — Phase 5.2 of PLAN.md.

In-process skeleton for the future gRPC/HTTP memory
service. The stub exposes the same shape the
``MemoryStore`` Protocol (Phase 1.1) would expose
(``add``, ``read``, ``search``, ``health``, ``close``)
but routes through a process-wide service stub so the
rest of the swarm can call ``get_memory_svc()`` and
the future gRPC client (when the actual extraction
happens) can swap in transparently.

The exit criterion for activating 5.2 is in
``docs/SOVEREIGN_SERVICES.md``: profiling the monolith
shows memory read/write is the dominant LLM-call cost,
AND a side-by-side parity test of the dual-backend shows
≥95% of the cognee extraction quality is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from heretek_swarm_core.memory import (
    MemoryEntry,
    MemoryStore,
    MemoryType,
    get_default_store,
)


@dataclass
class MemoryAddRequest:
    """Wire-format request for ``Add``."""

    content: str
    memory_type: MemoryType = MemoryType.EPISODIC
    identifier: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryServiceStub:
    """In-process skeleton for the future gRPC memory
    service. Delegates to the canonical ``MemoryStore``
    (cognee / mem0 / null) via ``get_default_store()``.
    """

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or get_default_store()

    async def add(self, request: MemoryAddRequest) -> str | None:
        return await self._store.add(
            content=request.content,
            memory_type=request.memory_type,
            identifier=request.identifier,
            metadata=request.metadata,
        )

    async def read(
        self,
        memory_id: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
    ) -> MemoryEntry | None:
        return await self._store.read(memory_id, memory_type)

    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        *,
        top_k: int = 5,
        identifier: str | None = None,
    ) -> list[MemoryEntry]:
        return await self._store.search(
            query,
            memory_type,
            top_k=top_k,
            identifier=identifier,
        )

    async def health(self) -> bool:
        return await self._store.health()

    async def close(self) -> None:
        await self._store.close()


_singleton: MemoryServiceStub | None = None


def get_memory_svc() -> MemoryServiceStub:
    """Return the process-wide :class:`MemoryServiceStub`."""
    global _singleton
    if _singleton is None:
        _singleton = MemoryServiceStub()
    return _singleton


__all__ = [
    "MemoryServiceStub",
    "MemoryAddRequest",
    "get_memory_svc",
]
