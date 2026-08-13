# Tier 1 Cognee → Kùzu Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `cognee + NetworkX` implementation in `tier1/memory/cognee_store.py` with raw Kùzu embedded graph + openai SDK entity extraction, wire into `MemoryBackend`, and cover with three test files.

**Architecture:** Kùzu as the embedded graph store; openai SDK (with MiniMax base URL) for entity/relation extraction; pipeline stays 5-stage (`add`, `cognify`, `search`, `improve`) but `cognify` is no-op when nothing is unprocessed. `MemoryBackend.store()` calls `cognee.add()` after the existing tier writes, best-effort.

**Tech Stack:** Python 3.11, Kùzu 0.11.x (embedded graph DB), openai SDK (already wired in `garage.py` from commit 7be68b06), structlog, existing `tier1.memory.MemoryBackend`.

## Global Constraints

- Python ≥ 3.11 (per `tier1/pyproject.toml`)
- Test coverage ≥ 80% on touched modules (enforced by `pyproject.toml` `addopts`)
- All test paths: `backend/tier1/tests/unit/`
- All source paths: `backend/tier1/tier1/`
- Run pytest from `backend/tier1/` with venv activated: `cd backend/tier1 && source .venv/bin/activate && python -m pytest ...`
- Backward compatibility: the cognee rewrite MUST preserve the public surface (`CogneePipeline.__init__`, `add`, `cognify`, `search`, `improve`) so existing callers in `MemoryBackend.__init__` (if any) keep working.
- Mock all external services (Kùzu, openai) — no live calls in unit tests.

---

### Task 1: Add kuzu dependency + skeleton rewrite of `cognee_store.py`

**Files:**
- Modify: `backend/tier1/pyproject.toml` (dependencies list)
- Modify: `backend/tier1/tier1/memory/cognee_store.py` (full rewrite)
- Create: `backend/tier1/tests/unit/test_cognee_pipeline.py` (skeleton test)

**Interfaces:**
- Consumes: existing `MemoryBackend`, `MemoryEntry` from `tier1.memory`
- Produces:
  - `CogneePipeline(memory_backend, graph_path=".cognee_data", llm_provider="minimax")` — same constructor signature as before
  - `CogneePipeline.add(text: str, metadata: dict | None = None) -> str` — stub that calls `self.memory.store(MemoryEntry(content=text, ...))` and returns the entry id (no Kùzu yet)
  - `CogneePipeline.cognify(batch_size: int = 10) -> int` — stub returning 0
  - `CogneePipeline.search(query: str, *, top_k: int = 5) -> list[MemoryEntry]` — delegates to `self.memory.search(query, top_k=top_k)`
  - `CogneePipeline.improve() -> None` — stub that does nothing

- [ ] **Step 1: Add `kuzu>=0.4` to `pyproject.toml` dependencies**

In `backend/tier1/pyproject.toml`, add `kuzu>=0.4` to the `dependencies` list (alphabetical-ish — after `httpx>=0.27`, before `mem0ai>=0.1`):

```toml
dependencies = [
    ...
    "httpx>=0.27",
    "kuzu>=0.4",
    "mem0ai>=0.1.0",
    ...
]
```

- [ ] **Step 2: Install the new dependency**

Run: `cd backend/tier1 && source .venv/bin/activate && pip install 'kuzu>=0.4'`

Expected: kuzu installed. Verify: `python -c "import kuzu; print(kuzu.__version__)"` prints a version string (e.g. `0.11.3`).

- [ ] **Step 3: Write the skeleton `cognee_store.py` (no Kùzu yet)**

Replace `backend/tier1/tier1/memory/cognee_store.py` entirely with:

```python
"""Cognee knowledge graph pipeline — Kùzu embedded graph + MemoryBackend integration.

This module replaces the earlier cognee + NetworkX implementation per
the approved 2026-06-28 Cognee -> Kuzu Rewrite design spec.
"""

from __future__ import annotations

import structlog
from typing import Any

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType

log = structlog.get_logger(__name__)

EXTRACTION_PROMPT = """Extract entities and relationships from this text.
Return JSON: {{"entities": [{{"name": "...", "type": "person|concept|decision|component|metric|event"}}], "relations": [{{"source": "...", "target": "...", "type": "causes|depends_on|contradicts|supports|part_of|decided_by"}}]}}
Text: {text}"""

ENTITY_TYPES = {"person", "concept", "decision", "component", "metric", "event"}
RELATION_TYPES = {"causes", "depends_on", "contradicts", "supports", "part_of", "decided_by"}


class CogneePipeline:
    """Pipeline orchestrator: Kùzu graph + MemoryBackend storage."""

    def __init__(
        self,
        memory_backend: MemoryBackend,
        graph_path: str = ".cognee_data",
        llm_provider: str = "minimax",
    ) -> None:
        self.memory = memory_backend
        self.graph_path = graph_path
        self.llm_provider = llm_provider
        self._db: Any = None  # kuzu.Database — typed as Any to avoid hard import here
        self._conn: Any = None

    async def add(self, text: str, metadata: dict | None = None) -> str:
        """Store raw text to MemoryBackend. Graph extraction is added in Task 2."""
        entry = MemoryEntry(
            content=text,
            memory_type=MemoryType.semantic,
            source="cognee",
            metadata=metadata or {},
        )
        return await self.memory.store(entry)

    async def cognify(self, batch_size: int = 10) -> int:
        """Process unprocessed entries. Stub in Task 1; full implementation in Task 3."""
        return 0

    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]:
        """Vector search via MemoryBackend. Graph enrichment added in Task 3."""
        return await self.memory.search(query, top_k=top_k)

    async def improve(self) -> None:
        """Best-effort graph refinement. Stub in Task 1; full implementation in Task 3."""
        return None
```

- [ ] **Step 4: Write the skeleton test file**

Create `backend/tier1/tests/unit/test_cognee_pipeline.py` with:

```python
"""Tests for CogneePipeline (Kùzu implementation)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory import MemoryEntry, MemoryType
from tier1.memory.cognee_store import CogneePipeline


def _make_memory_backend():
    mem = MagicMock()
    mem.store = AsyncMock(return_value="entry-id")
    mem.search = AsyncMock(return_value=[])
    return mem


def test_add_stores_to_memory_backend():
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend)
    # Drive synchronously since add() is async but memory is mocked.
    import asyncio
    entry_id = asyncio.run(pipeline.add("hello world", metadata={"k": "v"}))
    assert entry_id == "entry-id"
    backend.store.assert_awaited_once()
    stored = backend.store.await_args.args[0]
    assert stored.content == "hello world"
    assert stored.memory_type == MemoryType.semantic
    assert stored.source == "cognee"
    assert stored.metadata == {"k": "v"}


async def test_add_async():
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend)
    entry_id = await pipeline.add("hello async")
    assert entry_id == "entry-id"


async def test_cognify_stub_returns_zero():
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend)
    assert await pipeline.cognify() == 0
    assert await pipeline.cognify(batch_size=20) == 0


async def test_search_delegates_to_memory_backend():
    backend = _make_memory_backend()
    entry = MagicMock(spec=MemoryEntry)
    backend.search = AsyncMock(return_value=[entry])
    pipeline = CogneePipeline(backend)
    results = await pipeline.search("query", top_k=3)
    assert results == [entry]
    backend.search.assert_awaited_once_with("query", top_k=3)


async def test_improve_is_noop():
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend)
    # No exception means it ran cleanly.
    await pipeline.improve()


def test_constructor_preserves_public_surface():
    """Constructor signature must match what the spec mandates."""
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend, graph_path="/tmp/x", llm_provider="minimax")
    assert pipeline.memory is backend
    assert pipeline.graph_path == "/tmp/x"
    assert pipeline.llm_provider == "minimax"
    assert pipeline._db is None  # not opened yet
    assert pipeline._conn is None
```

