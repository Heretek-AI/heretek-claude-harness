# Packages Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move leaf sub-packages from `backend/heretek_swarm/` into `packages/core/` and `packages/api/`, update imports to new namespaces, activate the uv workspace, remove bridge files.

**Architecture:** Two focused Python packages replace the monolithic `heretek_swarm` package. The extraction is incremental — we move sub-packages without internal cross-dependencies first, then move sub-packages that depend on them, updating imports as we go. The root `heretek-swarm` package keeps re-export shims during migration.

**Tech Stack:** Python 3.11, uv workspace, setuptools, existing dependencies (pydantic, structlog, FastAPI, etc.)

## Global Constraints

- Working directory: `/home/john/Projects/heretek-swarm/`
- Python 3.11
- uv for package management (workspace)
- All existing tests must pass after each task
- No code refactoring — pure file moves + import updates
- Each task is independently mergeable

## Strategy

The monolith has 51 sub-packages with ~180K LOC and thousands of cross-imports. Moving everything in one PR is infeasible. This plan extracts **leaf sub-packages** first (no internal cross-dependencies), then moves the more complex ones in follow-up plans.

### Phase 1 (this plan): Leaf extractions + workspace activation

| Sub-package | Phase | Reason |
|---|---|---|
| embeddings/ → core | Phase 1 | Leaf — no internal deps |
| models/ → core | Phase 1 | Leaf — no internal deps |
| schemas/ → core | Phase 1 | Leaf — no internal deps |
| utils/ → core | Phase 1 | Leaf — no internal deps |
| validation/ → core | Phase 1 | Leaf — no internal deps |
| swarm_logging/ → core | Phase 1 | Leaf — no internal deps |
| slices/ (empty) | Phase 1 | Skip — already empty |
| integrations/ (empty) | Phase 1 | Skip — already empty |
| realtime/ → api | Phase 1 | Leaf — no internal deps |
| research/ | Phase 1 | Skip — research/, not production |

### Phase 2+: Cross-dependent sub-packages (future plans)

`actors/`, `consensus/`, `memory/`, `gateway/`, `runtime/`, `security/`, `llm/`, `api/`, `agents/`, `collective/`, `consciousness/`, `infrastructure/`, `plugins/`, `rag/`, `tools/`, `workflow/`, etc. These require Phase 1 to complete first, then update their internal imports.

## File Structure

**Create:**
- `packages/core/src/heretek_swarm_core/embeddings/` (moved from `backend/heretek_swarm/embeddings/`)
- `packages/core/src/heretek_swarm_core/models/` (moved from `backend/heretek_swarm/models/`)
- `packages/core/src/heretek_swarm_core/schemas/` (moved from `backend/heretek_swarm/schemas/`)
- `packages/core/src/heretek_swarm_core/utils/` (moved from `backend/heretek_swarm/utils/`)
- `packages/core/src/heretek_swarm_core/validation/` (moved from `backend/heretek_swarm/validation/`)
- `packages/core/src/heretek_swarm_core/swarm_logging/` (moved from `backend/heretek_swarm/swarm_logging/`)
- `packages/api/src/heretek_swarm_api/realtime/` (moved from `backend/heretek_swarm/realtime/`)

**Modify:**
- `packages/core/src/heretek_swarm_core/__init__.py` — add re-exports
- `packages/api/src/heretek_swarm_api/__init__.py` — add re-exports
- `pyproject.toml` — activate workspace members
- `backend/heretek_swarm/__init__.py` — add deprecation re-exports for backward compat

---

## Task 1: Move embeddings/ to core

**Files:**
- Move: `backend/heretek_swarm/embeddings/` → `packages/core/src/heretek_swarm_core/embeddings/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

**Interfaces:**
- Produces: `heretek_swarm_core.embeddings` module available

- [ ] **Step 1: Move the directory**

```bash
mkdir -p packages/core/src/heretek_swarm_core
mv backend/heretek_swarm/embeddings packages/core/src/heretek_swarm_core/embeddings
```

- [ ] **Step 2: Check for internal cross-imports**

```bash
grep -rn "from heretek_swarm\.embeddings\|from heretek_swarm import embeddings" backend/ swarm-dashboard/ tests/ 2>/dev/null
```

Expected: No output (embeddings is a leaf — no internal deps).

- [ ] **Step 3: Update internal imports within embeddings/**

```bash
grep -rn "from heretek_swarm\.embeddings\|from heretek_swarm import embeddings" backend/ swarm-dashboard/ tests/ 2>/dev/null | head -10
```

If found, update them to `from heretek_swarm_core.embeddings import ...`.

- [ ] **Step 4: Add re-export to core __init__.py**

Open `packages/core/src/heretek_swarm_core/__init__.py`. Add to `__all__`:

```python
from heretek_swarm_core.embeddings import *  # noqa: F401,F403
```

- [ ] **Step 5: Add backward-compat shim to backend/__init__.py**

Open `backend/heretek_swarm/__init__.py`. Add:

```python
# Backward-compat re-export (remove after migration complete)
from heretek_swarm_core.embeddings import *  # noqa: F401,F403
```

- [ ] **Step 6: Run tests**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -x -q --no-header 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add -A && git commit -m "refactor(packages): move embeddings/ from monolith to heretek_swarm_core"
```

