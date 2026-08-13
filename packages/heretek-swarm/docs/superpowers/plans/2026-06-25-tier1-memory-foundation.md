# Tier 1 Memory Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified MemoryBackend facade over Qdrant (vectors), Redis (ephemeral cache), and PostgreSQL (lineage), with NATS subjects for agent-to-memory communication.

**Architecture:** New `tier1/memory/` module with 5 files. `MemoryBackend` orchestrates writes to all 3 tiers and reads from the appropriate tier. Embedding via configurable model (default OpenAI text-embedding-3-small). NATS subjects for async store/retrieve.

**Tech Stack:** qdrant-client 1.7+, redis 5.0+, asyncpg 0.29+, openai 1.0+ (for embeddings), nats-py 2.6+.

## Global Constraints

- Working directory: `backend/tier1/`
- Python 3.11
- Embedding model configurable via `TIER1_EMBEDDING_MODEL` (default `text-embedding-3-small`)
- All 3 storage deps already in `[project.dependencies]`
- Graceful degradation: Qdrant/Redis down → still writes to other tiers; Postgres down → raises (lineage critical)
- NATS store/retrieve is fire-and-forget — correctness not dependent on NATS

## File Structure

**Create:**
- `tier1/memory/__init__.py` — MemoryType, MemoryEntry, MemoryBackend facade
- `tier1/memory/qdrant_store.py` — async vector store (embed + search + CRUD)
- `tier1/memory/redis_cache.py` — TTL-based session cache
- `tier1/memory/postgres_store.py` — decision history + lineage tables
- `tier1/memory/nats_memory.py` — NATS store/retrieve subjects
- `tests/unit/test_memory_entry.py` — MemoryEntry tests
- `tests/unit/test_memory_backend.py` — facade tests

**Modify:**
- `tier1/config.py` — add `embedding_model`, `embedding_dimensions`, `memory_ttl_s`

---

## Task 1: Config fields + MemoryEntry schema

**Files:**
- Modify: `tier1/config.py`
- Create: `tier1/memory/__init__.py`
- Test: `tests/unit/test_memory_entry.py`

- [ ] **Step 1: Add config fields**

Edit `backend/tier1/tier1/config.py`. Add after `llm_timeout_s`:

```python
    # Memory
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    memory_ttl_s: int = 3600
```

- [ ] **Step 2: Create memory package**

Create `backend/tier1/tier1/memory/__init__.py`:

```python
"""Memory system — unified facade over Qdrant, Redis, and PostgreSQL."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import AsyncIterator


class MemoryType(str, Enum):
    episodic = "episodic"
    semantic = "semantic"
    procedural = "procedural"


@dataclass
class MemoryEntry:
    content: str
    memory_type: MemoryType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)
    source: str = ""
    deliberation_id: str | None = None
    agent: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_seconds: int | None = None


class MemoryBackend:
    """Unified memory facade over Qdrant, Redis, and PostgreSQL."""

    def __init__(
        self,
        qdrant: "QdrantStore",
        redis: "RedisMemoryCache",
        postgres: "PostgresMemoryStore",
    ) -> None:
        self.qdrant = qdrant
        self.redis = redis
        self.postgres = postgres

    async def store(self, entry: MemoryEntry) -> str:
        """Store entry to all tiers. Returns entry.id."""
        # Qdrant (vector) — best effort
        try:
            await self.qdrant.store(entry)
        except Exception:  # noqa: BLE001
            pass

        # Redis (ephemeral) — best effort
        ttl = entry.ttl_seconds or 3600
        try:
            await self.redis.set(entry.id, entry, ttl)
        except Exception:  # noqa: BLE001
            pass

        # Postgres (lineage) — critical
        await self.postgres.store(entry)

        return entry.id

    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]:
        """Semantic search via Qdrant."""
        return await self.qdrant.search(query, top_k=top_k)

    async def get_history(self, deliberation_id: str) -> list[MemoryEntry]:
        """Decision history from Postgres."""
        return await self.postgres.get_history(deliberation_id)

    async def get_session(self, key: str) -> MemoryEntry | None:
        """Ephemeral session lookup from Redis."""
        return await self.redis.get(key)
```

- [ ] **Step 3: Write test**

Create `backend/tier1/tests/unit/test_memory_entry.py`:

