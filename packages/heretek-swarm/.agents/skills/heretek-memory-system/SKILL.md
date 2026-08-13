---
name: heretek-memory-system
description: >-
  Memory system development for Heretek Swarm's Cognee-backed memory. Use when
  implementing memory operations, working with knowledge graphs, or debugging
  memory issues. Covers Cognee API, access patterns, and intelligent prefetching.
---

# Heretek Swarm Memory System

## Architecture Overview

The memory system is built on **Cognee** (knowledge graph + vector memory engine) with access-pattern optimization and intelligent pre-fetching.

### Core Components
```
backend/heretek_swarm/memory/
├── __init__.py           # Package exports (re-exports MemoryStore + Mem0Backend)
├── access_patterns.py    # Tier classification, pattern analysis
├── cognee_reader.py      # Read-only Cognee client
├── cognee_writer.py      # Write-path Cognee client
├── eliza_memory.py       # Importance-decay memory manager
├── mem0_backend.py       # Mem0 (mem0ai) backend wrapper (Phase 1.1)
├── prefetcher.py         # LRU/LFU caches, pre-fetch scheduling
└── store.py              # MemoryStore Protocol + adapters + get_default_store()
```

### No Legacy Code
The following have been **deleted** and must not be reintroduced:
- `base.py`, `persistent.py`, `tiering.py`, `versioned.py`, `compression.py`, `migration_strategies.py`
- Legacy classes: `DualTierMemory`, `PersistentMemory`, `TieringManager`, `VersionedMemory`, `CompressionManager`

## The MemoryStore Protocol (Phase 1.1 — canonical interface)

New code should use the **`MemoryStore` Protocol** as the canonical interface
to all memory backends. The `CogneeMemoryReader` / `CogneeMemoryWriter` /
`Mem0Backend` classes still exist and are adapted to the protocol by
`_CogneeAdapter` and `_Mem0Adapter`; a `_NullMemoryStore` is the in-memory
fallback that keeps the swarm bootable in dev.

```python
from heretek_swarm.memory import MemoryStore, MemoryType, get_default_store

store: MemoryStore = get_default_store()  # resolved from env

# 5-stage pipeline
await store.add(entry)                              # write
entry = await store.read(memory_id)                 # read
hits = await store.search("query", top_k=10)        # search
health = await store.health()                       # backend health
await store.close()                                 # cleanup
```

### MemoryType enum
The canonical tier abstraction is `MemoryType` (StrEnum):
- `EPISODIC` — events and experiences
- `SEMANTIC` — knowledge and facts
- `PROCEDURAL` — skills and procedures
- `WORKING` — short-term context

```python
from heretek_swarm.memory import MemoryType

# Maps to cognee dataset name (e.g. 'episodic-agent-1')
dataset = MemoryType.EPISODIC.to_dataset("agent-1")
```

### Resolver

`get_default_store()` returns:
- `_CogneeAdapter` when `COGNEE_ENABLED=1` (default)
- `_Mem0Adapter` when `MEM0_ENABLED=1` (and `COGNEE_ENABLED!=1`)
- `_NullMemoryStore` (in-memory) when neither is enabled

`reset_default_store()` clears the cache (useful in tests).

### Adapter pattern

`_CogneeAdapter` wraps `CogneeMemoryWriter`; `_Mem0Adapter` wraps
`Mem0Backend`. Both delegate to the existing API surface; new code should
program against the Protocol, not the wrapper directly.

## Cognee API

### Reader Operations
```python
from heretek_swarm.memory import CogneeMemoryReader

reader = CogneeMemoryReader()

# Search memories
results = await reader.search(
    query="search text",
    limit=10,
    agent="agent_name",
    min_importance=0.5
)

# Get specific memory
memory = await reader.get(memory_id="abc123")

# List memories with filters
memories = await reader.list(
    tags=["learning", "observation"],
    created_after=datetime(2024, 1, 1)
)
```

### Writer Operations
```python
from heretek_swarm.memory import CogneeMemoryWriter

writer = CogneeMemoryWriter()

# Add memory
memory_id = await writer.add(
    content="observation text",
    metadata={
        "agent": "explorer",
        "importance": 0.8,
        "tags": ["observation", "learning"],
        "context": {"task_id": "T001"}
    }
)

# Process into knowledge graph
await writer.cognify()

# Update memory
await writer.update(
    memory_id=memory_id,
    content="updated text",
    metadata={"importance": 0.9}
)

# Delete memory
await writer.delete(memory_id=memory_id)
```