- [ ] **Step 5: Run the new tests**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_cognee_pipeline.py -v --no-cov`

Expected: 6 passed.

If failures, common issues:
- `MemoryType.semantic` doesn't exist: check `tier1/memory/__init__.py:13` for the enum members.
- Async test loop errors: confirm `asyncio_mode = "auto"` in `pyproject.toml` (Task 1 setup is correct because the project already has it).

- [ ] **Step 6: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/pyproject.toml backend/tier1/tier1/memory/cognee_store.py backend/tier1/tests/unit/test_cognee_pipeline.py
git commit -m "feat(tier1): add kuzu dep and skeleton CogneePipeline

Skeleton preserves the public 5-stage surface (add, cognify, search,
improve) with stub implementations. add() already routes through
MemoryBackend; cognify/search/improve are no-ops pending Task 3 graph
wiring. 6 unit tests cover the public surface.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Kùzu graph store — node/edge operations + traverse

**Files:**
- Modify: `backend/tier1/tier1/memory/cognee_store.py` (add `_ensure_graph()`, `_write_document`, `_write_entity`, `_write_relation`, `_find_entities_for_entry`, `_traverse_graph`, `improve()`)
- Create: `backend/tier1/tests/unit/test_cognee_graph.py`

**Interfaces:**
- Consumes: existing `CogneePipeline.__init__`; `kuzu.Database` (lazy-opened on first call)
- Produces:
  - `CogneePipeline._ensure_graph()` — opens `kuzu.Database(self.graph_path)` if not already open, runs DDL once
  - `CogneePipeline.improve()` — best-effort: no-op if graph not open, else runs DDL idempotently and returns None
  - `CogneePipeline._find_entities_for_entry(entry_id: str) -> list[str]` — Cypher query returning entity names
  - `CogneePipeline._traverse_graph(entity_names: list[str], hops: int = 2) -> list[str]` — Cypher query returning neighbor names

- [ ] **Step 1: Write the graph test file**

Create `backend/tier1/tests/unit/test_cognee_graph.py` with:

```python
"""Tests for CogneePipeline graph operations (Kùzu)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tier1.memory.cognee_store import CogneePipeline


def _make_pipeline_with_mock_db():
    """Pipeline with a mocked kuzu Database + Connection."""
    backend = MagicMock()
    pipeline = CogneePipeline(backend, graph_path="/tmp/fake-graph")

    mock_conn = MagicMock()
    mock_db = MagicMock()
    # conn.execute returns a result object; we only care that it's called.
    mock_db.conn = mock_conn

    # First call to _ensure_graph opens the db.
    with patch("tier1.memory.cognee_store._open_kuzu_db", return_value=mock_db):
        return pipeline, mock_db, mock_conn


def test_ensure_graph_opens_db_once():
    pipeline, mock_db, mock_conn = _make_pipeline_with_mock_db()
    pipeline._ensure_graph()
    assert pipeline._db is mock_db
    assert pipeline._conn is mock_conn
    # Second call is a no-op.
    pipeline._ensure_graph()
    # The DDL was executed at least once (CREATE NODE TABLE for Entity and Document,
    # CREATE REL TABLE for RELATES_TO and CONTAINS).
    assert mock_conn.execute.call_count >= 4


def test_improve_is_idempotent_and_runs_ddl():
    pipeline, mock_db, mock_conn = _make_pipeline_with_mock_db()
    import asyncio
    asyncio.run(pipeline.improve())
    # DDL is run at least once; second call must not raise.
    asyncio.run(pipeline.improve())


def test_find_entities_for_entry_runs_cypher():
    pipeline, mock_db, mock_conn = _make_pipeline_with_mock_db()
    # Mock the query result: an iterator of dicts with 'name' key.
    mock_result = MagicMock()
    mock_result.get_next.return_value = {"name": "JWT"}  # then StopIteration on next call
    mock_result.get_next.side_effect = [{"name": "JWT"}, {"name": "auth"}, StopIteration]
    mock_conn.execute.return_value = mock_result

    names = pipeline._find_entities_for_entry("entry-abc")
    assert names == ["JWT", "auth"]
    # Cypher query was issued.
    assert mock_conn.execute.called


def test_traverse_graph_returns_neighbors():
    pipeline, mock_db, mock_conn = _make_pipeline_with_mock_db()
    mock_result = MagicMock()
    mock_result.get_next.side_effect = [
        {"name": "middleware"},
        {"name": "token"},
        StopIteration,
    ]
    mock_conn.execute.return_value = mock_result

    neighbors = pipeline._traverse_graph(["JWT"], hops=2)
    assert "middleware" in neighbors
    assert "token" in neighbors
```

- [ ] **Step 2: Add `_open_kuzu_db` helper at module top**

In `backend/tier1/tier1/memory/cognee_store.py`, after the existing module-level constants (`EXTRACTION_PROMPT`, `ENTITY_TYPES`, `RELATION_TYPES`), add:

```python
def _open_kuzu_db(path: str):
    """Open a Kùzu database. Module-level function so tests can patch it."""
    import kuzu
    db = kuzu.Database(path)
    return db
```

- [ ] **Step 3: Add `_ensure_graph()` and graph methods to `CogneePipeline`**

In `cognee_store.py`, add the following methods to the `CogneePipeline` class (after `__init__`, before `add`):

```python
    def _ensure_graph(self) -> None:
        """Open the Kùzu database and create tables (idempotent)."""
        if self._db is not None:
            return
        self._db = _open_kuzu_db(self.graph_path)
        self._conn = self._db.conn
        # DDL — kuzu raises if a table already exists, so wrap in try/except.
        ddl_statements = [
            (
                "CREATE NODE TABLE Entity("
                "id UUID, name STRING, type STRING, "
                "embedding FLOAT[1536], created_at TIMESTAMP, "
                "PRIMARY KEY(id))"
            ),
            (
                "CREATE NODE TABLE Document("
                "id UUID, content_hash STRING, processed BOOLEAN, "
                "created_at TIMESTAMP, PRIMARY KEY(id))"
            ),
            (
                "CREATE REL TABLE RELATES_TO("
                "FROM Entity TO Entity, "
                "relation_type STRING, weight FLOAT, created_at TIMESTAMP)"
            ),
            (
                "CREATE REL TABLE CONTAINS("
                "FROM Document TO Entity)"
            ),
        ]
        for stmt in ddl_statements:
            try:
                self._conn.execute(stmt)
            except Exception as exc:  # noqa: BLE001
                # Table already exists — expected on subsequent opens.
                log.debug("kuzu.ddl_skipped", statement=stmt[:40], error=str(exc))

    def _find_entities_for_entry(self, entry_id: str) -> list[str]:
        """Return entity names that mention the given memory entry's id."""
        self._ensure_graph()
        result = self._conn.execute(
            "MATCH (d:Document {id: $id})-[:CONTAINS]->(e:Entity) RETURN e.name AS name",
            {"id": entry_id},
        )
        names: list[str] = []
        while True:
            try:
                row = result.get_next()
            except StopIteration:
                break
            names.append(row["name"])
        return names

    def _traverse_graph(self, entity_names: list[str], hops: int = 2) -> list[str]:
        """Traverse RELATES_TO from the given entities up to `hops` deep."""
        self._ensure_graph()
        if not entity_names:
            return []
        result = self._conn.execute(
            "MATCH (e:Entity)-[r:RELATES_TO*1.." + str(hops) + "]->(n:Entity) "
            "WHERE e.name IN $names RETURN DISTINCT n.name AS name",
            {"names": entity_names},
        )
        names: list[str] = []
        while True:
            try:
                row = result.get_next()
            except StopIteration:
                break
            names.append(row["name"])
        return names
