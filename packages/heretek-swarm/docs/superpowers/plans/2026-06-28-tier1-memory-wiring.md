# Tier 1 Memory Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing `MemoryBackend` into the deliberation graph so each agent turn recalls past deliberations and stores its verdict, without changing default behavior.

**Architecture:** Add an optional `memory: MemoryBackend | None` parameter through `Tribunal` → node factories → `run_agent`. Inside `run_agent`, recall top-k past deliberations via `memory.search()` and inject into the user prompt before streaming; after verdict parsing, call `memory.store()` with the verdict's reasoning. Both calls are best-effort — failures are logged and swallowed.

**Tech Stack:** Python 3.11, LangGraph, structlog, existing `tier1.memory.MemoryBackend`.

## Global Constraints

- Python ≥ 3.11 (per `tier1/pyproject.toml`)
- Test coverage ≥ 80% (enforced by `pyproject.toml` `addopts`)
- All test paths: `backend/tier1/tests/unit/`
- All source paths: `backend/tier1/tier1/`
- Run pytest from `backend/tier1/` with venv activated: `cd backend/tier1 && source .venv/bin/activate && python -m pytest ...`
- Use `structlog.get_logger(__name__)` for logging in modified modules
- Backward compatibility: `memory=None` must produce identical behavior to current code

---

### Task 1: Add `memory` parameter to `run_agent` and the four node factories

**Files:**
- Modify: `backend/tier1/tier1/deliberation/nodes/_base.py:59-133`
- Modify: `backend/tier1/tier1/deliberation/nodes/alpha.py:24-27`
- Modify: `backend/tier1/tier1/deliberation/nodes/beta.py:24-25`
- Modify: `backend/tier1/tier1/deliberation/nodes/charlie.py:24-25`
- Modify: `backend/tier1/tier1/deliberation/nodes/steward.py` (find `make_steward_node` signature)

**Interfaces:**
- Consumes: existing `run_agent(state, garage, *, agent, sink)`; existing `make_*_node(garage, sink=None)` factories
- Produces:
  - `run_agent(state, garage, *, agent, sink=None, memory=None)` — new `memory` param, default `None`. **Behavior unchanged in this task.**
  - `make_alpha_node(garage, sink=None, memory=None)` (analogous for beta/charlie/steward)

- [ ] **Step 1: Add `memory=None` parameter to `run_agent` (no behavior change)**

In `backend/tier1/tier1/deliberation/nodes/_base.py`, change the `run_agent` signature from:

```python
async def run_agent(
    state: DeliberationState,
    garage: ModelGarage,
    *,
    agent: AgentName,
    sink: EventSink | None = None,
) -> DeliberationState:
```

to:

```python
async def run_agent(
    state: DeliberationState,
    garage: ModelGarage,
    *,
    agent: AgentName,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
) -> DeliberationState:
```

Add `from __future__ import annotations` if not present (it is — line 3) so the forward reference `"MemoryBackend | None"` works without importing the class yet.

- [ ] **Step 2: Update the four node factories**

In each of `alpha.py`, `beta.py`, `charlie.py`, update the `make_*_node` factory. For `alpha.py:24-27`, change:

```python
def make_alpha_node(garage: ModelGarage, sink: EventSink | None = None):
    if sink is None:
        return partial(alpha_node, garage=garage)
    return partial(alpha_node, garage=garage, sink=sink)
```

to:

```python
def make_alpha_node(
    garage: ModelGarage,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
):
    if sink is None and memory is None:
        return partial(alpha_node, garage=garage)
    if memory is None:
        return partial(alpha_node, garage=garage, sink=sink)
    if sink is None:
        return partial(alpha_node, garage=garage, memory=memory)
    return partial(alpha_node, garage=garage, sink=sink, memory=memory)
```

Apply the same pattern to `beta.py` and `charlie.py`. For `steward.py`, find the existing `make_steward_node` signature and add the `memory: "MemoryBackend | None" = None` parameter; forward it through the underlying partial the same way (steward does not call memory, but the signature must accept the param so the Tribunal can pass one).

