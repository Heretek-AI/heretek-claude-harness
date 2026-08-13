"""
MemoryStore Protocol — the canonical interface every memory backend
must satisfy.

This module implements Phase 1.1 of PLAN.md (Zero-Trust Architecture
Audit, §3.1 Replace / §1.11 — 5 backends, no shared interface).

Why
---
The memory subsystem currently has five independent backends
(``CogneeMemoryWriter``, ``CogneeMemoryReader``, ``Mem0Backend``,
``MemoryManager`` (eliza-style), and the in-line ``access_patterns``
``AccessPatternAnalyzer``) with different method signatures. Callers
must know which backend they are hitting, and the
:class:`MemoryType` enum (EPISODIC/SEMANTIC/PROCEDURAL/WORKING) is
not exposed uniformly. ``actors/mixins/memory.py`` hard-codes
``self.access_analyzer`` and raises ``TypeError`` if missing.

Defining a Protocol lets us:
* Decouple :mod:`actors.mixins` from specific backends
* Make the Prime Directive "Consciousness-by-Design" pillar testable
  (every memory tier maps to a backend, verifiably)
* Add new backends (mem0 algorithm, headroom-tied, future cognee
  versions) without touching call sites

Scope
-----
This module ships:
* :class:`MemoryStore` — ``typing.Protocol`` with the minimum viable
  surface (``add``, ``read``, ``search``, ``health``, ``close``)
* :class:`MemoryType` — re-exported enum (was previously implicit)
* :func:`get_default_store` — process-wide resolver that returns
  cognee when enabled, else mem0 when initialized, else an in-memory
  no-op (so the swarm stays bootable in dev)

It does NOT yet replace every ``from heretek_swarm_core.memory.cognee_writer
import CogneeMemoryWriter`` call site — that is a multi-week migration
(Phase 1.1 in the audit). New code should import from here.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class MemoryType(StrEnum):
    """Tier of memory being addressed.

    Maps to a cognee ``dataset_name`` (``episode-<id>``,
    ``semantic-<id>``, ``procedural-<id>``, ``working-<id>``) so the
    backends can route writes/reads without a separate registry.
    """

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"

    def to_dataset(self, identifier: str) -> str:
        """Return the cognee dataset name for this tier + identifier."""
        return f"{self.value}-{identifier}"


class MemoryEntry:
    """A single memory record returned from a store.

    Intentionally a thin dataclass; backends can hydrate richer
    objects internally but the Protocol only requires these fields.
    """

    __slots__ = ("id", "content", "memory_type", "metadata", "created_at")

    def __init__(
        self,
        id: str,
        content: str,
        memory_type: MemoryType,
        metadata: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> None:
        self.id = id
        self.content = content
        self.memory_type = memory_type
        self.metadata = metadata or {}
        self.created_at = created_at

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"MemoryEntry(id={self.id!r}, type={self.memory_type.value!r}, "
            f"content={self.content[:32]!r}{'…' if len(self.content) > 32 else ''})"
        )


@runtime_checkable
class MemoryStore(Protocol):
    """The minimum surface every memory backend must implement.

    Backends (Cognee, mem0, in-memory) may add methods; callers that
    accept a :class:`MemoryStore` only see this surface. Backends that
    omit any method fail ``isinstance(x, MemoryStore)`` checks.
    """

    async def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        *,
        identifier: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Persist ``content`` under a tier-scoped dataset.

        Args:
            content: The text or JSON-encoded content to store.
            memory_type: Which tier this memory belongs to.
            identifier: Optional sub-identifier within the tier
                (e.g. ``agent_id``, ``session_id``). When ``None`` the
                store derives one (timestamp-based, UUID, etc.).
            metadata: Arbitrary key/value annotations.

        Returns:
            The backend's identifier for the new record, or ``None``
            when the write was a no-op (e.g. backend disabled).
        """
        ...

    async def read(
        self,
        memory_id: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
    ) -> MemoryEntry | None:
        """Retrieve a single memory by its backend id."""
        ...

    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        *,
        top_k: int = 5,
        threshold: float | None = None,
        identifier: str | None = None,
    ) -> list[MemoryEntry]:
        """Semantic-search the store. ``memory_type`` filters by tier;
        ``identifier`` filters by sub-id (agent/session)."""
        ...

    async def health(self) -> bool:
        """Liveness check used by ``GET /api/health``."""
        ...

    async def close(self) -> None:
        """Release any resources (HTTP clients, file handles)."""
        ...


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


_default_store: MemoryStore | None = None


def get_default_store() -> MemoryStore:
    """Return the process-wide :class:`MemoryStore` to use.

    Resolution order:
    1. :class:`CogneeMemoryWriter` if ``COGNEE_ENABLED`` env var is
       truthy (the cognee path is the canonical pipeline; see
       PLAN.md §3.1 Replace).
    2. :class:`Mem0Backend` if the mem0 client is initialized and
       ``MEM0_ENABLED`` is truthy.
    3. An in-memory ``NullMemoryStore`` (always returns empty lists)
       so the swarm stays bootable in dev.

    The result is cached after the first call.
    """
    global _default_store
    if _default_store is not None:
        return _default_store

    if os.getenv("COGNEE_ENABLED", "false").lower() in ("1", "true", "yes"):
        from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

        store: MemoryStore = _CogneeAdapter(CogneeMemoryWriter())
        _default_store = store
        return store

    if os.getenv("MEM0_ENABLED", "false").lower() in ("1", "true", "yes"):
        from heretek_swarm.api.main import mem0_backend  # lazy import

        if mem0_backend is not None and mem0_backend.client is not None:
            store = _Mem0Adapter(mem0_backend)
            _default_store = store
            return store

    _default_store = _NullMemoryStore()
    return _default_store