## Access Patterns

### Tier Classification
```python
from heretek_swarm.memory import AccessPattern, AccessTier

# Analyze access pattern
analyzer = AccessPatternAnalyzer()
pattern = analyzer.analyze(access_logs)

# Get tier recommendation
tier = pattern.recommended_tier  # HOT, WARM, COLD, ARCHIVE

# Apply tier
await writer.set_tier(memory_id, tier)
```

### Pattern Types
- **Sequential** - Accesses in order
- **Random** - No pattern
- **Temporal** - Time-based access
- **Frequency** - Based on access count

### Usage
```python
from heretek_swarm.memory import AccessPatternAnalyzer, MemoryAccessProfile

# Create analyzer
analyzer = AccessPatternAnalyzer()

# Analyze profile
profile = MemoryAccessProfile(
    agent="explorer",
    time_window=timedelta(hours=24),
    access_count=150
)

# Get recommendations
recommendations = analyzer.recommend(profile)
```

## Intelligent Prefetching

### Cache Types
```python
from heretek_swarm.memory import LRUCache, LFUCache

# LRU Cache (Least Recently Used)
lru = LRUCache(max_size=1000)
await lru.set("key", value)
value = await lru.get("key")

# LFU Cache (Least Frequently Used)
lfu = LFUCache(max_size=1000)
await lfu.set("key", value)
value = await lfu.get("key")
```

### Prefetch Scheduling
```python
from heretek_swarm.memory import (
    IntelligentPrefetcher,
    PreFetchScheduler,
    PreFetchRequest,
    PreFetchPriority
)

# Create prefetcher
prefetcher = IntelligentPrefetcher(
    reader=reader,
    cache=lru
)

# Schedule prefetch
request = PreFetchRequest(
    query="likely needed context",
    priority=PreFetchPriority.HIGH,
    agent="explorer",
    estimated_access_time=datetime.now() + timedelta(minutes=5)
)

scheduler = PreFetchScheduler(prefetcher)
await scheduler.schedule(request)
```

### Prefetch Strategies
- **Pattern-based** - Based on historical access patterns
- **Time-based** - Scheduled prefetching
- **Priority-based** - High priority items first
- **Predictive** - ML-based prediction

## Eliza Memory Manager

### Importance-Decay Pattern
```python
from heretek_swarm.memory import MemoryManager, create_memory_manager

# Create manager
manager = create_memory_manager(
    decay_rate=0.1,
    importance_threshold=0.3
)

# Add memory with importance
memory_id = await manager.remember(
    content="important observation",
    importance=0.9,
    agent="explorer"
)

# Recall memories (importance-weighted)
memories = await manager.recall(
    query="relevant context",
    limit=10,
    min_importance=0.5
)

# Forget low-importance memories
forgotten = await manager.forget(
    threshold=0.2,
    older_than=timedelta(days=30)
)
```

### Memory Types
- **Episodic** - Events and experiences
- **Semantic** - Knowledge and facts
- **Procedural** - Skills and procedures
- **Emotional** - Emotional associations

## Mem0 Backend (Phase 1.1)

`mem0_backend.py` is a wrapper around the `mem0ai` package. It's an
alternative to the cognee adapter; choose one or the other per
environment via env vars (cognee is the default).

```python
from heretek_swarm.memory import Mem0Backend, MEM0_AVAILABLE

if MEM0_AVAILABLE:
    backend = Mem0Backend()
    backend.configure(
        qdrant_url="http://qdrant:6333",
        collection_name="heretek_memories",
    )
    # Method surface matches CogneeMemoryWriter where possible
    memory_id = backend.add(
        content="observation",
        agent_id="explorer",
        metadata={"importance": 0.8, "tags": ["observation"]},
    )
    results = backend.search("observation", top_k=5)
    backend.delete_memory(memory_id)
```

`mem0ai` is optional; the module imports it lazily. When `mem0ai` is
unavailable, `MEM0_AVAILABLE` is `False` and `Mem0Backend` is a stub
that 503s on every method. Use `_get_memory_store()` (or
`get_default_store()`) to get the canonical store regardless of which
backend is wired.

## Testing Memory Operations

