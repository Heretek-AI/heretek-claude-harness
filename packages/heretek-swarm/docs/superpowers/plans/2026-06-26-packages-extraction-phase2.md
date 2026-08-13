# Phase 2: Cross-Dependent Packages Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move 7 cross-dependent sub-packages (`memory/`, `llm/`, `security/`, `consensus/`, `actors/`, `gateway/`, `runtime/`) from `backend/heretek_swarm/` into `packages/core/src/heretek_swarm_core/`, breaking circular dependencies via Protocol indirection.

**Architecture:** Dependency-ordered migration: Tier 0 (memory, llm — leaves) → Tier 1 (security, consensus) → Tier 2 (actors, gateway) → Tier 3 (runtime — wiring hub). The hardest edge (`actors ↔ consensus`) is broken by Protocol indirection — `consensus/deliberation_mesh.py` uses a `TYPE_CHECKING` import + `Protocol` class instead of a direct runtime import.

**Tech Stack:** Python 3.12 (uv workspace), existing dependencies.

## Global Constraints

- Working directory: `/home/john/Projects/heretek-swarm/`
- Use `.venv/bin/python` (not system python) for all test runs
- All 145 collectable tests must continue passing after each task
- No code refactoring beyond import updates + Protocol indirection
- 16 test files have pre-existing collection failures (pytest.mark.asyncio, missing deps) — always exclude them:
  `tests/test_otel.py tests/test_api_metrics.py tests/test_db_timing_otel.py tests/test_memory.py tests/test_code_graph_query.py tests/test_autonomous_analysis_api.py tests/test_autonomous_loop.py tests/test_autonomous_s06_api.py tests/test_cognee_graph.py tests/test_cognee_rag.py tests/test_cognee_reader.py tests/test_cognee_writer.py tests/test_langgraph_e2e.py tests/test_langgraph_workflow.py tests/test_model_garage_characterization.py tests/test_sandbox.py`

## File Structure

**Create:**
- `packages/core/src/heretek_swarm_core/memory/` (8 files, 3.6k LOC)
- `packages/core/src/heretek_swarm_core/llm/` (5 files, 1.8k LOC)
- `packages/core/src/heretek_swarm_core/security/` (24 files, 10k LOC)
- `packages/core/src/heretek_swarm_core/consensus/` (24 files, 11.7k LOC)
- `packages/core/src/heretek_swarm_core/actors/` (44 files, 16.3k LOC)
- `packages/core/src/heretek_swarm_core/gateway/` (15 files, 6.7k LOC)
- `packages/core/src/heretek_swarm_core/runtime/` (23 files, 7.7k LOC)

**Modify:**
- `packages/core/src/heretek_swarm_core/__init__.py` — add re-exports
- `backend/heretek_swarm/__init__.py` — add backward-compat shims

---

## Task 1: Move memory/ to core

**Files:**
- Move: `backend/heretek_swarm/memory/` → `packages/core/src/heretek_swarm_core/memory/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move the directory**

```bash
mv backend/heretek_swarm/memory packages/core/src/heretek_swarm_core/memory
```

- [ ] **Step 2: Find internal cross-imports**

```bash
grep -rn "from heretek_swarm\.memory\|from heretek_swarm import memory" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -30
```

- [ ] **Step 3: Update all internal imports**

For each match found, change `from heretek_swarm.memory` → `from heretek_swarm_core.memory` and `from heretek_swarm import memory` → `from heretek_swarm_core import memory`.

- [ ] **Step 4: Add re-export to core __init__.py**

```python
from heretek_swarm_core.memory import *  # noqa: F401,F403
```

- [ ] **Step 5: Add backward-compat shim**

```python
from heretek_swarm_core.memory import *  # noqa: F401,F403
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/python -m pytest tests/ --ignore=tests/test_otel.py --ignore=tests/test_api_metrics.py --ignore=tests/test_db_timing_otel.py --ignore=tests/test_memory.py --ignore=tests/test_code_graph_query.py --ignore=tests/test_autonomous_analysis_api.py --ignore=tests/test_autonomous_loop.py --ignore=tests/test_autonomous_s06_api.py --ignore=tests/test_cognee_graph.py --ignore=tests/test_cognee_rag.py --ignore=tests/test_cognee_reader.py --ignore=tests/test_cognee_writer.py --ignore=tests/test_langgraph_e2e.py --ignore=tests/test_langgraph_workflow.py --ignore=tests/test_model_garage_characterization.py --ignore=tests/test_sandbox.py 2>&1 | tail -3
```

Expected: 145 passed.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(packages): move memory/ from monolith to heretek_swarm_core"
```