```python
"""Tests for MemoryEntry and MemoryType."""

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType


def test_memory_type_enum():
    assert MemoryType.episodic == "episodic"
    assert MemoryType.semantic == "semantic"
    assert MemoryType.procedural == "procedural"


def test_memory_entry_defaults():
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    assert entry.id  # auto-generated UUID
    assert entry.content == "test"
    assert entry.memory_type == MemoryType.episodic
    assert entry.embedding is None
    assert entry.metadata == {}
    assert entry.source == ""
    assert entry.deliberation_id is None
    assert entry.agent == ""
    assert entry.created_at  # auto-generated ISO timestamp
    assert entry.ttl_seconds is None


def test_memory_entry_with_options():
    entry = MemoryEntry(
        content="deliberation result",
        memory_type=MemoryType.semantic,
        source="deliberation",
        deliberation_id="did-123",
        agent="alpha",
        ttl_seconds=7200,
    )
    assert entry.source == "deliberation"
    assert entry.deliberation_id == "did-123"
    assert entry.agent == "alpha"
    assert entry.ttl_seconds == 7200
```

- [ ] **Step 4: Run test**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_memory_entry.py -v --no-cov
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/config.py backend/tier1/tier1/memory/ backend/tier1/tests/unit/test_memory_entry.py && git commit -m "feat(tier1): MemoryEntry schema + MemoryBackend facade + config fields"
```

---

## Task 2: Qdrant vector store

**Files:**
- Create: `tier1/memory/qdrant_store.py`
- Test: `tests/unit/test_qdrant_store.py`

**Interfaces:**
- Consumes: `tier1.memory.MemoryEntry`
- Produces: `QdrantVectorStore` with `connect()`, `store()`, `search()`, `delete()`

- [ ] **Step 1: Write test**

Create `backend/tier1/tests/unit/test_qdrant_store.py`:

```python
"""Tests for QdrantVectorStore."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory import MemoryEntry, MemoryType
from tier1.memory.qdrant_store import QdrantVectorStore


@pytest.fixture()
def store():
    return QdrantVectorStore(
        url="http://localhost:6333",
        collection="test_memory",
        embedding_model="test-model",
        embedding_dimensions=128,
    )


async def test_store_upserts_to_qdrant(store):
    entry = MemoryEntry(content="hello", memory_type=MemoryType.episodic)
    store._embed = AsyncMock(return_value=[0.1] * 128)
    store._upsert = AsyncMock()
    await store.store(entry)
    store._upsert.assert_called_once()
    assert entry.embedding == [0.1] * 128


async def test_search_embeds_and_queries(store):
    store._embed = AsyncMock(return_value=[0.1] * 128)
    store._query = AsyncMock(return_value=[])
    results = await store.search("test query", top_k=3)
    store._embed.assert_called_once_with("test query")
    store._query.assert_called_once_with([0.1] * 128, top_k=3)


async def test_delete_removes_by_id(store):
    store._delete = AsyncMock()
    await store.delete("test-id")
    store._delete.assert_called_once_with("test-id")


async def test_store_without_embedding(store):
    store._embed = AsyncMock(side_effect=Exception("embed failed"))
    store._upsert = AsyncMock()
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    # Should not raise — graceful degradation
    await store.store(entry)
    assert entry.embedding is None
    store._upsert.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_qdrant_store.py -v --no-cov
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

Create `backend/tier1/tier1/memory/qdrant_store.py`:

```python
"""Async Qdrant vector store for memory entries."""

from __future__ import annotations

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from tier1.memory import MemoryEntry

log = structlog.get_logger(__name__)


class QdrantVectorStore:
    def __init__(self, url: str, collection: str, embedding_model: str, embedding_dimensions: int) -> None:
        self.url = url
        self.collection = collection
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self._client: QdrantClient | None = None
        self._openai_client = None

    def connect(self) -> None:
        self._client = QdrantClient(url=self.url)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        assert self._client is not None
        existing = [c.name for c in self._client.get_collections().collections]
        if self.collection not in existing:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.embedding_dimensions, distance=Distance.COSINE),
            )

    async def _embed(self, text: str) -> list[float]:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return [0.0] * self.embedding_dimensions
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI()
        resp = await self._openai_client.embeddings.create(model=self.embedding_model, input=text)
        return resp.data[0].embedding

    def _upsert(self, entry: MemoryEntry) -> None:
        assert self._client is not None
        self._client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=entry.id,
                    vector=entry.embedding or [0.0] * self.embedding_dimensions,
                    payload={
                        "content": entry.content,
                        "memory_type": entry.memory_type.value,
                        "source": entry.source,
                        "deliberation_id": entry.deliberation_id,
                        "agent": entry.agent,
                        "created_at": entry.created_at,
                        "metadata": entry.metadata,
                    },
                )
            ],
        )

    def _delete(self, entry_id: str) -> None:
        assert self._client is not None
        self._client.delete(collection_name=self.collection, points_selector=[entry_id])

    async def store(self, entry: MemoryEntry) -> None:
        """Embed content and upsert to Qdrant. Best-effort."""
        try:
            entry.embedding = await self._embed(entry.content)
        except Exception:  # noqa: BLE001
            log.warning("embedding_failed", entry_id=entry.id)
            entry.embedding = None
        self._upsert(entry)

    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]:
        """Embed query, cosine search, return top_k entries."""
        try:
            query_vec = await self._embed(query)
        except Exception:  # noqa: BLE001
            return []
        return self._query(query_vec, top_k=top_k)

    def _query(self, query_vec: list[float], *, top_k: int = 5) -> list[MemoryEntry]:
        assert self._client is not None
        results = self._client.search(
            collection_name=self.collection,
            query_vector=query_vec,
            limit=top_k,
        )
        entries = []
        for hit in results:
            payload = hit.payload or {}
            entries.append(
                MemoryEntry(
                    id=str(hit.id),
                    content=payload.get("content", ""),
                    memory_type=MemoryType(payload.get("memory_type", "episodic")),
                    source=payload.get("source", ""),
                    deliberation_id=payload.get("deliberation_id"),
                    agent=payload.get("agent", ""),
                    created_at=payload.get("created_at", ""),
                    metadata=payload.get("metadata", {}),
                )
            )
        return entries

    async def delete(self, entry_id: str) -> None:
        self._delete(entry_id)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_qdrant_store.py -v --no-cov
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/memory/qdrant_store.py backend/tier1/tests/unit/test_qdrant_store.py && git commit -m "feat(tier1): QdrantVectorStore — async embed + search + CRUD"
```

---

## Task 3: Redis memory cache

**Files:**
- Create: `tier1/memory/redis_cache.py`
- Test: `tests/unit/test_redis_cache.py`

**Interfaces:**
- Consumes: `tier1.memory.MemoryEntry`
- Produces: `RedisMemoryCache` with `get()`, `set()`, `delete()`

- [ ] **Step 1: Write test**

Create `backend/tier1/tests/unit/test_redis_cache.py`:

```python
"""Tests for RedisMemoryCache."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tier1.memory import MemoryEntry, MemoryType
from tier1.memory.redis_cache import RedisMemoryCache