def reset_default_store() -> None:
    """Clear the cached default store (used by tests)."""
    global _default_store
    _default_store = None


# ---------------------------------------------------------------------------
# Adapters — wrap existing backends so they conform to MemoryStore
# ---------------------------------------------------------------------------


class _CogneeAdapter:
    """Adapt :class:`CogneeMemoryWriter` to the :class:`MemoryStore`
    protocol. The writer has its own richer surface; this adapter
    surfaces only what the protocol requires."""

    def __init__(self, writer: Any) -> None:
        self._writer = writer

    async def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        *,
        identifier: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        dataset = memory_type.to_dataset(identifier or "default")
        return await self._writer.store(
            content=content, dataset=dataset, metadata=metadata
        )

    async def read(
        self,
        memory_id: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
    ) -> MemoryEntry | None:
        # CogneeMemoryWriter does not implement single-id read in the
        # current shape; the search-by-id pattern is the closest
        # equivalent. Callers needing exact-id resolution should hit
        # the underlying writer directly.
        results = await self._writer.search(query=memory_id, dataset=None)
        if not results:
            return None
        record = results[0]
        return MemoryEntry(
            id=str(record.get("id", memory_id)),
            content=str(record.get("content", record.get("text", ""))),
            memory_type=memory_type,
            metadata=record.get("metadata"),
            created_at=record.get("created_at"),
        )

    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        *,
        top_k: int = 5,
        threshold: float | None = None,
        identifier: str | None = None,
    ) -> list[MemoryEntry]:
        dataset = memory_type.to_dataset(identifier) if memory_type and identifier else None
        results = await self._writer.search(query=query, dataset=dataset, top_k=top_k)
        return [
            MemoryEntry(
                id=str(r.get("id", "")),
                content=str(r.get("content", r.get("text", ""))),
                memory_type=memory_type or MemoryType.EPISODIC,
                metadata=r.get("metadata"),
                created_at=r.get("created_at"),
            )
            for r in results[:top_k]
        ]

    async def health(self) -> bool:
        return await self._writer.health()

    async def close(self) -> None:
        await self._writer.close()


class _Mem0Adapter:
    """Adapt :class:`Mem0Backend` to the :class:`MemoryStore` protocol."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    async def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        *,
        identifier: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        # mem0's API takes a messages list; we synthesize a single
        # user message from the content.
        result = await self._backend.add(
            messages=[{"role": "user", "content": content}],
            user_id=identifier,
            metadata={"memory_type": memory_type.value, **(metadata or {})},
        )
        # mem0 returns a dict with ``results`` list; surface the first id.
        if isinstance(result, dict):
            results = result.get("results") or []
            if results and isinstance(results[0], dict):
                return str(results[0].get("id", ""))
        return None

    async def read(
        self,
        memory_id: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
    ) -> MemoryEntry | None:
        record = await self._backend.get(memory_id)
        if not record:
            return None
        if isinstance(record, dict):
            return MemoryEntry(
                id=str(record.get("id", memory_id)),
                content=str(record.get("memory", record.get("text", ""))),
                memory_type=memory_type,
                metadata=record.get("metadata"),
                created_at=record.get("created_at"),
            )
        return None

    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        *,
        top_k: int = 5,
        threshold: float | None = None,
        identifier: str | None = None,
    ) -> list[MemoryEntry]:
        results = await self._backend.search(
            query=query,
            user_id=identifier,
            top_k=top_k,
        )
        out: list[MemoryEntry] = []
        for r in results or []:
            if not isinstance(r, dict):
                continue
            out.append(
                MemoryEntry(
                    id=str(r.get("id", "")),
                    content=str(r.get("memory", r.get("text", ""))),
                    memory_type=memory_type or MemoryType.EPISODIC,
                    metadata=r.get("metadata"),
                    created_at=r.get("created_at"),
                )
            )
            if len(out) >= top_k:
                break
        return out

    async def health(self) -> bool:
        return self._backend.client is not None

    async def close(self) -> None:
        await self._backend.shutdown()


class _NullMemoryStore:
    """In-memory no-op used when neither cognee nor mem0 is enabled.

    Keeps the swarm bootable in dev/CI environments without any
    external memory service. All operations succeed and return
    empty/None results.
    """

    def __init__(self) -> None:
        self._records: dict[str, MemoryEntry] = {}

    async def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        *,
        identifier: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        import uuid

        rid = str(uuid.uuid4())
        self._records[rid] = MemoryEntry(
            id=rid,
            content=content,
            memory_type=memory_type,
            metadata={**(metadata or {}), "identifier": identifier} if identifier else metadata,
        )
        return rid

    async def read(
        self,
        memory_id: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
    ) -> MemoryEntry | None:
        return self._records.get(memory_id)

    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        *,
        top_k: int = 5,
        threshold: float | None = None,
        identifier: str | None = None,
    ) -> list[MemoryEntry]:
        # Naive substring match; good enough for dev / null backend.
        q = query.lower()
        scored: list[tuple[int, MemoryEntry]] = []
        for entry in self._records.values():
            if memory_type and entry.memory_type != memory_type:
                continue
            if identifier and entry.metadata.get("identifier") != identifier:
                continue
            score = sum(1 for tok in q.split() if tok in entry.content.lower())
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    async def health(self) -> bool:
        return True

    async def close(self) -> None:
        self._records.clear()


__all__ = [
    "MemoryType",
    "MemoryEntry",
    "MemoryStore",
    "get_default_store",
    "reset_default_store",
]