---

## Task 2: Move llm/ to core

**Files:**
- Move: `backend/heretek_swarm/llm/` → `packages/core/src/heretek_swarm_core/llm/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move**

```bash
mv backend/heretek_swarm/llm packages/core/src/heretek_swarm_core/llm
```

- [ ] **Step 2: Find internal cross-imports**

```bash
grep -rn "from heretek_swarm\.llm\|from heretek_swarm import llm" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -30
```

- [ ] **Step 3: Update all internal imports**

Change `heretek_swarm.llm` → `heretek_swarm_core.llm`.

- [ ] **Step 4: Add re-exports**

To both `packages/core/src/heretek_swarm_core/__init__.py` and `backend/heretek_swarm/__init__.py`:

```python
from heretek_swarm_core.llm import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests** (same command as Task 1)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move llm/ from monolith to heretek_swarm_core"
```

---

## Task 3: Move security/ to core

**Files:**
- Move: `backend/heretek_swarm/security/` → `packages/core/src/heretek_swarm_core/security/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move**

```bash
mv backend/heretek_swarm/security packages/core/src/heretek_swarm_core/security
```

- [ ] **Step 2: Find internal cross-imports**

```bash
grep -rn "from heretek_swarm\.security\|from heretek_swarm import security" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -30
```

- [ ] **Step 3: Update all internal imports**

Change `heretek_swarm.security` → `heretek_swarm_core.security`.

- [ ] **Step 4: Add re-exports**

To both `packages/core/src/heretek_swarm_core/__init__.py` and `backend/heretek_swarm/__init__.py`:

```python
from heretek_swarm_core.security import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests** (same command as Task 1)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move security/ from monolith to heretek_swarm_core"
```

---

## Task 4: Move consensus/ to core (with Protocol indirection for actors)

**Files:**
- Move: `backend/heretek_swarm/consensus/` → `packages/core/src/heretek_swarm_core/consensus/`
- Modify: `consensus/deliberation_mesh.py` — use Protocol indirection for `actors`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Find the cycle edge**

```bash
grep -rn "from heretek_swarm\.actors\|from heretek_swarm import actors" backend/heretek_swarm/consensus/ 2>/dev/null
```

- [ ] **Step 2: Move**

```bash
mv backend/heretek_swarm/consensus packages/core/src/heretek_swarm_core/consensus
```

- [ ] **Step 3: Apply Protocol indirection**

In `packages/core/src/heretek_swarm_core/consensus/deliberation_mesh.py`, find the runtime import of actors and replace with a Protocol indirection.

Before (e.g. line ~X):
```python
from heretek_swarm.actors import Agent
```

After:
```python
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from heretek_swarm_core.actors import Agent  # type hint only


class _AgentProtocol(Protocol):
    name: str
    # Add other methods that deliberation_mesh.py uses from Agent
```

Also change all `from heretek_swarm.consensus` imports elsewhere to `from heretek_swarm_core.consensus`.

- [ ] **Step 4: Update all other internal imports**

```bash
grep -rn "from heretek_swarm\.consensus\|from heretek_swarm import consensus" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -30
```

Change all to `heretek_swarm_core.consensus`.

- [ ] **Step 5: Add re-exports**

To both `packages/core/src/heretek_swarm_core/__init__.py` and `backend/heretek_swarm/__init__.py`:

```python
from heretek_swarm_core.consensus import *  # noqa: F401,F403
```

- [ ] **Step 6: Run tests** (same command as Task 1)

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(packages): move consensus/ from monolith to heretek_swarm_core with actors Protocol indirection"
```

---

## Task 5: Move actors/ to core

**Files:**
- Move: `backend/heretek_swarm/actors/` → `packages/core/src/heretek_swarm_core/actors/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move**

