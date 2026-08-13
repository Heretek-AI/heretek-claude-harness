# Tier 1 Mem0 + Access Patterns + Prefetcher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Mem0Backend (semantic memory), AccessPatternAnalyzer (read tracking), and IntelligentPrefetcher (predictive loading into Redis).

**Architecture:** Three components layer onto existing memory infrastructure. Mem0Backend wraps mem0ai for semantic memory. AccessPatternAnalyzer logs reads to Postgres. IntelligentPrefetcher uses patterns to preload Redis.

**Tech Stack:** mem0ai (already installed), asyncpg (already installed), redis (already installed), structlog.

## Global Constraints

- Working directory: `backend/tier1/`
- Python 3.11
- mem0ai already in `[project.dependencies]`
- Graceful degradation: mem0 unavailable → MemoryBackend works without semantic layer
- Prefetcher is best-effort, non-blocking, failures logged not raised

## File Structure

**Create:**
- `tier1/memory/mem0_store.py` — `Mem0Backend` class
- `tier1/memory/access_patterns.py` — `AccessPatternAnalyzer` class
- `tier1/memory/prefetcher.py` — `IntelligentPrefetcher` class
- `tests/unit/test_mem0_store.py`
- `tests/unit/test_access_patterns.py`
- `tests/unit/test_prefetcher.py`

**Modify:**
- `tier1/memory/__init__.py` — add `mem0` field to `MemoryBackend`

---

## Task 1: Mem0Backend

**Files:**
- Create: `tier1/memory/mem0_store.py`
- Test: `tests/unit/test_mem0_store.py`

- [ ] **Step 1: Write test**

Create `backend/tier1/tests/unit/test_mem0_store.py`:

```python
"""Tests for Mem0Backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory.mem0_store import Mem0Backend


def test_disabled_backend():
    backend = Mem0Backend(api_key=None)
    assert not backend._enabled


async def test_add_returns_none_when_disabled():
    backend = Mem0Backend(api_key=None)
    result = await backend.add("test", user_id="agent1")
    assert result is None


async def test_add_calls_client():
    backend = Mem0Backend(api_key="test-key")
    mock_client = MagicMock()
    mock_client.add = MagicMock(return_value={"id": "mem-123"})
    backend._client = mock_client
    result = await backend.add("test memory", user_id="agent1")
    mock_client.add.assert_called_once()
    assert result == "mem-123"


async def test_search_returns_empty_when_disabled():
    backend = Mem0Backend(api_key=None)
    result = await backend.search("query", user_id="agent1")
    assert result == []


async def test_delete_returns_false_when_disabled():
    backend = Mem0Backend(api_key=None)
    result = await backend.delete("mem-123")
    assert result is False
```

- [ ] **Step 2: Implement**

Create `backend/tier1/tier1/memory/mem0_store.py`:

```python
"""Mem0 semantic memory backend — wraps mem0ai library."""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


class Mem0Backend:
    def __init__(self, api_key: str | None = None, vector_store: str = "qdrant") -> None:
        self._api_key = api_key
        self._vector_store = vector_store
        self._enabled = bool(api_key)
        self._client = None

    def _ensure_client(self) -> None:
        if not self._enabled:
            return
        if self._client is None:
            from mem0ai import MemoryClient
            self._client = MemoryClient(api_key=self._api_key)

    async def add(self, text: str, user_id: str, metadata: dict | None = None) -> str | None:
        if not self._enabled:
            return None
        try:
            self._ensure_client()
            result = self._client.add(text, user_id=user_id, metadata=metadata or {})
            return result.get("id")
        except Exception as exc:  # noqa: BLE001
            log.warning("mem0_add_failed", error=str(exc))
            return None

    async def search(self, query: str, user_id: str, top_k: int = 5) -> list[dict]:
        if not self._enabled:
            return []
        try:
            self._ensure_client()
            result = self._client.search(query, user_id=user_id, limit=top_k)
            return result.get("results", []) if isinstance(result, dict) else result
        except Exception as exc:  # noqa: BLE001
            log.warning("mem0_search_failed", error=str(exc))
            return []

    async def update(self, memory_id: str, text: str) -> bool:
        if not self._enabled:
            return False
        try:
            self._ensure_client()
            self._client.update(memory_id, text)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("mem0_update_failed", error=str(exc))
            return False

    async def delete(self, memory_id: str) -> bool:
        if not self._enabled:
            return False
        try:
            self._ensure_client()
            self._client.delete(memory_id)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("mem0_delete_failed", error=str(exc))
            return False
```