### Unit Tests
```python
import pytest
from heretek_swarm.memory import CogneeMemoryReader, CogneeMemoryWriter

@pytest.mark.asyncio
async def test_memory_roundtrip():
    writer = CogneeMemoryWriter()
    reader = CogneeMemoryReader()

    # Write
    memory_id = await writer.add(
        content="test memory",
        metadata={"importance": 0.8}
    )

    # Read
    memory = await reader.get(memory_id)
    assert memory.content == "test memory"
    assert memory.metadata["importance"] == 0.8

@pytest.mark.asyncio
async def test_search():
    writer = CogneeMemoryWriter()
    reader = CogneeMemoryReader()

    # Add test data
    await writer.add("Python programming", tags=["coding"])
    await writer.add("JavaScript programming", tags=["coding"])
    await writer.cognify()

    # Search
    results = await reader.search("programming", limit=2)
    assert len(results) == 2
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_memory_with_agent():
    agent = ExplorerAgent(config)
    writer = CogneeMemoryWriter()

    # Agent observes
    observation = await agent.observe(context)

    # Store in memory
    await writer.add(
        content=observation,
        metadata={"agent": "explorer", "importance": 0.7}
    )

    # Later, agent recalls
    reader = CogneeMemoryReader()
    memories = await reader.search("observation", agent="explorer")
    assert len(memories) > 0
```

## Debugging Memory Issues

### Common Problems

1. **Cognee connection failed**
   - Check if Cognee service is running
   - Verify connection string
   - Check network connectivity

2. **Memory not found**
   - Verify memory_id exists
   - Check access permissions
   - Ensure memory wasn't deleted

3. **Search returns empty**
   - Run `cognify()` after adding memories
   - Check search query
   - Verify memory tags

4. **Prefetch not working**
   - Check cache size limits
   - Verify prefetch schedule
   - Monitor access patterns

### Debug Commands
```bash
# Check memory count
python -c "from heretek_swarm.memory import CogneeMemoryReader; import asyncio; r = CogneeMemoryReader(); print(asyncio.run(r.count()))"

# List recent memories
python -c "from heretek_swarm.memory import CogneeMemoryReader; import asyncio; r = CogneeMemoryReader(); print(asyncio.run(r.list(limit=10)))"

# Check cache stats
python -c "from heretek_swarm.memory import LRUCache; c = LRUCache(100); print(c.stats())"
```

## Performance Optimization

### Batch Operations
```python
# Batch add
memories = [
    {"content": f"memory {i}", "metadata": {"importance": 0.5}}
    for i in range(100)
]
await writer.add_batch(memories)

# Batch search
queries = ["query1", "query2", "query3"]
results = await reader.search_batch(queries, limit=10)
```

### Caching Strategy
1. **Hot data** - Keep in LRU cache
2. **Warm data** - Prefetch on access
3. **Cold data** - Load on demand
4. **Archive** - Compress and store

### Indexing
- Use tags for fast filtering
- Create custom indexes for common queries
- Monitor query performance

## Gotchas

1. **Always run `cognify()`** after adding memories - they're not searchable until processed
2. **No legacy imports** - Only use Cognee-backed types
3. **Async operations** - All memory operations are async
4. **Importance decay** - Memories fade over time unless reinforced
5. **Cache invalidation** - Manual invalidation may be needed
6. **Batch limits** - Respect Cognee API rate limits
7. **Prefer the Protocol** - New code should call `get_default_store()` and use the
   `MemoryStore` Protocol methods, not the legacy `CogneeMemoryReader` /
   `CogneeMemoryWriter` directly. The adapters wrap those classes; the Protocol
   is the migration target.
8. **MemoryMixin no-op when no analyzer** - `MemoryMixin._track_memory_access`
   and `MemoryMixin._prefetch_relevant` are no-ops when neither
   `self.memory_store` nor `self.access_analyzer` is set (the canonical
   `MemoryStore` is the primary memory path). The mixin has a
   `_get_memory_store()` method that returns the canonical store, preferring
   `self.memory_store` if set, falling back to `get_default_store()`. The
   legacy `self.access_analyzer` path is preserved for the few opt-in actors
   (arbiter, examiner, metis, empath, historian).

## Best Practices

1. Use meaningful tags for memories
2. Set appropriate importance levels
3. Implement memory cleanup schedules
4. Monitor memory usage and performance
5. Use negative assertions to prevent legacy code creep
6. Test both read and write paths
7. Document memory schemas
8. **Use the `MemoryStore` Protocol** for new code — it's the
   backend-agnostic interface; `Cognee` is just one of the 3 implementations
   (cognee / mem0 / null).
9. **Map MemoryType to cognee dataset name** via `MemoryType.to_dataset(identifier)`
   so the cognee 5-stage pipeline (add → cognify → search → improve) can route
   by tier uniformly.
