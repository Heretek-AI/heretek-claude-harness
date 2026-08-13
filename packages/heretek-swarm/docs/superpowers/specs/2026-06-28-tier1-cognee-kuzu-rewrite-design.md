# Tier 1 Cognee → Kùzu Rewrite — Design Spec

**Date:** 2026-06-28
**Status:** Approved

## Context

The Tier 1 Cognee Pipeline spec (2026-06-25) defined a 5-stage pipeline
backed by an embedded Kùzu graph. The existing implementation in
`tier1/memory/cognee_store.py` instead wraps the `cognee` library and
uses NetworkX as the graph backend — diverging from the spec's Kùzu +
openai-SDK approach. Both pieces are 0% covered and currently inert.
This sub-project aligns the code with the approved spec: Kùzu as the
graph backend, openai SDK for entity extraction (already wired via
commit 7be68b06 for MiniMax), and integration with `MemoryBackend`.

## Goals

1. Replace `cognee + NetworkX` with raw Kùzu embedded graph in
   `cognee_store.py`. Public 5-stage surface (`add`, `cognify`,
   `search`, `improve`) preserved.
2. Entity/relation extraction uses the openai SDK pointed at the
   existing MiniMax base URL — no new LLM client.
3. Wire `CogneePipeline` into `MemoryBackend`: optional
   `cognee: CogneePipeline | None = None` field, called from
   `MemoryBackend.store()` after the existing tier writes.
4. Three test files (pipeline stages, extraction parsing, Kùzu graph
   ops). All mocked — no live Kùzu or openai calls.
5. `MemoryBackend.store()` failures in the cognee path are best-effort
   (logged, swallowed); they never break a memory write.

## Non-goals

- Wiring `CogneePipeline` into `create_app()` lifespan (separate
  concern; the existing memory foundation spec already defers this).
- Replacing the cognee Python library across the rest of the codebase
  (only `cognee_store.py` is in scope).
- REST API for graph queries.
- Real-time graph updates or dashboards.
- Sub-project C (mem0 + pattern analysis).

## Architecture

`CogneePipeline` stays in `tier1/memory/cognee_store.py`. Same public
surface as the spec:

```python
class CogneePipeline:
    def __init__(
        self,
        memory_backend: MemoryBackend,
        graph_path: str = ".cognee_data",
        llm_provider: str = "minimax",
    ) -> None:
        ...
        self._db: kuzu.Database | None = None

    async def add(self, text: str, metadata: dict | None = None) -> str: ...
    async def cognify(self, batch_size: int = 10) -> int: ...
    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]: ...
    async def improve(self) -> None: ...
```

Internal wiring:

- `kuzu.Database(graph_path)` opened lazily on first use.
- LLM extraction builds an `openai.AsyncOpenAI(api_key=...,
  base_url=settings.minimax_base_url)` client. Settings are pulled
  from the existing `tier1.config.get_settings()` so the LLM wiring
  from commit 7be68b06 is reused — no new client.
- Extraction prompt (verbatim from the spec):
  ```
  EXTRACTION_PROMPT = """Extract entities and relationships from this text.
  Return JSON: {{"entities": [{{"name": "...", "type": "person|concept|decision|component|metric|event"}}], "relations": [{{"source": "...", "target": "...", "type": "causes|depends_on|contradicts|supports|part_of|decided_by"}}]}}
  Text: {text}"""
  ```

### Kùzu schema (per spec)

Node tables:
- `Entity`: `id UUID`, `name STRING`, `type STRING`,
  `embedding FLOAT[1536]`, `created_at TIMESTAMP`
- `Document`: `id UUID`, `content_hash STRING`, `processed BOOLEAN`,
  `created_at TIMESTAMP`

Edge tables:
- `RELATES_TO`: `source Entity`, `target Entity`, `relation_type STRING`,
  `weight FLOAT`, `created_at TIMESTAMP`
- `CONTAINS`: `source Document`, `target Entity`

`improve()` keeps the spec's behavior: best-effort prune of stale
edges, merge of duplicate entities by name.

## MemoryBackend wiring