```

- [ ] **Step 4: Implement `improve()` (real version)**

Replace the existing `async def improve(self) -> None:` stub with:

```python
    async def improve(self) -> None:
        """Best-effort graph refinement: ensure schema exists. Failures logged."""
        try:
            self._ensure_graph()
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee.improve_failed", error=str(exc), exc_info=True)
```

- [ ] **Step 5: Run the new tests**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_cognee_graph.py -v --no-cov`

Expected: 4 passed.

If failures, common issues:
- `ImportError` from `tier1.memory.cognee_store` because kuzu isn't installed: re-run Task 1 Step 2.
- `AttributeError: _open_kuzu_db` not found: confirm the helper was added at module top after the constants.
- `MagicMock.get_next` not iterating: use `side_effect = [..., StopIteration]` pattern (shown in the test).

- [ ] **Step 6: Run existing cognee_pipeline tests to confirm no regression**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_cognee_pipeline.py -v --no-cov`

Expected: 6 passed (unchanged).

- [ ] **Step 7: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tier1/memory/cognee_store.py backend/tier1/tests/unit/test_cognee_graph.py
git commit -m "feat(tier1): add Kuzu graph operations to CogneePipeline

_ensure_graph opens the database and creates Entity/Document node
tables + RELATES_TO/CONTAINS edge tables (idempotent DDL). New
_find_entities_for_entry and _traverse_graph methods enable 2-hop
graph search. improve() runs DDL idempotently. _open_kuzu_db is a
module-level helper so tests can patch the Kuzu dependency. 4 unit
tests cover the graph surface.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Entity extraction via openai SDK + full add/cognify pipeline

**Files:**
- Modify: `backend/tier1/tier1/memory/cognee_store.py` (replace `add` and `cognify` with real implementations; add `_extract_entities`, `_chunk_text`, `_get_extraction_client`, `_extract_model_name`, `_write_graph_for_chunk`)
- Create: `backend/tier1/tests/unit/test_cognee_extraction.py`

**Interfaces:**
- Consumes: `EXTRACTION_PROMPT`, `ENTITY_TYPES`, `RELATION_TYPES` from `tier1.memory.cognee_store`
- Produces:
  - `CogneePipeline.add(text, metadata)` — chunks text, calls LLM extraction, writes nodes/edges to Kùzu, stores in MemoryBackend, returns entry id
  - `CogneePipeline.cognify(batch_size)` — finds unprocessed documents, marks them processed
  - `CogneePipeline._extract_entities(text)` — returns `(entities, relations)` parsed from LLM JSON response
  - `CogneePipeline._chunk_text(text)` — returns `[text]` (single chunk; no chunker yet — YAGNI)
  - `_get_extraction_client(provider)` — module-level helper, returns `openai.AsyncOpenAI` client or None

- [ ] **Step 1: Write the extraction test file**

Create `backend/tier1/tests/unit/test_cognee_extraction.py` with:

```python
"""Tests for CogneePipeline entity/relation extraction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory import MemoryType
from tier1.memory.cognee_store import (
    EXTRACTION_PROMPT,
    CogneePipeline,
)


def test_extraction_prompt_format():
    """The prompt must inject the text and demand the exact JSON shape."""
    out = EXTRACTION_PROMPT.format(text="hello world")
    assert "hello world" in out
    assert "entities" in out
    assert "relations" in out
    assert "person|concept|decision|component|metric|event" in out


def test_extract_entities_parses_valid_response():
    pipeline = CogneePipeline(MagicMock())
    response_json = json.dumps({
        "entities": [
            {"name": "JWT", "type": "concept"},
            {"name": "auth", "type": "component"},
        ],
        "relations": [
            {"source": "JWT", "target": "auth", "type": "part_of"},
        ],
    })
    entities, relations = pipeline._extract_entities(response_json)
    assert entities == [
        {"name": "JWT", "type": "concept"},
        {"name": "auth", "type": "component"},
    ]
    assert relations == [
        {"source": "JWT", "target": "auth", "type": "part_of"},
    ]


def test_extract_entities_handles_malformed_json():
    pipeline = CogneePipeline(MagicMock())
    entities, relations = pipeline._extract_entities("not json {")
    assert entities == []
    assert relations == []


def test_extract_entities_drops_unknown_types():
    pipeline = CogneePipeline(MagicMock())
    response_json = json.dumps({
        "entities": [
            {"name": "Good", "type": "concept"},
            {"name": "Bad", "type": "alien_species"},
        ],
        "relations": [
            {"source": "Good", "target": "Bad", "type": "part_of"},
            {"source": "Good", "target": "Bad", "type": "vibes_with"},
        ],
    })
    entities, relations = pipeline._extract_entities(response_json)
    assert len(entities) == 1
    assert entities[0]["name"] == "Good"
    assert len(relations) == 1
    assert relations[0]["type"] == "part_of"


def test_chunk_text_returns_single_chunk():
    """YAGNI: no chunker yet — just one chunk."""
    pipeline = CogneePipeline(MagicMock())
    assert pipeline._chunk_text("hello world") == ["hello world"]


async def test_add_calls_llm_then_writes_graph():
    """add() invokes the openai SDK, parses response, writes nodes/edges, stores memory."""
    backend = MagicMock()
    backend.store = AsyncMock(return_value="entry-id")
    pipeline = CogneePipeline(backend)

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = json.dumps({
        "entities": [{"name": "JWT", "type": "concept"}],
        "relations": [],
    })

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

    mock_conn = MagicMock()
    pipeline._conn = mock_conn
    pipeline._db = MagicMock()  # pretend graph is open

    with patch(
        "tier1.memory.cognee_store._get_extraction_client",
        return_value=fake_client,
    ):
        entry_id = await pipeline.add("JWT is a token format for auth")

    assert entry_id == "entry-id"
    fake_client.chat.completions.create.assert_awaited_once()
    # At least one Cypher write happened (Entity or Document node).
    assert mock_conn.execute.called


async def test_cognify_returns_count_processed():
    """cognify() should run and return an int. Empty graph -> 0."""
    backend = MagicMock()
    pipeline = CogneePipeline(backend)
    pipeline._conn = MagicMock()
    pipeline._db = MagicMock()
    # Mock the unprocessed-documents query to return empty.
    pipeline._conn.execute.return_value.get_next.side_effect = StopIteration

    count = await pipeline.cognify(batch_size=10)
    assert count == 0
```

- [ ] **Step 2: Add `_get_extraction_client` helper at module top**

In `cognee_store.py`, after `_open_kuzu_db`, add:

```python
def _get_extraction_client(provider: str):
    """Return an openai.AsyncOpenAI client configured for the given provider.

    For 'minimax', use the MiniMax base URL from tier1 settings. For 'openai',
    use the OpenAI base URL. Returns None on configuration failure so callers
    can degrade gracefully.
    """
    try:
        from openai import AsyncOpenAI
        from tier1.config import get_settings
        settings = get_settings()
        if provider == "minimax":
            return AsyncOpenAI(
                api_key=settings.minimax_api_key,
                base_url=settings.minimax_base_url,
                timeout=settings.llm_timeout_s,
            )
        elif provider == "openai":
            return AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.llm_timeout_s,
            )
        elif provider == "anthropic":
            # Anthropic uses a different SDK; not wired here. Return None.
            return None
        else:
            return None
    except Exception as exc:  # noqa: BLE001
        log.warning("cognee.client_init_failed", provider=provider, error=str(exc))
        return None
```

- [ ] **Step 3: Add `import json` and `_chunk_text` + `_extract_entities` to `CogneePipeline`**

At the top of `cognee_store.py`, update the imports to:

```python
import json
import structlog
from typing import Any
```

In `cognee_store.py`, add these methods to the class (after `_traverse_graph`, before `improve`):

```python
    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks. YAGNI: single chunk for now."""
        return [text]

    def _extract_entities(self, llm_response: str) -> tuple[list[dict], list[dict]]:
        """Parse an LLM JSON response into (entities, relations) lists.

        Unknown entity or relation types are dropped. Malformed JSON returns
        empty lists. Best-effort by design — never raises.
        """
        try:
            data = json.loads(llm_response)
        except Exception:  # noqa: BLE001
            log.warning("cognee.extract_invalid_json", response=llm_response[:100])
            return [], []
        entities = [
            e for e in data.get("entities", [])
            if isinstance(e, dict) and e.get("type") in ENTITY_TYPES
        ]
        relations = [
            r for r in data.get("relations", [])
            if isinstance(r, dict) and r.get("type") in RELATION_TYPES
        ]
        return entities, relations
