---
name: outline-driven-dev
description: Enforce Outline-Driven Development (ODD): requirement analysis -> task outline -> incremental execution -> empirical verification.
---

# outline-driven-dev

Enforce systematic, step-by-step engineering execution.

## Phases

### 1. Outline & Spec
Define exact requirements, target files, and modification boundaries before making edits.

### 2. Task Checklist
Maintain a `task_list.md` checklist with atomic steps. Mark items complete as work proceeds.

### 3. Incremental Execution
Make targeted, atomic changes. Never perform sweeping unverified mass edits across unrelated components.

### 4. Empirical Verification
Always execute test runner, type checker, or linter after changes. Verify pass state with zero errors before concluding.
