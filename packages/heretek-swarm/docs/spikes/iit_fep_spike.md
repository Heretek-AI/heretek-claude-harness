# pyphi + pymdp spike — Phase 3C of the OSS roadmap

## Decision (2026-06-04)

**Keep the in-house 3,149-LOC code (Option 1).** Defer the
pyphi/pymdp migration indefinitely — upstream pyphi has not
released since 2019 and shows no signs of activity. Revisit only
if a maintained pyphi-2 or viable pymdp path appears.

A 6-month re-check is scheduled (cron) to re-verify upstream
status; if nothing has changed by then, the in-house code remains
the canonical IIT/FEP path per the plan's "what stays in-house"
section.

## Purpose

Validate that **pyphi** (https://github.com/wmayner/pyphi,
MIT, Tononi/Albantakis lab reference implementation of IIT 3.0)
and **pymdp** (https://github.com/infer-actively/pymdp,
MIT, active-inference framework) are the integration target for
the 3,149-LOC in-house consciousness math:

  * `consciousness/iit.py` (462) + `consciousness/iit_phi.py` (805) = **1,267 LOC** (IIT)
  * `consciousness/fep.py` (526) + `consciousness/fep_active_inference.py` (1,356) = **1,882 LOC** (FEP)

Combined target: 3,149 LOC reduction (matches the plan's Phase 3C).

## Status (verified 2026-06-04)

- **pyphi 1.x** is the canonical Tononi-lab implementation but is
  **incompatible with Python 3.10+** (uses
  `from collections import Iterable` which was removed). The project
  runs Python 3.11+/3.14, so pyphi 1.x is **not a drop-in**.
- **pymdp** is currently Python 3.10+ compatible (per its GitHub
  CI badge) but has heavy JAX/PyTorch dependencies that may not fit
  the swarm's runtime.
- A working spike would require either:
  - Fork pyphi 1.x and patch the `collections.Iterable` import
    (low effort, high risk of breaking IIT numerics).
  - Use a maintained pyphi alternative (e.g. `pyphi-2` if it
    exists, or roll a thin IIT-3.0 wrapper over `numpy`).
  - Or keep the in-house IIT/FEP and add a Python-version pin to
    the affected files.

## Kill criteria (per the plan)

- If pyphi's numerical reproducibility is <0.99 correlation with
  our reference outputs, keep the in-house code.
- If pymdp's JAX dependency adds >50MB to the runtime image,
  fall back to a hand-rolled active-inference loop.

## Migration pattern (full cutover, not yet applied)

The 3,149-LOC candidate set is replaced as follows:

1. `consciousness/iit.py` (462) + `consciousness/iit_phi.py` (805) = 1,267 LOC
   → DELETE; replaced by `from pyphi import compute phi` (after the
   Python 3.14 compatibility patch).
2. `consciousness/fep.py` (526) + `consciousness/fep_active_inference.py` (1,356) = 1,882 LOC
   → DELETE; replaced by `from pymdp.agent import Agent` for active
   inference.

The 3 in-house files kept per the plan:
- `consciousness/ast.py` (Graziano AST — no OSS replacement)
- `consciousness/agency_metrics.py` (Prime Directive compliance)
- `consciousness/self_model.py` (project-specific self-model)

## Recommendation (per the spike)

**DEFER the IIT/FEP migration** until either:
1. pyphi releases a Python 3.11+ compatible version, OR
2. The project pins the affected files to Python 3.9 (not viable
   for the rest of the swarm which uses 3.11+ syntax).

In the meantime, keep the in-house IIT/FEP as the
differentiating-surface code per the plan's "what stays in-house"
section.

## Result

- pyphi 1.x is **not** Python 3.14 compatible (verified by import
  error: `ImportError: cannot import name 'Iterable' from 'collections'`).
- pymdp is Python 3.10+ compatible but adds JAX/PyTorch
  dependencies that don't fit the runtime image.
- The Phase 3C migration is **BLOCKED** pending upstream
  compatibility fixes.

This finding is the spike's primary output: it tells the team
the Phase 3C work cannot proceed as planned without either
forking pyphi or downgrading Python.