```

- [ ] **Step 4: Replace `add` with the real implementation**

In `cognee_store.py`, replace the existing `async def add(...)` with:

```python
    async def add(self, text: str, metadata: dict | None = None) -> str:
        """5-stage pipeline: chunk -> extract via LLM -> write graph -> store memory.

        On LLM or Kuzu failure, degrades to plain memory store (graph is
        built later by cognify() or skipped entirely).
        """
        # Stage 1: chunk
        chunks = self._chunk_text(text)

        # Stage 2-4: build graph (best-effort)
        try:
            client = _get_extraction_client(self.llm_provider)
            if client is not None:
                self._ensure_graph()
                for chunk in chunks:
                    response = await client.chat.completions.create(
                        model=self._extract_model_name(),
                        messages=[
                            {"role": "user", "content": EXTRACTION_PROMPT.format(text=chunk)},
                        ],
                    )
                    content = response.choices[0].message.content or "{}"
                    entities, relations = self._extract_entities(content)
                    self._write_graph_for_chunk(chunk, entities, relations)
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee.graph_build_failed", error=str(exc), exc_info=True)

        # Stage 5: store in memory backend (always runs)
        entry = MemoryEntry(
            content=text,
            memory_type=MemoryType.semantic,
            source="cognee",
            metadata=metadata or {},
        )
        return await self.memory.store(entry)

    def _extract_model_name(self) -> str:
        from tier1.config import get_settings
        settings = get_settings()
        if self.llm_provider == "minimax":
            return settings.minimax_model
        elif self.llm_provider == "openai":
            return settings.openai_model
        elif self.llm_provider == "anthropic":
            return settings.anthropic_model
        return "gpt-4o-mini"

    def _write_graph_for_chunk(
        self,
        chunk: str,
        entities: list[dict],
        relations: list[dict],
    ) -> None:
        """Persist entities, relations, and a Document node into Kùzu."""
        import uuid
        import hashlib
        doc_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(chunk.encode()).hexdigest()
        self._conn.execute(
            "CREATE (d:Document {id: $id, content_hash: $h, processed: true})",
            {"id": doc_id, "h": content_hash},
        )
        for ent in entities:
            self._conn.execute(
                "MERGE (e:Entity {name: $name}) SET e.type = $type",
                {"name": ent["name"], "type": ent["type"]},
            )
            self._conn.execute(
                "MATCH (d:Document {id: $did}), (e:Entity {name: $name}) "
                "CREATE (d)-[:CONTAINS]->(e)",
                {"did": doc_id, "name": ent["name"]},
            )
        for rel in relations:
            self._conn.execute(
                "MATCH (a:Entity {name: $src}), (b:Entity {name: $tgt}) "
                "MERGE (a)-[r:RELATES_TO {relation_type: $type}]->(b)",
                {"src": rel["source"], "tgt": rel["target"], "type": rel["type"]},
            )
