# Phase 2: Cross-Dependent Packages Extraction — Design Spec

**Date:** 2026-06-26
**Status:** Approved (pending implementation)

## Context

Phase 1 of packages extraction moved 7 leaf sub-packages into `packages/core/` and `packages/api/`. The workspace is now activated and all three packages install as editable workspace members. This spec covers Phase 2: moving the remaining cross-dependent sub-packages that form the core agent infrastructure.

## Goals

1. Move `memory/`, `llm/`, `security/`, `consensus/`, `actors/`, `gateway/`, `runtime/` to `packages/core/src/heretek_swarm_core/`
2. Break circular dependencies through Protocol indirection + lazy imports (no code refactoring)
3. All existing tests continue to pass after each task
4. After Phase 2: ~65k LOC moved total (Phase 1: 7k + Phase 2: 58k)

## Non-goals

- Moving api/ sub-packages (Phase 3, future plan)
- Splitting actors/ into multiple packages (deferred — too risky for now)
- Changing any code beyond imports (pure file moves + import updates)

## Architecture

### Dependency-Ordered Migration Sequence

```
Tier 0 (no internal Phase-2 deps):
  1. memory/      → core (3.6k LOC, 0 cross-deps)
  2. llm/         → core (1.8k LOC, 0 cross-deps)

Tier 1 (depend only on Tier 0):
  3. security/    → core (10k LOC, 1 dep → consensus)
  4. consensus/   → core (11.7k LOC, 2 deps — has cycle with actors)

Tier 2 (depends on Tier 0 + 1):
  5. actors/      → core (16.3k LOC, 5 deps — biggest, most-imported)
  6. gateway/     → core (6.7k LOC, 1 dep → security)

Tier 3 (depends on everything below):
  7. runtime/     → core (7.7k LOC, 5 deps — wiring hub, move LAST)
```

### Sub-package Mapping

| Sub-package | Source | Destination | Files | LOC |
|---|---|---|---|---:|
| memory/ | `backend/heretek_swarm/memory/` | `packages/core/src/heretek_swarm_core/memory/` | 8 | 3,609 |
| llm/ | `backend/heretek_swarm/llm/` | `packages/core/src/heretek_swarm_core/llm/` | 5 | 1,817 |
| security/ | `backend/heretek_swarm/security/` | `packages/core/src/heretek_swarm_core/security/` | 24 | 10,115 |
| consensus/ | `backend/heretek_swarm/consensus/` | `packages/core/src/heretek_swarm_core/consensus/` | 24 | 11,771 |
| actors/ | `backend/heretek_swarm/actors/` | `packages/core/src/heretek_swarm_core/actors/` | 44 | 16,319 |
| gateway/ | `backend/heretek_swarm/gateway/` | `packages/core/src/heretek_swarm_core/gateway/` | 15 | 6,676 |
| runtime/ | `backend/heretek_swarm/runtime/` | `packages/core/src/heretek_swarm_core/runtime/` | 23 | 7,737 |

## Circular Dependency Strategy

The hardest edge is `actors ↔ consensus`. Three concrete edges to break:

| Edge | File | What it imports | Strategy |
|---|---|---|---|
| `consensus → actors` | `consensus/deliberation_mesh.py` | actor types | Protocol indirection |
| `consensus → security` | `consensus/immune.py` | immune types | Lazy import |
| `gateway → security` | `gateway/jetstream_manager.py` | token validation | Direct import (security moves first) |
| `actors → consensus` | actors/* (14 statements) | heavy | Move actors first |
| `actors → security` | actors/* (24 statements) | heaviest | Move security before actors |
| `actors → memory` | actors/* (15 statements) | direct | Move memory before actors |
| `runtime → actors` | runtime/* (34 statements) | wiring | Move actors before runtime |

**Protocol indirection pattern** (used for `consensus → actors`):

```python
# In consensus/deliberation_mesh.py (when it lives in packages/core/.../consensus/)
# actors is NOT yet at heretek_swarm_core.actors — use Protocol indirection

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from heretek_swarm_core.actors import Actor  # only for type hints

class ActorProtocol(Protocol):
    name: str
    async def process(self, msg: object) -> object: ...
```

## Error handling

- Pre-existing circular imports (already fixed in Phase 1) provide the pattern: lazy `__getattr__` proxy in the legacy `__init__.py`
- Cross-package cycles broken by Protocol indirection where the import is just for type hints
- Each task verifies imports work + tests pass before moving to the next

## Testing

- `.venv/bin/python -m pytest tests/ --ignore=<5 pre-existing broken files>` — must stay at 145 passing
- After each task: verify moved modules importable from both old and new paths
- Final task: full integration test via `from heretek_swarm_core.runtime import *`

## Implementation order

1. Move memory/ to core
2. Move llm/ to core
3. Move security/ to core (with consensus Protocol indirection prep)
4. Move consensus/ to core (with actors Protocol indirection)
5. Move actors/ to core (using the Protocol indirection from step 4)
6. Move gateway/ to core
7. Move runtime/ to core (final, wires everything together)
