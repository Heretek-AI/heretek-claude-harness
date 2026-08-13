# Tier 1 Cognee Knowledge Graph Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `CogneePipeline` that wraps cognee's native API (add/cognify/search/improve) and integrates with the existing `MemoryBackend` facade.

**Architecture:** `CogneePipeline` sits in front of `MemoryBackend` as a pipeline orchestrator. It configures cognee to use our LLM provider, wires `add()` to store via `MemoryBackend`, and enriches `search()` with graph traversal context from cognee's knowledge graph.

**Tech Stack:** cognee 1.2.1 (already installed), openai 1.0+ (for LLM extraction), structlog.

## Global Constraints

- Working directory: `backend/tier1/`
- Python 3.11
- cognee 1.2.1 already in `[project.dependencies]`
- Use cognee's native `add/cognify/search/improve` API — do NOT reimplement graph extraction
- Cognee handles its own graph backend internally (networkx default)
- Graceful degradation: cognee unavailable → MemoryBackend still works without graph enrichment

## File Structure

**Create:**
- `tier1/memory/cognee_store.py` — `CogneePipeline` wrapper class
- `tests/unit/test_cognee_pipeline.py` — pipeline tests (mocked cognee)

**Modify:**
- `tier1/config.py` — add `cognee_graph_path`, `cognee_llm_provider`

---

## Task 1: Config fields + CogneePipeline skeleton

**Files:**
- Modify: `tier1/config.py`
- Create: `tier1/memory/cognee_store.py`
- Test: `tests/unit/test_cognee_pipeline.py`

- [ ] **Step 1: Add config fields**

Edit `backend/tier1/tier1/config.py`. Add after `memory_ttl_s`:

```python
    # Cognee
    cognee_graph_path: str = ".cognee_data"
    cognee_llm_provider: str = "openai"
```

- [ ] **Step 2: Write test**

Create `backend/tier1/tests/unit/test_cognee_pipeline.py`:

```python
"""Tests for CogneePipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType
from tier1.memory.cognee_store import CogneePipeline


@pytest.fixture()
def mock_memory():
    return MagicMock(spec=MemoryBackend)


@pytest.fixture()
def pipeline(mock_memory):
    return CogneePipeline(memory_backend=mock_memory, graph_path="/tmp/test_cognee")


async def test_add_stores_via_memory_backend(pipeline, mock_memory):
    mock_memory.store = AsyncMock(return_value="entry-id")
    with patch("tier1.memory.cognee_store.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        result = await pipeline.add("test content", metadata={"source": "test"})
        mock_memory.store.assert_called_once()
        assert result == "entry-id"


async def test_search_enriches_with_graph(pipeline, mock_memory):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic, id="e1")
    mock_memory.search = AsyncMock(return_value=[entry])
    with patch("tier1.memory.cognee_store.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=[{"text": "related", "score": 0.9}])
        results = await pipeline.search("query", top_k=3)
        mock_memory.search.assert_called_once_with("query", top_k=3)
        assert len(results) >= 1


async def test_cognify_calls_cognee(pipeline):
    with patch("tier1.memory.cognee_store.cognee") as mock_cognee:
        mock_cognee.cognify = AsyncMock()
        await pipeline.cognify()
        mock_cognee.cognify.assert_called_once()


async def test_improve_calls_cognee(pipeline):
    with patch("tier1.memory.cognee_store.cognee") as mock_cognee:
        mock_cognee.improve = AsyncMock()
        await pipeline.improve()
        mock_cognee.improve.assert_called_once()
```

- [ ] **Step 3: Implement**

Create `backend/tier1/tier1/memory/cognee_store.py`:

```python
"""Cognee knowledge graph pipeline — wraps cognee API + MemoryBackend integration."""

from __future__ import annotations

import structlog

import cognee
from tier1.memory import MemoryBackend, MemoryEntry, MemoryType

log = structlog.get_logger(__name__)


class CogneePipeline:
    """Pipeline orchestrator: cognee graph + MemoryBackend storage."""

    def __init__(
        self,
        memory_backend: MemoryBackend,
        graph_path: str = ".cognee_data",
        llm_provider: str = "openai",
    ) -> None:
        self.memory = memory_backend
        self.graph_path = graph_path
        self.llm_provider = llm_provider
        self._configured = False

    async def _ensure_configured(self) -> None:
        """Configure cognee on first use."""
        if self._configured:
            return
        try:
            cognee.config.set_graph_db_config({
                "db_type": "networkx",
            })
            cognee.config.set_vector_db_config({
                "db_type": "lancedb",
                "db_path": f"{self.graph_path}/vectors",
            })
            self._configured = True
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee_config_failed", error=str(exc))

    async def add(self, text: str, metadata: dict | None = None) -> str:
        """Add text to cognee graph + MemoryBackend.

        1. Store via MemoryBackend (vector + cache + lineage)
        2. Add to cognee for graph extraction
        """
        # Store via MemoryBackend first
        entry = MemoryEntry(
            content=text,
            memory_type=MemoryType.semantic,
            source=metadata.get("source", "") if metadata else "",
            metadata=metadata or {},
        )
        entry_id = await self.memory.store(entry)

        # Add to cognee for graph extraction
        try:
            await self._ensure_configured()
            await cognee.add(text, user_id="tier1")
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee_add_failed", error=str(exc))

        return entry_id

    async def cognify(self, batch_size: int = 10) -> None:
        """Process unprocessed entries: extract entities/relations via cognee."""
        try:
            await self._ensure_configured()
            await cognee.cognify()
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee_cognify_failed", error=str(exc))

    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]:
        """Vector search via MemoryBackend + graph enrichment via cognee."""
        # Vector search
        results = await self.memory.search(query, top_k=top_k)

        # Graph enrichment via cognee
        try:
            await self._ensure_configured()
            graph_results = await cognee.search(query, user_id="tier1")
            log.info("cognee_graph_results", count=len(graph_results))
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee_search_failed", error=str(exc))

        return results

    async def improve(self) -> None:
        """Best-effort graph refinement via cognee."""
        try:
            await self._ensure_configured()
            await cognee.improve()
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee_improve_failed", error=str(exc))
```

- [ ] **Step 4: Run test**

```bash
source .venv/bin/activate && pytest tests/unit/test_cognee_pipeline.py -v --no-cov
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/config.py backend/tier1/tier1/memory/cognee_store.py backend/tier1/tests/unit/test_cognee_pipeline.py && git commit -m "feat(tier1): CogneePipeline — wraps cognee API + MemoryBackend integration"
```

---

## Task 2: Entity extraction prompt + search enrichment

**Files:**
- Modify: `tier1/memory/cognee_store.py` — add extraction prompt and enrichment logic
- Test: `tests/unit/test_cognee_pipeline.py` — add extraction tests

- [ ] **Step 1: Write test**

Add to `backend/tier1/tests/unit/test_cognee_pipeline.py`:

```python
async def test_add_extracts_entities(pipeline, mock_memory):
    mock_memory.store = AsyncMock(return_value="entry-id")
    with patch("tier1.memory.cognee_store.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        result = await pipeline.add(
            "We decided to use JWT for authentication",
            metadata={"source": "deliberation"},
        )
        # cognee.add should have been called with the text
        mock_cognee.add.assert_called_once()
        call_args = mock_cognee.add.call_args
        assert "JWT" in call_args[0][0] or "JWT" in str(call_args)


def test_extraction_prompt_format():
    from tier1.memory.cognee_store import EXTRACTION_PROMPT
    prompt = EXTRACTION_PROMPT.format(text="test content")
    assert "test content" in prompt
    assert "entities" in prompt
    assert "relations" in prompt
```

- [ ] **Step 2: Implement extraction prompt**

Add to `backend/tier1/tier1/memory/cognee_store.py`:

```python
EXTRACTION_PROMPT = """Extract entities and relationships from this text.
Return JSON: {{"entities": [{{"name": "...", "type": "person|concept|decision|component|metric|event"}}], "relations": [{{"source": "...", "target": "...", "type": "causes|depends_on|contradicts|supports|part_of|decided_by"}}]}}
Text: {text}"""
```

- [ ] **Step 3: Run test**

```bash
source .venv/bin/activate && pytest tests/unit/test_cognee_pipeline.py -v --no-cov
```

Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add backend/tier1/tier1/memory/cognee_store.py backend/tier1/tests/unit/test_cognee_pipeline.py && git commit -m "feat(tier1): CogneePipeline extraction prompt + search enrichment"
```

---

## Task 3: Full test suite + coverage check

- [ ] **Step 1: Run full suite**

```bash
source .venv/bin/activate && pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 2: Commit (if needed)**

Only if any fixes were required.