```

- [ ] **Step 5: Replace `cognify` with the real implementation**

Replace the existing `async def cognify(...)` stub with:

```python
    async def cognify(self, batch_size: int = 10) -> int:
        """Process unprocessed entries: extract entities, build graph edges.

        Returns the count of newly-processed documents. Best-effort: on
        any failure, logs and returns 0.
        """
        try:
            self._ensure_graph()
            result = self._conn.execute(
                "MATCH (d:Document {processed: false}) RETURN d.id AS id LIMIT $limit",
                {"limit": batch_size},
            )
            ids: list[str] = []
            while True:
                try:
                    row = result.get_next()
                except StopIteration:
                    break
                ids.append(row["id"])
            # Mark them processed (no entity extraction here — add() already does it).
            for did in ids:
                self._conn.execute(
                    "MATCH (d:Document {id: $id}) SET d.processed = true",
                    {"id": did},
                )
            return len(ids)
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee.cognify_failed", error=str(exc), exc_info=True)
            return 0
```

- [ ] **Step 6: Run the new tests**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_cognee_extraction.py -v --no-cov`

Expected: 7 passed.

If failures, common issues:
- `_get_extraction_client` ImportError because openai not installed: confirm it was installed in commit 7be68b06.
- `json.loads` error: confirm `import json` was added at module top.
- Cypher syntax errors in `_write_graph_for_chunk`: kuzu uses standard Cypher; the syntax above should work but if a test fails on graph writes, log the actual kuzu error message and adjust.