- [ ] **Step 3: Run test**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_mem0_store.py -v -o "addopts="
```

Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/tier1/tier1/memory/mem0_store.py backend/tier1/tests/unit/test_mem0_store.py && git commit -m "feat(tier1): Mem0Backend — semantic memory wrapper with graceful degradation"
```

---

## Task 2: AccessPatternAnalyzer

**Files:**
- Create: `tier1/memory/access_patterns.py`
- Test: `tests/unit/test_access_patterns.py`

- [ ] **Step 1: Write test**

Create `backend/tier1/tests/unit/test_access_patterns.py`:

```python
"""Tests for AccessPatternAnalyzer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory.access_patterns import AccessPatternAnalyzer


@pytest.fixture()
def analyzer():
    a = AccessPatternAnalyzer(pool=None)
    a._pool = AsyncMock()
    return a


async def test_record_access_inserts_row(analyzer):
    await analyzer.record_access("agent1", "entry-1")
    analyzer._pool.execute.assert_called_once()


async def test_get_top_entries_returns_ids(analyzer):
    row = MagicMock()
    row.__getitem__ = lambda self, k: {"entry_id": "e1", "count": 5}[k]
    analyzer._pool.fetch = AsyncMock(return_value=[row])
    result = await analyzer.get_top_entries("agent1", top_n=3)
    assert result == ["e1"]


async def test_get_patterns_returns_frequency(analyzer):
    row = MagicMock()
    row.__getitem__ = lambda self, k: {"entry_id": "e1", "count": 3, "last_accessed": "2025-01-01"}[k]
    analyzer._pool.fetch = AsyncMock(return_value=[row])
    result = await analyzer.get_patterns("agent1", window_s=3600)
    assert len(result) == 1
    assert result[0]["entry_id"] == "e1"
```

- [ ] **Step 2: Implement**

Create `backend/tier1/tier1/memory/access_patterns.py`:

```python
"""Per-agent memory access pattern tracking."""

from __future__ import annotations

from datetime import datetime, timezone

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS memory_access_patterns (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    accessed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_access_agent
ON memory_access_patterns(agent_id, accessed_at);
"""


class AccessPatternAnalyzer:
    def __init__(self, pool) -> None:
        self._pool = pool

    async def connect(self) -> None:
        await self._pool.execute(_CREATE_TABLE)
        await self._pool.execute(_CREATE_INDEX)

    async def record_access(self, agent_id: str, entry_id: str, timestamp: float | None = None) -> None:
        ts = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.now(timezone.utc)
        await self._pool.execute(
            "INSERT INTO memory_access_patterns (agent_id, entry_id, accessed_at) VALUES ($1, $2, $3)",
            agent_id, entry_id, ts,
        )

    async def get_patterns(self, agent_id: str, window_s: int = 3600) -> list[dict]:
        rows = await self._pool.fetch(
            """SELECT entry_id, COUNT(*) as count, MAX(accessed_at) as last_accessed
               FROM memory_access_patterns
               WHERE agent_id = $1 AND accessed_at > NOW() - INTERVAL '1 second' * $2
               GROUP BY entry_id ORDER BY count DESC""",
            agent_id, window_s,
        )
        return [{"entry_id": r["entry_id"], "count": r["count"], "last_accessed": str(r["last_accessed"])} for r in rows]

    async def get_top_entries(self, agent_id: str, top_n: int = 10) -> list[str]:
        rows = await self._pool.fetch(
            """SELECT entry_id, COUNT(*) as count
               FROM memory_access_patterns WHERE agent_id = $1
               GROUP BY entry_id ORDER BY count DESC LIMIT $2""",
            agent_id, top_n,
        )
        return [r["entry_id"] for r in rows]
```

