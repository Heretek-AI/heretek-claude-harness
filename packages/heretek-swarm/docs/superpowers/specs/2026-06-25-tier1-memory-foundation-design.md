# Tier 1 Memory Foundation — Design Spec

**Date:** 2026-06-25
**Status:** Approved (pending implementation)

## Context

Tier 1 Core Triad deliberates but has no memory — each deliberation starts from zero. The architecture doc defines a dual-tier memory system with Qdrant (vectors), PostgreSQL (lineage), and Redis (ephemeral cache). This sub-project builds the foundation: the three storage tiers behind a unified `MemoryBackend` facade, with NATS subjects for agent-to-memory communication.

## Goals

1. `MemoryBackend` facade with `store()`, `search()`, `get_history()`, `get_session()`.
2. Qdrant vector store for semantic search over memory entries.
3. Redis ephemeral cache for session-scoped recent context.
4. PostgreSQL persistent store for decision history and lineage.
5. NATS subjects for async store/retrieve between agents and memory.
6. Embedding model configurable via `TIER1_EMBEDDING_MODEL`.

## Non-goals

- Cognee knowledge graph pipeline (sub-project B).
- mem0 semantic memory (sub-project C).
- Access pattern analysis or prefetching (sub-project C).
- REST API endpoints for memory (NATS only for now).

## Architecture

Three storage tiers behind a unified `MemoryBackend` facade.

```
tier1/memory/
├── __init__.py          # MemoryBackend facade, MemoryEntry, MemoryType
├── qdrant_store.py      # Vector store (embed + search + CRUD)
├── redis_cache.py       # Ephemeral session cache (TTL-based)
├── postgres_store.py    # Persistent decision history + lineage
└── nats_memory.py       # NATS subjects for store_request/retrieve_request
```

`MemoryBackend` exposes:
- `async store(entry: MemoryEntry) -> str` — stores to all applicable tiers
- `async search(query: str, *, top_k: int = 5) -> list[MemoryEntry]` — vector search via Qdrant
- `async get_history(deliberation_id: str) -> list[MemoryEntry]` — Postgres lineage
- `async get_session(key: str) -> MemoryEntry | None` — Redis ephemeral lookup

## Components

### A. `tier1/memory/__init__.py`

`MemoryType` enum: `episodic`, `semantic`, `procedural`

`MemoryEntry` dataclass:
```python
@dataclass
class MemoryEntry:
    id: str               # uuid4
    content: str          # text content
    memory_type: MemoryType
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)
    source: str = ""      # "deliberation", "user", "external"
    deliberation_id: str | None = None
    agent: str = ""       # which agent produced this
    created_at: str = ""  # ISO timestamp
    ttl_seconds: int | None = None  # None = permanent
```

`MemoryBackend` class:
- Constructor takes `qdrant: QdrantStore`, `redis: RedisCache`, `postgres: PostgresStore`
- Embedding model configurable via `TIER1_EMBEDDING_MODEL` (default `text-embedding-3-small`)

### B. `tier1/memory/qdrant_store.py`

- `connect()` — create collection if not exists (vector size from embedding model)
- `store(entry)` — embed content, upsert to Qdrant
- `search(query, top_k)` — embed query, cosine search, return top_k results
- `delete(id)` — remove vector by ID

### C. `tier1/memory/redis_cache.py`

- `get(key)` — retrieve cached MemoryEntry
- `set(key, entry, ttl)` — cache with TTL
- `delete(key)` — remove from cache

### D. `tier1/memory/postgres_store.py`

Extends existing `PostgresPool` with memory-specific tables:
- `memory_entries` — stores `MemoryEntry` records (lineage)
- `decision_history` — stores deliberation decisions with references

### E. `tier1/memory/nats_memory.py`

Two NATS subjects:
- `swarm.internal.memory.store` — subscribe, store entry, publish confirmation
- `swarm.internal.memory.retrieve` — subscribe, search, publish results

## Data flow

```
Agent calls MemoryBackend.store(entry)
    │
    ├── embed content (OpenAI / local)
    ├── store vector → Qdrant (permanent)
    ├── cache entry → Redis (TTL-based, ephemeral)
    ├── write lineage → PostgreSQL (permanent)
    └── publish to NATS swarm.internal.memory.store

Agent calls MemoryBackend.search(query, top_k=5)
    │
    ├── embed query
    ├── cosine search → Qdrant
    ├── rank results
    └── return top_k MemoryEntry[]

Agent calls MemoryBackend.get_history(deliberation_id)
    │
    └── query PostgreSQL → return all entries for that deliberation

Agent calls MemoryBackend.get_session(key)
    │
    └── Redis lookup → return cached MemoryEntry or None
```

## Error handling

- Qdrant unavailable: `store()` still writes to Postgres + Redis; `search()` returns empty list.
- Redis unavailable: `store()` still writes to Qdrant + Postgres; `get_session()` returns None.
- Postgres unavailable: `store()` still writes to Qdrant + Redis; `get_history()` raises. Lineage is critical.
- Embedding API unavailable: `store()` saves without embedding; `search()` returns empty. Log warning.
- NATS unavailable: `store()` still writes to all 3 tiers. NATS is fire-and-forget for observation.

## Testing

| Test | What it verifies |
|---|---|
| `test_memory_entry.py` | MemoryEntry creation, serialization, defaults |
| `test_qdrant_store.py` | Vector store/retrieve/search (mocked Qdrant client) |
| `test_redis_cache.py` | Cache get/set/delete (mocked Redis) |
| `test_postgres_store.py` | Decision history write/read (mocked Postgres) |
| `test_memory_backend.py` | Facade: store writes to all tiers, search hits Qdrant, history hits Postgres |
| `test_nats_memory.py` | NATS subject handler: store/retrieve via NATS |

All mocked — no live Qdrant/Redis/Postgres needed for unit tests.

## Dependencies

Already present: `qdrant-client>=1.7`, `redis>=5.0`, `asyncpg>=0.29`.

New config fields in `tier1/config.py`:
```python
embedding_model: str = "text-embedding-3-small"
embedding_dimensions: int = 1536
memory_ttl_s: int = 3600
```

## Implementation order

1. Add config fields to `tier1/config.py`
2. Create `tier1/memory/__init__.py` with MemoryEntry + MemoryType + MemoryBackend facade
3. Create `tier1/memory/qdrant_store.py` with vector CRUD
4. Create `tier1/memory/redis_cache.py` with TTL cache
5. Create `tier1/memory/postgres_store.py` with decision history tables
6. Create `tier1/memory/nats_memory.py` with store/retrieve subjects
7. Wire MemoryBackend into `create_app()` lifespan
8. Write unit tests (6 test files)
9. Run full suite, verify coverage ≥ 80%