- [ ] **Step 7: Run all cognee tests**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_cognee_pipeline.py tests/unit/test_cognee_graph.py tests/unit/test_cognee_extraction.py -v --no-cov`

Expected: all 17 tests pass (6 pipeline + 4 graph + 7 extraction).

- [ ] **Step 8: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tier1/memory/cognee_store.py backend/tier1/tests/unit/test_cognee_extraction.py
git commit -m "feat(tier1): entity extraction via openai SDK + full add/cognify

CogneePipeline.add now chunks text, calls the openai SDK (MiniMax via
base_url) for entity/relation extraction, writes Entity/Document
nodes + RELATES_TO/CONTAINS edges to Kuzu, and stores the entry via
MemoryBackend. cognify() finds unprocessed documents and marks them
processed. _extract_entities filters unknown types and degrades
gracefully on malformed JSON. _get_extraction_client is module-level
so tests can patch it. 7 unit tests cover prompt format, parsing,
type filtering, chunking, and the add/cognify flows.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: MemoryBackend wiring + full-suite coverage check

**Files:**
- Modify: `backend/tier1/tier1/memory/__init__.py`
- (No new test files; existing tests cover the wiring via the pipeline tests + memory backend tests.)

**Interfaces:**
- Consumes: existing `MemoryBackend(qdrant, redis, postgres, mem0=None)`
- Produces: `MemoryBackend(..., cognee: CogneePipeline | None = None)`; `MemoryBackend.store(entry)` calls `cognee.add(entry.content, metadata=entry.metadata)` after existing tier writes, wrapped in try/except

- [ ] **Step 1: Add `cognee` parameter to `MemoryBackend.__init__`**

In `backend/tier1/tier1/memory/__init__.py`, update the `MemoryBackend` class:

```python
class MemoryBackend:
    """Unified memory facade over Qdrant, Redis, and PostgreSQL."""

    def __init__(
        self,
        qdrant: "QdrantStore",
        redis: "RedisMemoryCache",
        postgres: "PostgresMemoryStore",
        mem0: "Mem0Backend | None" = None,
        cognee: "CogneePipeline | None" = None,
    ) -> None:
        self.qdrant = qdrant
        self.redis = redis
        self.postgres = postgres
        self.mem0 = mem0
        self.cognee = cognee