- [ ] **Step 3: Run the existing deliberation tests to confirm no regression**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_alpha.py tests/unit/test_beta.py tests/unit/test_charlie.py tests/unit/test_steward.py tests/unit/test_llm_garage.py -v`

Expected: all green. No behavioral change yet.

- [ ] **Step 4: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tier1/deliberation/nodes/_base.py \
        backend/tier1/tier1/deliberation/nodes/alpha.py \
        backend/tier1/tier1/deliberation/nodes/beta.py \
        backend/tier1/tier1/deliberation/nodes/charlie.py \
        backend/tier1/tier1/deliberation/nodes/steward.py
git commit -m "feat(tier1): add memory parameter to run_agent and node factories

Backward-compatible signature plumbing; no behavior change. Tribunal
will pass memory through in a follow-up.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add recall and store blocks inside `run_agent`

**Files:**
- Modify: `backend/tier1/tier1/deliberation/nodes/_base.py`

**Interfaces:**
- Consumes: `MemoryBackend` (from `tier1.memory`), `MemoryEntry`, `MemoryType` (both from `tier1.memory`)
- Produces: `run_agent` now performs two additional best-effort operations gated on `memory is not None`

- [ ] **Step 1: Import the memory types and add a structlog logger**

At the top of `backend/tier1/tier1/deliberation/nodes/_base.py`, after the existing imports, add:

```python
import structlog

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType

log = structlog.get_logger(__name__)
```

Place these so the existing import order is preserved (group stdlib, then third-party, then local). `structlog` is third-party; the `tier1.memory` import is local.

- [ ] **Step 2: Add the recall block before the streaming loop**

In `run_agent`, after `user = build_user_prompt(state, agent)` and before `full_prompt = f"{system}\n\n{user}"`, insert:

```python
# Memory recall: pull past deliberations on similar topics.
if memory is not None:
    try:
        recall = await memory.search(state["problem"], top_k=3)
    except Exception:  # noqa: BLE001
        log.warning("memory.recall_failed", agent=agent, exc_info=True)
        recall = []
    if recall:
        recall_block = "PAST DELIBERATIONS ON SIMILAR TOPICS:\n" + "\n".join(
            f"- [{r.deliberation_id}] {r.agent}: {r.content[:200]}"
            for r in recall
        )
        user = user + "\n\n" + recall_block

full_prompt = f"{system}\n\n{user}"
```

The current line `full_prompt = f"{system}\n\n{user}"` already exists immediately after `user = build_user_prompt(state, agent)` (around line 69). Move the existing assignment below the new recall block so the recalled context flows into the final prompt.

- [ ] **Step 3: Add the store block after verdict emission**

In `run_agent`, after the `verdict_kind` event is appended (the line `events.append(DeliberationEvent(..., kind=verdict_kind, ...))`) and its sink call, but before the comment `# Update state`, insert:

```python
# Memory store: persist the verdict reasoning for future recall.
if memory is not None:
    entry = MemoryEntry(
        content=verdict.reasoning,
        memory_type=MemoryType.semantic,
        source="deliberation",
        deliberation_id=state.get("deliberation_id"),
        agent=agent,
        metadata={
            "position": verdict.position,
            "confidence": verdict.confidence,
            "round": state.get("round", 0),
        },
    )
    try:
        await memory.store(entry)
    except Exception:  # noqa: BLE001
        log.warning("memory.store_failed", agent=agent, exc_info=True)
```

- [ ] **Step 4: Run existing tests — default-behavior preservation check**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_alpha.py tests/unit/test_beta.py tests/unit/test_charlie.py tests/unit/test_steward.py tests/unit/test_llm_garage.py -v`

Expected: all green. With `memory=None` the new branches are skipped; existing behavior unchanged.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tier1/deliberation/nodes/_base.py
git commit -m "feat(tier1): recall and store memory around agent turns

run_agent now searches memory for related past deliberations before
streaming and stores the verdict reasoning after parsing. Both calls
are best-effort — failures are logged and swallowed so a memory outage
never breaks a deliberation.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Wire `memory` through `Tribunal`

**Files:**
- Modify: `backend/tier1/tier1/deliberation/graph.py:54-86`

**Interfaces:**
- Consumes: existing `Tribunal(settings, garage, sink)` constructor; the new `make_*_node(garage, sink, memory)` signatures from Task 1
- Produces: `Tribunal(settings, garage, sink=None, memory=None)` and `_build` forwards `self.memory` to all four factories

- [ ] **Step 1: Add `memory` parameter to `Tribunal.__init__`**

In `backend/tier1/tier1/deliberation/graph.py`, change the `__init__` from:

```python
def __init__(
    self,
    settings: Settings,
    garage: ModelGarage,
    sink: EventSink | None = None,
) -> None:
    self.settings = settings
    self.garage = garage
    self.sink = sink
    self._compiled = self._build(self.sink)
