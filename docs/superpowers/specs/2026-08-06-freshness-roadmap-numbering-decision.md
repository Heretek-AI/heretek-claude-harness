---
date: 2026-08-06
topic: freshness-roadmap-numbering
status: accepted
closes: roadmap-spec-numbering-gap
parent: docs/superpowers/specs/2026-08-06-freshness-enforced-coding-roadmap-design.md
---

# Freshness Roadmap Issue Numbering — Decision

> Date: 2026-08-06. Resolves a spec gap surfaced during Plan A Task 3 execution.
> Author: agent-led per `2026-08-06-freshness-enforced-coding-roadmap-design.md` §8.

## Context

Spec `2026-08-06-freshness-enforced-coding-roadmap-design.md` §8 (Definition of
done) mandates that the 18 roadmap issues be filed "numbered #36–#53":

> - [ ] Final check: `gh issue list --label freshness-roadmap` returns all 18 with no duplicates

The implementation actually filed the 18 issues as **#66–#83**, because GitHub's
issue numbering is global and monotonic, and intervening issues were created in
the project between the spec's authoring and the filing session (housekeeping
triage, dependabot PRs, etc.). The spec draft numbers (`#36–#53`) also exist as
real GitHub issues owned by **other** work — e.g., `#42` is the
`security@heretek.ai` mailbox ops ticket, not a roadmap item.

When the issues were first filed with spec-draft numbers in their
`## Cross-references` sections, those refs resolved to unrelated issues,
actively misleading readers.

## Options considered

### A. Re-file the 18 issues with the spec-draft numbers #36–#53

- Pro: matches the spec DoD verbatim.
- Con: impossible — GitHub does not allow renumbering. The only way to achieve
  this would be to close the 18 issues and file 18 new ones, which would
  inherit whatever numbers GitHub chose next (still not #36–#53). Also breaks
  any already-applied labels, references, and review state.
- Con: would orphan the actual #36–#53 issues (none of which are owned by this
  work) and create 18 new closed issues (noise).

### B. Adopt the actual GitHub-assigned numbers; amend the spec DoD

- Pro: matches reality. The 18 issues are filed, properly labeled, and resolve
  correctly in cross-references.
- Pro: the spec's intent (a verifiable set of 18 issues with consistent
  structure) is satisfied — the numbering was a means, not an end.
- Pro: aligns with how prior heretek specs (e.g.,
  `2026-08-05-v2-code-quality-issue-set-design.md`) describe issues — they
  reference issue *numbers* assigned at filing time, not pre-allocated slots.
- Con: spec must be amended post-hoc. The contradiction between §8 ("numbered
  #36–#53") and §6 (cross-reference matrix using #36–#53) is now real.

### C. Hybrid — keep both numbering schemes; document the mapping

- Pro: preserves the spec's table (which uses #36–#53 throughout §3, §6, §7)
  for future planning and educational purposes.
- Pro: leaves the actual GitHub-assigned numbers as authoritative for issue
  bodies and external links.
- Con: requires maintaining a mapping document going forward.

## Decision

**Option B + Option C combined.** Adopt Option B for *all references in issue
bodies and external communication*; preserve Option C by keeping the
spec's `#36–#53` numbering in §3 (the planning table) and §7 (sequencing
table), with a documented mapping in this ADR and in the spec §8 DoD.

The mapping (spec-draft # → GitHub #) is:

```
36 → 66,  37 → 67,  38 → 68,  39 → 69,  40 → 70,  41 → 71,  42 → 72,  43 → 73,
44 → 74,  45 → 75,  46 → 76,  47 → 77,  48 → 78,  49 → 79,  50 → 80,  51 → 81,
52 → 82,  53 → 83
```

(Plan A Task 3 fix round 1 applied this mapping to all 18 issue bodies and to
the spec's `## Cross-references` matrices. All cross-references now resolve
correctly.)

The spec §8 DoD is amended to read:

> - [ ] Final check: `gh issue list --label freshness-roadmap` returns all 18
>   with no duplicates. (Spec-draft numbers #36–#53 map to GitHub-assigned
>   numbers per [this ADR](2026-08-06-freshness-roadmap-numbering-decision.md).)

## Consequences

- **Spec amendment applied in fix round 1** — the contradiction is resolved in
  both directions: the spec acknowledges the spec-draft numbers as planning
  identifiers, and the implementation acknowledges the GitHub numbers as
  authoritative identifiers.
- **Future plans referencing these issues** should use the GitHub-assigned
  numbers (#66–#83 for roadmap items, #84–#86 for Phase 4 follow-ups).
- **Future SDD specs** should NOT pre-allocate issue numbers; they should
  describe items by topic and let filing assign the numbers. Cross-reference
  matrices in specs are still useful as planning artifacts, but should be
  marked "(spec-draft #; actual GitHub # assigned at filing time)".
- **Tracking:** the parked spec-gap note in
  `.superpowers/sdd/2026-08-06-freshness-enforced-coding-foundation/progress.md`
  line 11 is closed by this ADR.

## Related

- `2026-08-06-freshness-enforced-coding-roadmap-design.md` §3, §6, §7, §8
- Plan A Task 3 fix round 1 (commits `8626e11..67d3bae`)
- Plan D Task 5 fix round 1 (commit `3ead9c2`; Phase 4 follow-up issues
  `#84`, `#85`, `#86` use the same GitHub-assigned-numbering principle)