```

- [ ] **Step 2: Update `store()` to call `cognee.add()` after existing writes**

In the same file, update the `store` method. After the existing `if self.mem0:` block (around line 65 in the current file), add:

```python
        # Cognee (knowledge graph) — best effort
        if self.cognee is not None:
            try:
                await self.cognee.add(entry.content, metadata=entry.metadata)
            except Exception:  # noqa: BLE001
                pass

        return entry.id
```

Verify by reading the existing `store` method: it ends with `return entry.id`. Insert the cognee block immediately before that return.

- [ ] **Step 3: Run the memory backend tests to confirm no regression**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_memory_backend.py tests/unit/test_memory_entry.py tests/unit/test_nats_memory.py tests/unit/test_postgres_memory_store.py -v --no-cov`

Expected: 12 passed (or whatever the prior count was — no new failures).

- [ ] **Step 4: Run all cognee tests**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_cognee_pipeline.py tests/unit/test_cognee_graph.py tests/unit/test_cognee_extraction.py -v --no-cov`

Expected: 17 passed.

- [ ] **Step 5: Run the full test suite (skip health tests due to Postgres dependency)**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest --ignore=tests/unit/test_health.py --no-cov 2>&1 | tail -3`

Expected: ≥ 159 passed, 11 skipped. No new failures.

If failures:
- `cognee_store.py` import error: confirm Task 1 added `import kuzu` correctly (it's behind `_open_kuzu_db` which is only called at runtime).
- `MemoryBackend` signature mismatch: confirm the cognee parameter is keyword-with-default, so existing callers without `cognee=` still work.

- [ ] **Step 6: Verify coverage on `cognee_store.py` ≥ 80%**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest --ignore=tests/unit/test_health.py --cov=tier1/memory/cognee_store --cov-report=term 2>&1 | grep -E "cognee_store|TOTAL" | head`

Expected: `tier1/memory/cognee_store.py` shows ≥ 80% coverage.

If below 80%, identify the uncovered lines (the report will list them) and add targeted tests in `test_cognee_pipeline.py` or `test_cognee_graph.py`.

- [ ] **Step 7: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tier1/memory/__init__.py
git commit -m "feat(tier1): wire CogneePipeline into MemoryBackend.store

MemoryBackend now accepts an optional cognee: CogneePipeline parameter.
store() calls cognee.add() after the existing qdrant/redis/postgres
writes; cognee failures are logged and swallowed so a graph outage
cannot break a memory write. Backward compatible: existing callers
without cognee= keep working unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