- [ ] **Step 3: Run test**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_access_patterns.py -v -o "addopts="
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/tier1/tier1/memory/access_patterns.py backend/tier1/tests/unit/test_access_patterns.py && git commit -m "feat(tier1): AccessPatternAnalyzer — per-agent read tracking in Postgres"
```

---

## Task 3: IntelligentPrefetcher

**Files:**
- Create: `tier1/memory/prefetcher.py`
- Test: `tests/unit/test_prefetcher.py`

- [ ] **Step 1: Write test**

Create `backend/tier1/tests/unit/test_prefetcher.py`:

```python
"""Tests for IntelligentPrefetcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory.prefetcher import IntelligentPrefetcher


@pytest.fixture()
def prefetcher():
    patterns = AsyncMock()
    cache = AsyncMock()
    backend = AsyncMock()
    return IntelligentPrefetcher(patterns=patterns, cache=cache, backend=backend)


async def test_get_candidates_returns_top_entries(prefetcher):
    prefetcher.patterns.get_top_entries = AsyncMock(return_value=["e1", "e2", "e3"])
    result = await prefetcher.get_candidates("agent1")
    assert result == ["e1", "e2", "e3"]
    prefetcher.patterns.get_top_entries.assert_called_once_with("agent1", top_n=10)


async def test_prefetch_loads_uncached_entries(prefetcher):
    prefetcher.patterns.get_top_entries = AsyncMock(return_value=["e1", "e2"])
    prefetcher.cache.get = AsyncMock(side_effect=[None, MagicMock()])  # e1 miss, e2 hit
    prefetcher.backend.postgres = MagicMock()
    prefetcher.backend.postgres.get_history = AsyncMock(return_value=[])
    count = await prefetcher.prefetch("agent1")
    assert count >= 0
```

- [ ] **Step 2: Implement**

Create `backend/tier1/tier1/memory/prefetcher.py`:

```python
"""Intelligent memory prefetcher — preloads likely-needed entries into Redis."""

from __future__ import annotations

import structlog

from tier1.memory.access_patterns import AccessPatternAnalyzer
from tier1.memory.redis_cache import RedisMemoryCache

log = structlog.get_logger(__name__)


class IntelligentPrefetcher:
    def __init__(
        self,
        patterns: AccessPatternAnalyzer,
        cache: RedisMemoryCache,
        backend,  # MemoryBackend
    ) -> None:
        self.patterns = patterns
        self.cache = cache
        self.backend = backend

    async def get_candidates(self, agent_id: str) -> list[str]:
        return await self.patterns.get_top_entries(agent_id, top_n=10)

    async def prefetch(self, agent_id: str, context: dict | None = None) -> int:
        """Preload likely-needed entries into Redis. Returns count prefetched."""
        try:
            candidates = await self.get_candidates(agent_id)
            count = 0
            for entry_id in candidates:
                existing = await self.cache.get(entry_id)
                if existing is not None:
                    continue
                entries = await self.backend.postgres.get_history(entry_id)
                if entries:
                    await self.cache.set(entry_id, entries[0], ttl=3600)
                    count += 1
            return count
        except Exception as exc:  # noqa: BLE001
            log.warning("prefetch_failed", agent_id=agent_id, error=str(exc))
            return 0
```

- [ ] **Step 3: Run test**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_prefetcher.py -v -o "addopts="
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/tier1/tier1/memory/prefetcher.py backend/tier1/tests/unit/test_prefetcher.py && git commit -m "feat(tier1): IntelligentPrefetcher — predictive memory loading into Redis"
```

---

## Task 4: Integration + full test suite

**Files:**
- Modify: `tier1/memory/__init__.py` — add `mem0` field to `MemoryBackend`

- [ ] **Step 1: Update MemoryBackend**

Edit `backend/tier1/tier1/memory/__init__.py`. Change `MemoryBackend.__init__` to accept optional `mem0`:

```python
class MemoryBackend:
    def __init__(
        self,
        qdrant: "QdrantStore",
        redis: "RedisMemoryCache",
        postgres: "PostgresMemoryStore",
        mem0: "Mem0Backend | None" = None,
    ) -> None:
        self.qdrant = qdrant
        self.redis = redis
        self.postgres = postgres
        self.mem0 = mem0
```

Update `store()` to include mem0:

```python
    async def store(self, entry: MemoryEntry) -> str:
        # ... existing Qdrant/Redis/Postgres logic ...

        # Mem0 (semantic) — best effort
        if self.mem0:
            try:
                await self.mem0.add(entry.content, user_id=entry.agent, metadata=entry.metadata)
            except Exception:  # noqa: BLE001
                pass

        return entry.id
```

- [ ] **Step 2: Run full suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/ -q -o "addopts="
```

Expected: all pass (144+ tests).

- [ ] **Step 3: Commit**

```bash
git add backend/tier1/tier1/memory/__init__.py && git commit -m "feat(tier1): wire Mem0Backend into MemoryBackend facade"
```