```python
class MemoryBackend:
    def __init__(
        self,
        qdrant,
        redis,
        postgres,
        mem0: "Mem0Backend | None" = None,
        cognee: "CogneePipeline | None" = None,
    ) -> None:
        ...
        self.cognee = cognee

    async def store(self, entry: MemoryEntry) -> str:
        ...existing writes to qdrant/redis/postgres...
        if self.cognee is not None:
            try:
                await self.cognee.add(entry.content, metadata=entry.metadata)
            except Exception:
                log.warning("cognee.add_failed", entry_id=entry.id, exc_info=True)
        return entry.id
```

The cognee call sits AFTER the existing tier writes (which already
include qdrant best-effort, redis best-effort, and postgres
critical) so a cognee failure can never block a memory write.

## Components touched

| File | Change |
|---|---|
| `pyproject.toml` | Add `kuzu>=0.4` to dependencies |
| `tier1/memory/cognee_store.py` | Full rewrite per spec; drop `import cognee`; add Kùzu + openai SDK |
| `tier1/memory/__init__.py` | Add `cognee: CogneePipeline \| None = None` parameter to `MemoryBackend.__init__`; call `cognee.add()` from `store()` after existing writes |
| `tests/unit/test_cognee_pipeline.py` (new) | add/cognify/search/improve with mocked Kùzu + mocked openai client |
| `tests/unit/test_cognee_extraction.py` (new) | prompt formatting, JSON parse of LLM response |
| `tests/unit/test_cognee_graph.py` (new) | Kùzu node/edge creation, traversal, prune |

## Data flow

```
cognee.add("auth decision: use JWT")
  ├── chunk text → single chunk (no chunker yet — YAGNI)
  ├── extract via openai SDK (MiniMax via base_url)
  │     response JSON → entities [{name, type}], relations [{source, target, type}]
  ├── write Entity nodes + RELATES_TO edges to Kùzu
  ├── write Document node + CONTAINS edges to Kùzu
  ├── mark Document.processed = True
  └── return Document.id

MemoryBackend.store(entry) called elsewhere
  ├── existing tier writes (qdrant best-effort, redis best-effort, postgres critical)
  └── if self.cognee: cognee.add(entry.content, metadata=entry.metadata) best-effort

cognee.search("what did we decide about auth?")
  ├── vector search via self.memory.search(query, top_k=top_k)
  ├── for each entry: find entities via CONTAINS → traverse RELATES_TO 2 hops
  └── return enriched list (vector entry + neighbor entities)
```

## Error handling

- Kùzu unavailable: `add()` still stores to `MemoryBackend` via the
  outer wrapper (degrades to tier-1-only). `search()` returns vector
  results without graph enrichment.
- LLM (openai SDK) unavailable: `add()` stores raw content via
  `MemoryBackend.store()` without entity extraction. `cognify()`
  skips unprocessed entries.
- `improve()` is best-effort. Failures logged, not raised.

## Testing

| Test file | Coverage |
|---|---|
| `test_cognee_pipeline.py` | Pipeline stages: `add`/`cognify`/`search`/`improve` (mocked Kùzu `Database` + mocked openai `AsyncOpenAI`) |
| `test_cognee_extraction.py` | `EXTRACTION_PROMPT` formatting, JSON parse of LLM response, fallback to empty lists on malformed JSON |
| `test_cognee_graph.py` | Kùzu operations: create Entity/Document nodes, RELATES_TO/CONTAINS edges, 2-hop traversal, `improve()` prune and dedupe |

All unit tests are mocked — no live Kùzu database or openai API
calls. Coverage target ≥ 80% on `cognee_store.py` after the rewrite.

## Dependencies

New:
```
kuzu>=0.4
```

Already present:
- `openai>=1.0` (added in commit `7be68b06`)
- `pydantic-settings`, `structlog` (used for logging)

## Implementation order

1. Add `kuzu>=0.4` to `pyproject.toml` dependencies.
2. Rewrite `tier1/memory/cognee_store.py` per spec (drop `import
   cognee`, add Kùzu + openai SDK, preserve public surface).
3. Add `cognee` parameter to `MemoryBackend.__init__`; call
   `cognee.add()` from `store()` after existing tier writes.
4. Write `tests/unit/test_cognee_pipeline.py`,
   `tests/unit/test_cognee_extraction.py`,
   `tests/unit/test_cognee_graph.py` — all mocked.
5. Run full suite, verify coverage on `cognee_store.py` ≥ 80% and
   existing tests still pass.