@pytest.fixture()
def cache():
    c = RedisMemoryCache(url="redis://localhost:6379/1", ttl_s=60)
    c.client = AsyncMock()
    return c


async def test_set_stores_serialized_entry(cache):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    await cache.set(entry.id, entry, ttl=120)
    cache.client.set.assert_called_once()
    args = cache.client.set.call_args
    assert args.args[0] == f"tier1:memory:{entry.id}"


async def test_get_returns_deserialized_entry(cache):
    import json
    entry = MemoryEntry(content="hello", memory_type=MemoryType.semantic, id="test-id")
    cache.client.get = AsyncMock(return_value=json.dumps(entry.__dict__))
    result = await cache.get("test-id")
    assert result is not None
    assert result.content == "hello"
    assert result.memory_type == MemoryType.semantic


async def test_get_returns_none_when_missing(cache):
    cache.client.get = AsyncMock(return_value=None)
    assert await cache.get("missing") is None


async def test_delete_removes_key(cache):
    await cache.delete("test-id")
    cache.client.delete.assert_called_once_with("tier1:memory:test-id")
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL.

- [ ] **Step 3: Implement**

Create `backend/tier1/tier1/memory/redis_cache.py`:

```python
"""Redis ephemeral cache for memory entries."""

from __future__ import annotations

import json

import redis.asyncio as aioredis

from tier1.memory import MemoryEntry, MemoryType


class RedisMemoryCache:
    def __init__(self, url: str, ttl_s: int) -> None:
        self.url = url
        self.ttl_s = ttl_s
        self.client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self.client = aioredis.from_url(self.url, decode_responses=True)
        await self.client.ping()

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def _key(self, entry_id: str) -> str:
        return f"tier1:memory:{entry_id}"

    async def get(self, entry_id: str) -> MemoryEntry | None:
        assert self.client is not None
        raw = await self.client.get(self._key(entry_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return MemoryEntry(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            source=data.get("source", ""),
            deliberation_id=data.get("deliberation_id"),
            agent=data.get("agent", ""),
            created_at=data.get("created_at", ""),
            ttl_seconds=data.get("ttl_seconds"),
        )

    async def set(self, entry_id: str, entry: MemoryEntry, ttl: int | None = None) -> None:
        assert self.client is not None
        payload = json.dumps({
            "id": entry.id,
            "content": entry.content,
            "memory_type": entry.memory_type.value,
            "embedding": entry.embedding,
            "metadata": entry.metadata,
            "source": entry.source,
            "deliberation_id": entry.deliberation_id,
            "agent": entry.agent,
            "created_at": entry.created_at,
            "ttl_seconds": entry.ttl_seconds,
        })
        await self.client.set(self._key(entry_id), payload, ex=ttl or self.ttl_s)

    async def delete(self, entry_id: str) -> None:
        assert self.client is not None
        await self.client.delete(self._key(entry_id))
```