```bash
mv backend/heretek_swarm/actors packages/core/src/heretek_swarm_core/actors
```

- [ ] **Step 2: Find internal cross-imports**

```bash
grep -rn "from heretek_swarm\.actors\|from heretek_swarm import actors" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -50
```

- [ ] **Step 3: Update all internal imports**

Change `heretek_swarm.actors` → `heretek_swarm_core.actors`. The Protocol indirection from Task 4 step 3 must be reversed here — `consensus/deliberation_mesh.py` now imports from `heretek_swarm_core.actors` directly (the import is under `TYPE_CHECKING` so no runtime cycle).

- [ ] **Step 4: Add re-exports**

To both `packages/core/src/heretek_swarm_core/__init__.py` and `backend/heretek_swarm/__init__.py`:

```python
from heretek_swarm_core.actors import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests** (same command as Task 1)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move actors/ from monolith to heretek_swarm_core (largest move)"
```

---

## Task 6: Move gateway/ to core

**Files:**
- Move: `backend/heretek_swarm/gateway/` → `packages/core/src/heretek_swarm_core/gateway/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move**

```bash
mv backend/heretek_swarm/gateway packages/core/src/heretek_swarm_core/gateway
```

- [ ] **Step 2: Find internal cross-imports**

```bash
grep -rn "from heretek_swarm\.gateway\|from heretek_swarm import gateway" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -30
```

- [ ] **Step 3: Update all internal imports**

Change `heretek_swarm.gateway` → `heretek_swarm_core.gateway`. If `gateway/jetstream_manager.py` imports from `security`, it's now at `heretek_swarm_core.security`.

- [ ] **Step 4: Add re-exports**

To both `packages/core/src/heretek_swarm_core/__init__.py` and `backend/heretek_swarm/__init__.py`:

```python
from heretek_swarm_core.gateway import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests** (same command as Task 1)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move gateway/ from monolith to heretek_swarm_core"
```

---

## Task 7: Move runtime/ to core (final — wiring hub)

**Files:**
- Move: `backend/heretek_swarm/runtime/` → `packages/core/src/heretek_swarm_core/runtime/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move**

```bash
mv backend/heretek_swarm/runtime packages/core/src/heretek_swarm_core/runtime
```

- [ ] **Step 2: Find internal cross-imports**

```bash
grep -rn "from heretek_swarm\.runtime\|from heretek_swarm import runtime" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -50
```

- [ ] **Step 3: Update all internal imports**

Change `heretek_swarm.runtime` → `heretek_swarm_core.runtime`. `runtime/main_loop.py` imports from `actors`, `consensus`, `memory`, `gateway`, `llm` — all now at `heretek_swarm_core.*`.

- [ ] **Step 4: Add re-exports**

To both `packages/core/src/heretek_swarm_core/__init__.py` and `backend/heretek_swarm/__init__.py`:

```python
from heretek_swarm_core.runtime import *  # noqa: F401,F403
```

- [ ] **Step 5: Run full integration test**

```bash
.venv/bin/python -c "from heretek_swarm_core.runtime import *; from heretek_swarm_core.actors import *; from heretek_swarm_core.consensus import *; print('All Phase 2 imports OK')" 2>&1 | tail -3
```

Expected: `All Phase 2 imports OK`

- [ ] **Step 6: Run tests** (same command as Task 1)

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(packages): move runtime/ from monolith to heretek_swarm_core (Phase 2 complete)"
```

---

## Summary

Phase 2 moves 7 cross-dependent sub-packages (~58k LOC, ~143 files) into `packages/core/src/heretek_swarm_core/`. The dependency-ordered sequence (Tier 0 → Tier 1 → Tier 2 → Tier 3) ensures each package move doesn't break earlier moves. The `actors ↔ consensus` cycle is broken by Protocol indirection — `consensus/deliberation_mesh.py` uses a `TYPE_CHECKING` import + `Protocol` class.

After Phase 2, the only remaining monolith content is the API surface (`api/`, `observability/`, `security middleware`, `mcp/`, `integrations/`, `plugins/`, `agents/`, `rag/`) — Phase 3 will handle those.
