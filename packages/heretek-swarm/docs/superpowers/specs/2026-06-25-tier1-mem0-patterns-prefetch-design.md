# Tier 1 Mem0 Semantic Memory + Access Patterns + Prefetcher — Design Spec

**Date:** 2026-06-25
**Status:** Approved (pending implementation)

## Context

Tier 1 now has a memory foundation (sub-project A: Qdrant + Redis + PostgreSQL), a knowledge graph pipeline (sub-project B: Cognee), but no semantic memory layer, no access pattern tracking, and no predictive prefetching. Sub-project C adds all three.

Mem0 provides semantic memory (user preferences, facts, relationships) backed by vector search. Access pattern analytics track which entries agents read and when. The prefetcher uses these patterns to preload likely-needed entries into Redis before agents request them.

## Goals

1. `Mem0Backend` — wraps mem0ai library with add/search/update/delete
2. `AccessPatternAnalyzer` — per-agent read-pattern tracking in PostgreSQL
3. `IntelligentPrefetcher` — predictive memory loading into Redis cache
4. Integration with existing `MemoryBackend` facade

## Non-goals

- Real-time streaming of access patterns (batch is sufficient)
- Complex ML models for prediction (frequency-based heuristic is fine for now)
- Dashboard/analytics UI for access patterns
- Cross-agent pattern sharing

## Architecture

Three components that layer onto existing memory infrastructure.

```
MemoryBackend (facade)
├── QdrantStore (vectors)
├── RedisMemoryCache (ephemeral)
├── PostgresMemoryStore (lineage)
├── CogneePipeline (knowledge graph) — sub-project B
└── Mem0Backend (semantic memory) — NEW

AccessPatternAnalyzer
├── tracks per-agent read patterns
└── stores in Postgres memory_access_patterns table

IntelligentPrefetcher
├── reads AccessPatternAnalyzer patterns
├── predicts next N entries agent will need
└── preloads into RedisMemoryCache
```

## Components

### A. `tier1/memory/mem0_store.py`

`Mem0Backend` class:

```python
class Mem0Backend:
    def __init__(self, api_key: str | None = None, vector_store: str = "qdrant"):
        self._client = None
        self._api_key = api_key
        self._vector_store = vector_store
        self._enabled = bool(api_key)

    def _ensure_client(self):
        """Lazy init mem0ai client."""
        if not self._enabled:
            return
        if self._client is None:
            from mem0ai import MemoryClient
            self._client = MemoryClient(api_key=self._api_key)

    async def add(self, text: str, user_id: str, metadata: dict | None = None) -> str | None:
        """Add semantic memory entry. Returns memory ID or None if disabled."""

    async def search(self, query: str, user_id: str, top_k: int = 5) -> list[dict]:
        """Search semantic memory. Returns list of memory dicts."""

    async def update(self, memory_id: str, text: str) -> bool:
        """Update existing memory entry."""

    async def delete(self, memory_id: str) -> bool:
        """Delete memory entry."""
```

### B. `tier1/memory/access_patterns.py`

`AccessPatternAnalyzer` class:

```python
class AccessPatternAnalyzer:
    def __init__(self, pool):
        self._pool = pool  # asyncpg pool

    async def connect(self):
        """Create memory_access_patterns table if not exists."""

    async def record_access(self, agent_id: str, entry_id: str, timestamp: float | None = None):
        """Log a memory read event."""

    async def get_patterns(self, agent_id: str, window_s: int = 3600) -> list[dict]:
        """Return access frequency data for an agent within time window."""

    async def get_top_entries(self, agent_id: str, top_n: int = 10) -> list[str]:
        """Return most-frequently-accessed entry IDs for an agent."""
```

Postgres table:
```sql
CREATE TABLE IF NOT EXISTS memory_access_patterns (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    accessed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_access_agent ON memory_access_patterns(agent_id, accessed_at);
```

### C. `tier1/memory/prefetcher.py`

`IntelligentPrefetcher` class:

```python
class IntelligentPrefetcher:
    def __init__(self, patterns: AccessPatternAnalyzer, cache: RedisMemoryCache, backend: MemoryBackend):
        self.patterns = patterns
        self.cache = cache
        self.backend = backend

    async def prefetch(self, agent_id: str, context: dict | None = None) -> int:
        """Predict and preload entries into Redis. Returns count of entries prefetched."""

    async def get_candidates(self, agent_id: str) -> list[str]:
        """Return entry IDs likely needed next based on access patterns."""
```

### D. Integration with MemoryBackend

`MemoryBackend` gains a `mem0` field:

```python
class MemoryBackend:
    def __init__(self, qdrant, redis, postgres, mem0=None):
        self.mem0 = mem0  # Mem0Backend | None

    async def store(self, entry):
        # ... existing tiers ...
        if self.mem0:
            await self.mem0.add(entry.content, user_id=entry.agent, metadata=entry.metadata)
```

## Data flow

```
Agent reads memory:
  1. AccessPatternAnalyzer.record_access(agent_id, entry_id)
  2. Normal MemoryBackend.search() flow

Prefetcher runs (periodic or triggered):
  1. AccessPatternAnalyzer.get_top_entries(agent_id) → [entry_id_1, entry_id_2, ...]
  2. For each: MemoryBackend.get_session(entry_id) → check if already cached
  3. If not cached: fetch from Postgres, store in RedisMemoryCache
  4. Return count of prefetched entries

Agent searches memory:
  1. RedisMemoryCache.get() — fast path (includes prefetched entries)
  2. If miss: QdrantStore.search() — vector search
  3. If mem0 enabled: Mem0Backend.search() — semantic search
```

## Error handling

- mem0 unavailable: `Mem0Backend._enabled = False`, all ops return None/empty. MemoryBackend works without semantic layer.
- Prefetcher failure: logged, no impact on search correctness. Entries still fetched on-demand.
- Access pattern recording failure: logged, prefetcher uses stale/empty patterns.

## Testing

| Test | What it verifies |
|---|---|
| `test_mem0_store.py` | Mem0Backend add/search/update/delete (mocked mem0ai) |
| `test_access_patterns.py` | AccessPatternAnalyzer record/get (mocked Postgres pool) |
| `test_prefetcher.py` | IntelligentPrefetcher prefetch/candidates (mocked deps) |

All mocked — no live mem0/Postgres/Redis for unit tests.

## Dependencies

Already present: `mem0ai` (in architecture doc), `redis`, `asyncpg`

No new dependencies needed.

## Implementation order

1. Create `tier1/memory/mem0_store.py` with `Mem0Backend`
2. Create `tier1/memory/access_patterns.py` with `AccessPatternAnalyzer`
3. Create `tier1/memory/prefetcher.py` with `IntelligentPrefetcher`
4. Wire into `MemoryBackend` (add `mem0` field)
5. Write unit tests (3 test files)
6. Run full suite
