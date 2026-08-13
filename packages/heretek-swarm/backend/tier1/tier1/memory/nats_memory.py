"""NATS subject handlers for memory store/retrieve."""

from __future__ import annotations

import json
import structlog

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType

log = structlog.get_logger(__name__)

SUBJECT_STORE = "swarm.internal.memory.store"
SUBJECT_RETRIEVE = "swarm.internal.memory.retrieve"


def setup_memory_nats(nats, backend: MemoryBackend) -> None:
    """Subscribe to memory store/retrieve NATS subjects."""
    import asyncio

    async def handle_store(msg):
        try:
            data = json.loads(msg.data.decode())
            entry = MemoryEntry(
                content=data["content"],
                memory_type=MemoryType(data.get("memory_type", "episodic")),
                source=data.get("source", ""),
                deliberation_id=data.get("deliberation_id"),
                agent=data.get("agent", ""),
                metadata=data.get("metadata", {}),
            )
            entry_id = await backend.store(entry)
            if msg.reply:
                await nats.publish(msg.reply, json.dumps({"id": entry_id, "ok": True}).encode())
        except Exception as exc:  # noqa: BLE001
            log.exception("memory_store_failed", error=str(exc))

    async def handle_retrieve(msg):
        try:
            data = json.loads(msg.data.decode())
            query = data.get("query", "")
            top_k = data.get("top_k", 5)
            results = await backend.search(query, top_k=top_k)
            payload = [
                {"id": e.id, "content": e.content, "memory_type": e.memory_type.value}
                for e in results
            ]
            if msg.reply:
                await nats.publish(msg.reply, json.dumps({"results": payload}).encode())
        except Exception as exc:  # noqa: BLE001
            log.exception("memory_retrieve_failed", error=str(exc))

    asyncio.ensure_future(nats.subscribe(SUBJECT_STORE, cb=handle_store))
    asyncio.ensure_future(nats.subscribe(SUBJECT_RETRIEVE, cb=handle_retrieve))