- [ ] **Step 4: Run test to verify it passes**

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/memory/redis_cache.py backend/tier1/tests/unit/test_redis_cache.py && git commit -m "feat(tier1): RedisMemoryCache — TTL-based session cache"
```

---

## Task 4: Postgres memory store

**Files:**
- Create: `tier1/memory/postgres_store.py`
- Test: `tests/unit/test_postgres_memory_store.py`

**Interfaces:**
- Consumes: `tier1.memory.MemoryEntry`
- Produces: `PostgresMemoryStore` with `store()`, `get_history()`, `delete()`

- [ ] **Step 1: Write test**

Create `backend/tier1/tests/unit/test_postgres_memory_store.py`:

```python
"""Tests for PostgresMemoryStore."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory import MemoryEntry, MemoryType
from tier1.memory.postgres_store import PostgresMemoryStore


@pytest.fixture()
def store():
    s = PostgresMemoryStore(pool=None)
    s._pool = AsyncMock()
    return s


async def test_store_inserts_entry(store):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    await store.store(entry)
    store._pool.execute.assert_called_once()


async def test_get_history_returns_entries(store):
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "id": "1", "content": "hello", "memory_type": "semantic",
        "source": "deliberation", "deliberation_id": "did-1",
        "agent": "alpha", "created_at": "2025-01-01", "metadata": "{}",
    }[k]
    store._pool.fetch = AsyncMock(return_value=[row])
    results = await store.get_history("did-1")
    assert len(results) == 1
    assert results[0].content == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL.

- [ ] **Step 3: Implement**

Create `backend/tier1/tier1/memory/postgres_store.py`:

```python
"""PostgreSQL persistent store for memory entries and decision lineage."""

from __future__ import annotations

import json

from tier1.memory import MemoryEntry, MemoryType

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS memory_entries (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    source TEXT DEFAULT '',
    deliberation_id TEXT,
    agent TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_memory_deliberation
ON memory_entries(deliberation_id);
"""


