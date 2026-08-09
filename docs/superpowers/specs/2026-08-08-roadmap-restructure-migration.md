# Roadmap Restructure — Migration Spec

**Date:** 2026-08-08
**Purpose:** Close out the old v1.x→v4-vision tracking structure and open the new v3.5/v5/v6 phase tracking issues.

## Pre-conditions

- New `docs/superpowers/roadmap.md` exists (Task 1).
- All 9 spike ADRs exist (Task 3).
- All rejection notes exist (Task 3).
- `PLAN.md` slimmed (Task 4).

## Issue Migration Sequence

### Close (3 issues)

1. **#87 [ROADMAP] All open issues prioritized index** → close as completed. Add comment:

   > Replaced by `docs/superpowers/roadmap.md` (canonical home for the new v2-v6 phased roadmap). See migration spec `docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md`.

2. **#88 v1.x (active maintenance + v1.1 hardening)** → close as completed (`state_reason: completed`). Add comment:

   > v1.0.0 shipped 2026-08-05 (CHANGELOG). Phase frozen; v1.x maintenance continues via PR-by-PR triage rather than a tracking issue.

3. **#92 cross-cutting: long-term test of 4 ideation approaches** → keep open, reassign to v4. Add comment:

   > Reassigned to v4 (workflow + eval). Cross-cutting ideation measurement continues; v4 phase tracking now at the mutated #91.

### Mutate (3 issues)

4. **#89 v2: backlog (new plugins, packs, tooling)** → update title to `v2: hooks hardening + security`. Update body to match the v2 scope from `docs/superpowers/roadmap.md` (3 ✅ + 1 🔬 + 2 ❌, 2 sub-specs: v2-a hooks hardening, v2-b security hardening).

5. **#90 v3: freshness enforcement, model cards, tokens** → update title to `v3: MCP/ACI expansion`. Update body to match the v3 scope (2 ✅ + 1 🔬, 2 sub-specs: v3-a MCP server expansion, v3-b catalog MCP audit).

6. **#91 v4-vision: spike research** → update title to `v4: workflow + eval`. Update body to match the v4 scope (3 ✅ + 1 🔬, 2 sub-specs: v4-a workflow patterns, v4-b Terminal-Bench 2.1 evaluation harness). Note that #92 cross-cutting test is reassigned here.

### Open (3 new issues)

7. **v3.5: observability** (parent of #109-#124) → use the `tracking` label. Body: scope, sub-specs list, acceptance criteria from `docs/superpowers/roadmap.md` §v3.5.

8. **v5: BYOK + local inference** → use the `tracking` label. Body: scope, sub-specs list (v5-a BYOK, v5-b local inference), acceptance criteria.

9. **v6: meta-harness + ACP research** → use the `tracking` label. Body: scope, sub-specs list (v6-a meta-harness, v6-b ACP, v6-c emerging patterns), acceptance criteria.

## Execution Order

Tasks 5-7 implement this spec. Sequence: open new issues first (so they exist before mutations), then mutate existing, then close.

## Verification

After all 9 actions:
- 6 phase tracking issues exist with `tracking` label
- 3 closed issues (#87, #88 done; #92 open with reassignment comment)
- 0 untracked v1.x→v4-vision references in new artifacts
