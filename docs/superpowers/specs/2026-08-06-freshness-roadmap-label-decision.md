---
date: 2026-08-06
topic: freshness-roadmap-label
status: accepted
closes: roadmap-spec-label-gap
parent: docs/superpowers/specs/2026-08-06-freshness-enforced-coding-roadmap-design.md
---

# Freshness Roadmap `freshness-roadmap` Label — Decision

> Date: 2026-08-06. Resolves a spec gap surfaced during Plan A Task 3 execution.
> Author: agent-led per `2026-08-06-freshness-enforced-coding-roadmap-design.md` §8.

## Context

Spec `2026-08-06-freshness-enforced-coding-roadmap-design.md` has two
contradictory statements about labels:

**§2 (Non-goals)** explicitly forbids creating new labels:

> - Adding new labels to the repo. All proposed issues use existing labels
>   (`enhancement`, `security-scan`, `tech-debt`, `testing`, `help-wanted`,
>   `question`).

**§8 (Definition of done)** mandates a verification step that requires a
non-existent label:

> - [ ] Final check: `gh issue list --label freshness-roadmap` returns all 18
>   with no duplicates

The label `freshness-roadmap` does not exist in heretek's repository, and per
§2's non-goal, creating it would violate the spec's own constraint.

When Plan A Task 3 ran, the implementer correctly did NOT create the label
(pursuant to §2), and §8's "Final check" simply cannot be executed as written.

## Options considered

### A. Create the `freshness-roadmap` label

- Pro: §8's "Final check" becomes executable.
- Con: directly contradicts §2's non-goal.
- Con: introduces a label that's broader than the spec's own §2 enumeration
  (which lists only the 6 existing labels). A single new label here opens the
  door to "well, what's another broad label we need?" creep on future specs.

### B. Drop the §8 verification step; rely on existing labels only

- Pro: respects §2's non-goal.
- Pro: §8 already lists per-item-type labels (SHIP: `enhancement` + domain;
  SPIKE: `enhancement`; TEST: `enhancement` + `question` + `testing`) — these
  are sufficient to identify roadmap items via `gh issue list` with multiple
  label filters.
- Pro: aligns with how prior heretek specs (e.g.,
  `2026-08-05-v2-code-quality-issue-set-design.md`) verify issue filing — they
  check per-item labels, not a single umbrella label.
- Con: requires re-specifying the §8 verification in terms of existing labels.

### C. Replace `freshness-roadmap` with a search filter on issue titles

- Pro: no new label needed.
- Pro: matches the spec's title-prefix convention ("v1 freshness primitives: …",
  "v2 detection: …", etc., which Plan A Task 3 applied to all 18 issues).
- Con: brittle to title changes (future maintainers might rename issues
  without realizing the verification depends on the title prefix).

## Decision

**Option B chosen.** The §8 "Final check" is rewritten to use the existing
per-item-type labels, not a non-existent umbrella label.

The amended §8 check reads:

> - [ ] Final check: `gh issue list --label enhancement --state open | grep -c "^v[1-4]"` returns 18 (matches the 4 phases' issue prefixes). Per-type verification:
>   - SHIP: `gh issue list --label enhancement --label security-scan` returns ≥7
>   - SPIKE: `gh issue list --label enhancement` filtered to type=spike returns ≥6
>   - TEST: `gh issue list --label enhancement --label question --label testing` returns 4

This approach:
1. Respects §2's non-goal (no new labels).
2. Makes §8's verification step executable.
3. Provides stronger guarantees than a single umbrella label would (per-type
   checks catch mis-classification).

The spec §8 DoD is amended to drop the `freshness-roadmap` reference and replace
it with the multi-label verification above.

## Consequences

- **No new label created.** heretek's label set is unchanged. The 18 roadmap
  issues use the existing 4-label vocabulary (enhancement, security-scan,
  tech-debt, testing, question, tracking — `tracking` was added by
  Plan D Task 5 for the 3 follow-up issues, which was a different decision).
- **§8 "Final check" rewritten** to use existing labels in a per-type
  verification block.
- **Future specs** should not invent umbrella labels for verification. If a
  spec needs to filter its issues, use the per-item-type labels already in the
  vocabulary.
- **Tracking:** the parked spec-gap note in
  `.superpowers/sdd/2026-08-06-freshness-enforced-coding-foundation/progress.md`
  line 12 is closed by this ADR.

## Related

- `2026-08-06-freshness-enforced-coding-roadmap-design.md` §2, §8
- Plan A Task 3 fix round 1 (commits `8626e11..67d3bae`)
- Plan A pre-flight fix (commit `b99e0dd`; Plan A Task 3 re-applied in
  commits `d7154e7`, `b99e0dd`) — dropped `research` label per §2