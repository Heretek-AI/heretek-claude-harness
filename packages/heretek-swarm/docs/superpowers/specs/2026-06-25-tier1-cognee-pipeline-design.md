# Tier 1 Cognee Knowledge Graph Pipeline — Design Spec

**Date:** 2026-06-25
**Status:** Approved (pending implementation)

## Context

Tier 1 Core Triad now has a memory foundation (sub-project A): `MemoryBackend` over Qdrant, Redis, and PostgreSQL. But it has no knowledge graph — deliberation results are stored as flat entries with no entity/relationship structure. Cognee adds a knowledge graph layer that extracts entities and relations from memory entries, enabling graph-traversal-enriched search.

Cognee sits in front of `MemoryBackend` as a pipeline orchestrator — it calls `MemoryBackend.store()` for vector/cache/lineage, and maintains its own Kùzu graph for entity/relationship structure.

## Goals

1. `CogneePipeline` class with 5-stage pipeline: `add()`, `cognify()`, `search()`, `improve()`
2. Kùzu embedded graph backend for entity/relation storage
3. Entity/relation extraction via LLM (structured output)
4. Graph-traversal-enriched search (combine vector results with graph neighbors)
5. Integration with existing `MemoryBackend` facade

## Non-goals

- REST API for graph queries (NATS only for now)
- Real-time graph updates (batch `cognify()` is sufficient)
- Graph visualization or dashboards
- Sub-project C (mem0 + pattern analysis) — separate spec

## Architecture

Cognee sits in front of `MemoryBackend` as a pipeline orchestrator.

```
CogneePipeline
├── add(text, metadata) → extract entities/relations → MemoryBackend.store()
├── cognify() → batch graph extraction on unprocessed entries
├── search(query, top_k) → enrich via graph traversal → MemoryBackend.search()
└── improve() → prune stale edges, merge duplicates
```

## Components

### A. `tier1/memory/cognee_store.py`

`CogneePipeline` class:

```python
class CogneePipeline:
    def __init__(self, memory_backend: MemoryBackend, graph_path: str, llm_provider: str = "minimax"):
        self.memory = memory_backend
        self.graph_path = graph_path
        self.llm_provider = llm_provider
        self._graph: kuzu.Database | None = None

    async def add(self, text: str, metadata: dict | None = None) -> str:
        """5-stage: chunk → extract entities → store graph → store memory → mark processed."""

    async def cognify(self, batch_size: int = 10) -> int:
        """Process unprocessed documents: extract entities/relations, build graph edges."""

    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]:
        """Vector search + graph enrichment: for each result, traverse graph for related entities."""

    async def improve(self) -> None:
        """Best-effort graph refinement: prune stale edges, merge duplicate entities."""
```

### B. Kùzu graph schema

Embedded, disk-persistent at `graph_path`.

**Node tables:**
- `Entity`: `id UUID`, `name STRING`, `type STRING`, `embedding FLOAT[1536]`, `created_at TIMESTAMP`
- `Document`: `id UUID`, `content_hash STRING`, `processed BOOLEAN`, `created_at TIMESTAMP`

**Edge tables:**
- `RELATES_TO`: `source Entity`, `target Entity`, `relation_type STRING`, `weight FLOAT`, `created_at TIMESTAMP`
- `CONTAINS`: `source Document`, `target Entity`

### C. Entity extraction

Uses LLM with structured output to extract entities and relations from text:

```python
EXTRACTION_PROMPT = """Extract entities and relationships from this text.
Return JSON: {"entities": [{"name": "...", "type": "..."}], "relations": [{"source": "...", "target": "...", "type": "..."}]}
Text: {text}"""
```

Entity types: `person`, `concept`, `decision`, `component`, `metric`, `event`
Relation types: `causes`, `depends_on`, `contradicts`, `supports`, `part_of`, `decided_by`

### D. Search enrichment

```python
async def search(self, query, *, top_k=5):
    # 1. Vector search via MemoryBackend
    vector_results = await self.memory.search(query, top_k=top_k)

    # 2. For each result, extract entities and traverse graph
    enriched = []
    for entry in vector_results:
        entities = self._find_entities_for_entry(entry.id)
        neighbors = self._traverse_graph(entities, hops=2)
        enriched.append({"entry": entry, "graph_context": neighbors})

    return enriched
```

## Data flow

```
Agent → CogneePipeline.add("auth decision: use JWT")
  ├── chunk text into passages
  ├── extract entities via LLM: [Entity("JWT", "concept"), Entity("auth", "concept")]
  ├── extract relations: [(JWT, auth, "part_of")]
  ├── store entities/relations in Kùzu graph
  ├── MemoryBackend.store(MemoryEntry(content="auth decision: use JWT", ...))
  └── mark document as processed in Kùzu

Agent → CogneePipeline.search("what did we decide about auth?")
  ├── MemoryBackend.search("what did we decide about auth?") → vector results
  ├── for each result, find entities → traverse Kùzu graph (2 hops)
  ├── collect related entities: JWT, token, middleware, etc.
  └── return enriched results with graph context
```

## Error handling

- Kùzu unavailable: `add()` still stores to MemoryBackend (degrades to tier-1-only). `search()` returns vector results without graph enrichment.
- LLM unavailable for extraction: `add()` stores raw content without entity extraction. `cognify()` skips unprocessed entries.
- `improve()` is best-effort, runs in background. Failures logged, not raised.

## Testing

| Test | What it verifies |
|---|---|
| `test_cognee_pipeline.py` | Pipeline stages: add, cognify, search, improve (mocked Kùzu + LLM) |
| `test_cognee_extraction.py` | Entity/relation extraction prompt parsing |
| `test_cognee_graph.py` | Kùzu graph operations: create nodes, traverse, prune |

All mocked — no live Kùzu or LLM calls for unit tests.

## Dependencies

New:
```
kuzu>=0.4
```

Already present: `openai>=1.0` (for LLM extraction calls)

## Implementation order

1. Add `kuzu>=0.4` to dependencies
2. Create `tier1/memory/cognee_store.py` with `CogneePipeline`
3. Implement entity extraction (LLM structured output)
4. Implement Kùzu graph operations (create, traverse, prune)
5. Wire into `MemoryBackend` (add `cognee` field, update `store()`)
6. Write unit tests (3 test files)
7. Run full suite, verify coverage
