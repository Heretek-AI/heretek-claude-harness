# #42 — RLM fast-gate results

> Status: DECIDED — AST-grep adopted. Authored 2026-08-06.

## Method

The planned comparison uses a 50-edit corpus from heretek's git history, with ground-truth labels assigned by manual review. The corpus run was not completed for the Plan B milestone, so no comparative precision or recall values are available.

## Results

| Metric | RLM (#42) | ast-grep (#43) | Decision |
|---|---|---|---|
| Precision | Not measured (corpus run pending) | Not measured (corpus run pending) | RLM did not demonstrate precision ≥ ast-grep |
| Recall | Not measured (corpus run pending) | Not measured (corpus run pending) | RLM did not demonstrate recall > ast-grep × 1.5 |
| Latency p50 | Not measured (corpus run pending) | Fast-gate implementation shipped in Task 5 | No evidence that RLM meets the comparative threshold |
| Latency p95 | Not measured (corpus run pending) | <100 ms in Task 5 latency test | RLM did not demonstrate p95 ≤2 s |

## Decision

Adopt #43 (AST-grep) as the synchronous fast-gate. Task 5 shipped the AST-grep hook, while the #42 RLM scaffold from Task 4 remains research-only.

The decision rule requires RLM to show precision at least equal to AST-grep, recall greater than 1.5 times AST-grep, and p95 latency no greater than 2 seconds. Because the corpus run did not produce measurements demonstrating all three conditions, the rule defaults to AST-grep. No RLM adoption ADR or AST-grep deprecation change is applicable.

The scaffold and pending corpus comparison remain available for future research. If a later corpus run demonstrates every threshold, this decision can be revisited.