```

to:

```python
def __init__(
    self,
    settings: Settings,
    garage: ModelGarage,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
) -> None:
    self.settings = settings
    self.garage = garage
    self.sink = sink
    self.memory = memory
    self._compiled = self._build(self.sink, self.memory)
```

Add `"MemoryBackend | None"` to the existing `from __future__ import annotations` (line 6 already has it) so the forward reference resolves at type-check time without a circular import.

- [ ] **Step 2: Forward `memory` in `_build`**

Change `_build` from:

```python
def _build(self, sink: EventSink | None):
    g = StateGraph(DeliberationState)
    g.add_node("alpha", make_alpha_node(self.garage, sink))
    g.add_node("beta", make_beta_node(self.garage, sink))
    g.add_node("charlie", make_charlie_node(self.garage, sink))
    g.add_node("steward_tally", make_steward_node(self.settings, sink))
    g.add_node("finalize", _finalize_node)
```

to:

```python
def _build(self, sink: EventSink | None, memory: "MemoryBackend | None" = None):
    g = StateGraph(DeliberationState)
    g.add_node("alpha", make_alpha_node(self.garage, sink, memory))
    g.add_node("beta", make_beta_node(self.garage, sink, memory))
    g.add_node("charlie", make_charlie_node(self.garage, sink, memory))
    g.add_node("steward_tally", make_steward_node(self.settings, sink, memory))
    g.add_node("finalize", _finalize_node)
```

- [ ] **Step 3: Add the `MemoryBackend` import**

At the top of `graph.py`, add to the local imports:

```python
from tier1.memory import MemoryBackend
```

(Forward references still work because `from __future__ import annotations` is in effect, but a real import keeps type checkers and IDEs happy without runtime cost.)

- [ ] **Step 4: Run the existing Tribunal tests to confirm no regression**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_alpha.py tests/unit/test_beta.py tests/unit/test_charlie.py tests/unit/test_steward.py tests/unit/test_llm_garage.py -v`

Expected: all green. `Tribunal()` without `memory` produces identical graphs.

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tier1/deliberation/graph.py
git commit -m "feat(tier1): Tribunal accepts optional memory backend

Forwards to all four node factories. Backward compatible: Tribunal()
without memory builds the same graph as before.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Write the wiring tests

**Files:**
- Create: `backend/tier1/tests/unit/test_memory_wiring.py`

**Interfaces:**
- Consumes: `run_agent`, `make_alpha_node`, `Tribunal` (all from `tier1.deliberation.*`); mocked `MemoryBackend` from `unittest.mock.AsyncMock`

- [ ] **Step 1: Create the test file**

Create `backend/tier1/tests/unit/test_memory_wiring.py` with:

```python
"""Tests for memory wiring into the deliberation graph."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.config import Settings
from tier1.deliberation.graph import Tribunal
from tier1.deliberation.nodes._base import run_agent
from tier1.deliberation.nodes.alpha import make_alpha_node
from tier1.deliberation.state import initial_state


def _settings() -> Settings:
    return Settings(
        minimax_api_key="",
        anthropic_api_key="",
        openai_api_key="",
    )


def _fake_memory(entries=None, search_error=None, store_error=None):
    """Build a mocked MemoryBackend."""
    mem = AsyncMock()
    if search_error:
        mem.search = AsyncMock(side_effect=search_error)
    else:
        mem.search = AsyncMock(return_value=entries or [])
    if store_error:
        mem.store = AsyncMock(side_effect=store_error)
    else:
        mem.store = AsyncMock(return_value="entry-id")
    return mem


def _fake_garage():
    """ModelGarage stub that yields a valid verdict-shaped string."""
    garage = MagicMock()
    return garage


def _make_capturing_stream(garage, captured):
    async def capturing_stream(prompt, *, agent):
        captured.append(prompt)
        yield MagicMock(
            token='{"position":"approve","confidence":0.7,"reasoning":"ok","concerns":[]}',
            agent=agent,
            seq=0,
        )
    garage.stream_chat = capturing_stream
    return garage


_VERDICT_JSON = (
    '{"position":"approve","confidence":0.7,"reasoning":"ok","concerns":[]}'
)


async def test_run_agent_recalls_before_streaming():
    memory = _fake_memory(entries=[
        MagicMock(deliberation_id="d1", agent="alpha", content="past reasoning"),
    ])
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="new", problem="test problem")

    await run_agent(state, garage, agent="alpha", memory=memory)

    memory.search.assert_awaited_once()
    assert memory.search.await_args.kwargs["top_k"] == 3
    assert memory.search.await_args.args[0] == "test problem"
    assert "PAST DELIBERATIONS" in captured[0]
    assert "[d1]" in captured[0]
    assert "past reasoning" in captured[0]


async def test_run_agent_stores_after_verdict():
    memory = _fake_memory()
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="abc", problem="x")

    await run_agent(state, garage, agent="alpha", memory=memory)

    memory.store.assert_awaited_once()
    entry = memory.store.await_args.args[0]
    assert entry.deliberation_id == "abc"
    assert entry.agent == "alpha"
    assert entry.content == "ok"
    assert entry.metadata["position"] == "approve"


async def test_run_agent_without_memory_is_unchanged():
    """memory=None must produce identical behavior to old code."""
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="x", problem="y")

    result = await run_agent(state, garage, agent="alpha")  # no memory kwarg

    assert result.get("alpha_verdict") is not None
    assert result["alpha_verdict"].position == "approve"
    assert "PAST DELIBERATIONS" not in captured[0]


async def test_run_agent_search_failure_does_not_break():
    memory = _fake_memory(search_error=RuntimeError("qdrant down"))
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="x", problem="y")

    result = await run_agent(state, garage, agent="alpha", memory=memory)

    assert result.get("alpha_verdict") is not None


async def test_run_agent_store_failure_does_not_break():
    memory = _fake_memory(store_error=RuntimeError("postgres down"))
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    state = initial_state(deliberation_id="x", problem="y")

    result = await run_agent(state, garage, agent="alpha", memory=memory)

    assert result.get("alpha_verdict") is not None


async def test_tribunal_accepts_memory():
    """Tribunal constructs with a memory backend without error."""
    settings = _settings()
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)
    memory = _fake_memory()

    tribunal = Tribunal(settings, garage, memory=memory)

    assert tribunal.memory is memory


async def test_tribunal_without_memory_default():
    """Tribunal() with no memory still constructs and is callable."""
    settings = _settings()
    garage = _fake_garage()
    captured: list[str] = []
    _make_capturing_stream(garage, captured)

    tribunal = Tribunal(settings, garage)

    assert tribunal.memory is None
    assert tribunal._compiled is not None
```

- [ ] **Step 2: Run the new tests**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest tests/unit/test_memory_wiring.py -v`

Expected: 7 passed.

- [ ] **Step 3: If failures occur, iterate**

Common issues and fixes:

- **Recall assertion fails on `captured[0]`**: ensure `capturing_stream` yields one token; the parser will then accept it and emit a verdict event. If `memory.search` does not run, the `if memory is not None:` branch was not entered — re-check the `run_agent` parameter wiring.
- **`MemoryBackend` import error**: confirm `from tier1.memory import MemoryBackend` is in `graph.py` and `__future__` annotations import is present.
- **`MemoryType` is `str, Enum`**: comparing `entry.memory_type.value == "semantic"` should work; if not, change to `entry.memory_type == MemoryType.semantic`.
- **Tribunal construction fails**: ensure `_build(self.sink, self.memory)` (Task 3 Step 1) is being called and all four factory calls pass `memory`.

Re-run until all 7 pass.

- [ ] **Step 4: Commit the tests**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tests/unit/test_memory_wiring.py
git commit -m "test(tier1): cover memory recall/store wiring and backward compat

Seven tests: recall injects past deliberations into prompt, store
persists verdict reasoning, no-memory default is unchanged, search
and store failures don't break the deliberation, Tribunal accepts
optional memory.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Full suite + coverage check

**Files:** none modified — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `cd backend/tier1 && source .venv/bin/activate && python -m pytest -v`

Expected: all previously-passing tests still pass; the 7 new tests pass. Total ≥ 111 tests (104 prior + 7 new).

- [ ] **Step 2: Verify coverage ≥ 80%**

The coverage report at the bottom of the pytest output will show `TOTAL`. Confirm the percentage is ≥ 80%. If it drops below:

- Look for newly-uncovered lines in `tier1/deliberation/nodes/_base.py` — the recall/store branches.
- Add a small targeted test in `test_memory_wiring.py` that exercises the uncovered branch.

- [ ] **Step 3: Commit any test follow-ups (if needed)**

```bash
cd /home/john/Projects/heretek-swarm
git add backend/tier1/tests/unit/test_memory_wiring.py
git commit -m "test(tier1): push memory wiring coverage above 80%

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(Only commit if Step 2 surfaced an uncovered branch and Step 1 was extended.)