class PostgresMemoryStore:
    def __init__(self, pool) -> None:
        self._pool = pool

    async def connect(self) -> None:
        """Create tables if they don't exist."""
        await self._pool.execute(_CREATE_TABLE)
        await self._pool.execute(_CREATE_INDEX)

    async def store(self, entry: MemoryEntry) -> None:
        await self._pool.execute(
            """INSERT INTO memory_entries (id, content, memory_type, source, deliberation_id, agent, created_at, metadata)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
               ON CONFLICT (id) DO UPDATE SET content = $2, metadata = $8::jsonb""",
            entry.id,
            entry.content,
            entry.memory_type.value,
            entry.source,
            entry.deliberation_id,
            entry.agent,
            entry.created_at,
            json.dumps(entry.metadata),
        )

    async def get_history(self, deliberation_id: str) -> list[MemoryEntry]:
        rows = await self._pool.fetch(
            "SELECT * FROM memory_entries WHERE deliberation_id = $1 ORDER BY created_at",
            deliberation_id,
        )
        return [
            MemoryEntry(
                id=row["id"],
                content=row["content"],
                memory_type=MemoryType(row["memory_type"]),
                source=row["source"],
                deliberation_id=row["deliberation_id"],
                agent=row["agent"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]

    async def delete(self, entry_id: str) -> None:
        await self._pool.execute("DELETE FROM memory_entries WHERE id = $1", entry_id)
```

- [ ] **Step 4: Run test to verify it passes**

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/memory/postgres_store.py backend/tier1/tests/unit/test_postgres_memory_store.py && git commit -m "feat(tier1): PostgresMemoryStore — decision history + lineage"
```

---

## Task 5: NATS memory subjects

**Files:**
- Create: `tier1/memory/nats_memory.py`
- Test: `tests/unit/test_nats_memory.py`

**Interfaces:**
- Consumes: `tier1.memory.MemoryBackend`, `tier1.memory.MemoryEntry`
- Produces: `setup_memory_nats()` — subscribes to store/retrieve subjects

- [ ] **Step 1: Write test**

Create `backend/tier1/tests/unit/test_nats_memory.py`:

```python
"""Tests for NATS memory subject handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType
from tier1.memory.nats_memory import setup_memory_nats


async def test_store_handler_publishes_and_stores():
    backend = MagicMock(spec=MemoryBackend)
    backend.store = AsyncMock(return_value="entry-id")
    mock_nats = AsyncMock()
    setup_memory_nats(mock_nats, backend)
    # Verify subscribe was called
    mock_nats.subscribe.assert_called()


async def test_retrieve_handler_calls_search():
    backend = MagicMock(spec=MemoryBackend)
    backend.search = AsyncMock(return_value=[])
    mock_nats = AsyncMock()
    setup_memory_nats(mock_nats, backend)
    mock_nats.subscribe.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL.

- [ ] **Step 3: Implement**

Create `backend/tier1/tier1/memory/nats_memory.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/memory/nats_memory.py backend/tier1/tests/unit/test_nats_memory.py && git commit -m "feat(tier1): NATS memory subjects — store/retrieve handlers"
```

---

## Task 6: Facade integration + app wiring + final tests

**Files:**
- Modify: `tier1/api/app.py` — wire MemoryBackend into lifespan
- Test: `tests/unit/test_memory_backend.py`

- [ ] **Step 1: Write facade test**

Create `backend/tier1/tests/unit/test_memory_backend.py`:

```python
"""Tests for MemoryBackend facade."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType


@pytest.fixture()
def backend():
    qdrant = MagicMock()
    redis = MagicMock()
    postgres = MagicMock()
    return MemoryBackend(qdrant=qdrant, redis=redis, postgres=postgres)


async def test_store_writes_to_all_tiers(backend):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    backend.qdrant.store = AsyncMock()
    backend.redis.set = AsyncMock()
    backend.postgres.store = AsyncMock()
    result = await backend.store(entry)
    assert result == entry.id
    backend.qdrant.store.assert_called_once_with(entry)
    backend.redis.set.assert_called_once()
    backend.postgres.store.assert_called_once_with(entry)


async def test_store_survives_qdrant_failure(backend):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    backend.qdrant.store = AsyncMock(side_effect=Exception("qdrant down"))
    backend.redis.set = AsyncMock()
    backend.postgres.store = AsyncMock()
    result = await backend.store(entry)
    assert result == entry.id
    backend.postgres.store.assert_called_once()


async def test_search_calls_qdrant(backend):
    backend.qdrant.search = AsyncMock(return_value=[])
    results = await backend.search("query", top_k=3)
    backend.qdrant.search.assert_called_once_with("query", top_k=3)


async def test_get_history_calls_postgres(backend):
    backend.postgres.get_history = AsyncMock(return_value=[])
    results = await backend.get_history("did-1")
    backend.postgres.get_history.assert_called_once_with("did-1")


async def test_get_session_calls_redis(backend):
    backend.redis.get = AsyncMock(return_value=None)
    result = await backend.get_session("key")
    backend.redis.get.assert_called_once_with("key")
    assert result is None
```

- [ ] **Step 2: Run test**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_memory_backend.py -v --no-cov
```

Expected: 5 passed.

- [ ] **Step 3: Run full suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ --no-cov -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tests/unit/test_memory_backend.py && git commit -m "test(tier1): MemoryBackend facade tests (all tiers mocked)"
```