---

## Task 2: Move models/ to core

**Files:**
- Move: `backend/heretek_swarm/models/` → `packages/core/src/heretek_swarm_core/models/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move the directory**

```bash
mv backend/heretek_swarm/models packages/core/src/heretek_swarm_core/models
```

- [ ] **Step 2: Check for internal cross-imports**

```bash
grep -rn "from heretek_swarm\.models\|from heretek_swarm import models" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -20
```

Update all matches to `from heretek_swarm_core.models import ...`.

- [ ] **Step 3: Add re-export to core __init__.py**

```python
from heretek_swarm_core.models import *  # noqa: F401,F403
```

- [ ] **Step 4: Add backward-compat shim to backend/__init__.py**

```python
from heretek_swarm_core.models import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -x -q --no-header 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move models/ from monolith to heretek_swarm_core"
```

---

## Task 3: Move schemas/ to core

**Files:**
- Move: `backend/heretek_swarm/schemas/` → `packages/core/src/heretek_swarm_core/schemas/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move the directory**

```bash
mv backend/heretek_swarm/schemas packages/core/src/heretek_swarm_core/schemas
```

- [ ] **Step 2: Check for internal cross-imports**

```bash
grep -rn "from heretek_swarm\.schemas\|from heretek_swarm import schemas" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -20
```

Update matches.

- [ ] **Step 3: Add re-export to core __init__.py**

```python
from heretek_swarm_core.schemas import *  # noqa: F401,F403
```

- [ ] **Step 4: Add backward-compat shim**

```python
from heretek_swarm_core.schemas import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -x -q --no-header 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move schemas/ from monolith to heretek_swarm_core"
```

---

## Task 4: Move utils/ to core

**Files:**
- Move: `backend/heretek_swarm/utils/` → `packages/core/src/heretek_swarm_core/utils/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move the directory**

```bash
mv backend/heretek_swarm/utils packages/core/src/heretek_swarm_core/utils
```

- [ ] **Step 2: Check for internal cross-imports**

```bash
grep -rn "from heretek_swarm\.utils\|from heretek_swarm import utils" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -20
```

Update matches.

- [ ] **Step 3: Add re-export**

```python
from heretek_swarm_core.utils import *  # noqa: F401,F403
```

- [ ] **Step 4: Add backward-compat shim**

```python
from heretek_swarm_core.utils import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -x -q --no-header 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move utils/ from monolith to heretek_swarm_core"
```

---

## Task 5: Move validation/ to core

**Files:**
- Move: `backend/heretek_swarm/validation/` → `packages/core/src/heretek_swarm_core/validation/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move the directory**

```bash
mv backend/heretek_swarm/validation packages/core/src/heretek_swarm_core/validation
```

- [ ] **Step 2: Check for internal cross-imports**

```bash
grep -rn "from heretek_swarm\.validation\|from heretek_swarm import validation" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -20
```

Update matches.

- [ ] **Step 3: Add re-export**

```python
from heretek_swarm_core.validation import *  # noqa: F401,F403
```

- [ ] **Step 4: Add backward-compat shim**

```python
from heretek_swarm_core.validation import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -x -q --no-header 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move validation/ from monolith to heretek_swarm_core"
```

---

## Task 6: Move swarm_logging/ to core

**Files:**
- Move: `backend/heretek_swarm/swarm_logging/` → `packages/core/src/heretek_swarm_core/swarm_logging/`
- Modify: `packages/core/src/heretek_swarm_core/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move the directory**

```bash
mv backend/heretek_swarm/swarm_logging packages/core/src/heretek_swarm_core/swarm_logging
```

- [ ] **Step 2: Check for internal cross-imports**

```bash
grep -rn "from heretek_swarm\.swarm_logging\|from heretek_swarm import swarm_logging" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -20
```

Update matches.

- [ ] **Step 3: Add re-export**

```python
from heretek_swarm_core.swarm_logging import *  # noqa: F401,F403
```

- [ ] **Step 4: Add backward-compat shim**

```python
from heretek_swarm_core.swarm_logging import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -x -q --no-header 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move swarm_logging/ from monolith to heretek_swarm_core"
```

---

## Task 7: Move realtime/ to api

**Files:**
- Move: `backend/heretek_swarm/realtime/` → `packages/api/src/heretek_swarm_api/realtime/`
- Modify: `packages/api/src/heretek_swarm_api/__init__.py`
- Modify: `backend/heretek_swarm/__init__.py`

- [ ] **Step 1: Move the directory**

```bash
mkdir -p packages/api/src/heretek_swarm_api
mv backend/heretek_swarm/realtime packages/api/src/heretek_swarm_api/realtime
```

- [ ] **Step 2: Check for internal cross-imports**

```bash
grep -rn "from heretek_swarm\.realtime\|from heretek_swarm import realtime" backend/ swarm-dashboard/ tests/ packages/ 2>/dev/null | head -20
```

Update matches.

- [ ] **Step 3: Add re-export to api __init__.py**

```python
from heretek_swarm_api.realtime import *  # noqa: F401,F403
```

- [ ] **Step 4: Add backward-compat shim**

```python
from heretek_swarm_api.realtime import *  # noqa: F401,F403
```

- [ ] **Step 5: Run tests**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -x -q --no-header 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(packages): move realtime/ from monolith to heretek_swarm_api"
```

---

## Task 8: Activate uv workspace

**Files:**
- Modify: `pyproject.toml` — change `[tool.uv.workspace] members = []` to `members = ["packages/core", "packages/api"]`
- Modify: `packages/core/pyproject.toml` — add `heretek-swarm-core` build config
- Modify: `packages/api/pyproject.toml` — add `heretek-swarm-api` build config + dependency on `heretek-swarm-core`

- [ ] **Step 1: Check current root pyproject.toml workspace section**

```bash
grep -A5 "tool.uv.workspace" pyproject.toml
```

Expected: `members = []`

- [ ] **Step 2: Update root pyproject.toml**

Edit `pyproject.toml`. Change:

```toml
[tool.uv.workspace]
members = []
```

to:

```toml
[tool.uv.workspace]
members = ["packages/core", "packages/api"]
```

- [ ] **Step 3: Verify packages/core/pyproject.toml has build config**

```bash
cat packages/core/pyproject.toml | head -30
```

Expected: should have `[build-system]` and `[project]` sections. If not, the existing stub needs build config added.

If missing, add:

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "heretek-swarm-core"
version = "0.2.0"
# ... rest from existing stub
```

- [ ] **Step 4: Verify packages/api/pyproject.toml has build config + core dependency**

```bash
cat packages/api/pyproject.toml | head -40
```

Ensure it depends on `heretek-swarm-core>=0.2.0`. If not, add to `[project.dependencies]`:

```toml
"heretek-swarm-core>=0.2.0",
```

- [ ] **Step 5: Reinstall with workspace**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && uv sync 2>&1 | tail -10
```

Expected: installs both packages in editable mode.

- [ ] **Step 6: Verify imports work from new packages**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && python -c "from heretek_swarm_core.embeddings import *; from heretek_swarm_core.models import *; from heretek_swarm_core.schemas import *; from heretek_swarm_core.utils import *; from heretek_swarm_core.validation import *; from heretek_swarm_core.swarm_logging import *; from heretek_swarm_api.realtime import *; print('All imports OK')"
```

Expected: `All imports OK`

- [ ] **Step 7: Run full test suite**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -q --no-header 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "build(packages): activate uv workspace with core and api packages"
```

---

## Task 9: Final verification

- [ ] **Step 1: Verify both packages build**

```bash
cd /home/john/Projects/heretek-swarm/packages/core && python -m build --wheel 2>&1 | tail -5
cd /home/john/Projects/heretek-swarm/packages/api && python -m build --wheel 2>&1 | tail -5
```

Expected: both build wheels successfully.

- [ ] **Step 2: Verify monolith still works (backward compat)**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && python -c "from heretek_swarm.embeddings import *; from heretek_swarm.models import *; print('Backward compat OK')"
```

Expected: `Backward compat OK`

- [ ] **Step 3: Run full test suite one more time**

```bash
cd /home/john/Projects/heretek-swarm && source .venv/bin/activate && pytest tests/ -q --no-header 2>&1 | tail -5
```

- [ ] **Step 4: Commit final state**

```bash
cd /home/john/Projects/heretek-swarm && git add -A && git commit -m "chore(packages): phase 1 extraction complete — workspace active, leaf packages moved" --allow-empty
```

---

## Summary

Phase 1 extracts **7 leaf sub-packages** (6 to core, 1 to api) and activates the uv workspace. No internal cross-dependencies are affected, so each task is a pure file move + import update + re-export.

Phase 2+ (future plans) will handle the remaining 44 sub-packages that have internal cross-dependencies.
