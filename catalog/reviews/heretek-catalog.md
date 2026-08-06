# heretek:catalog

> First-party item. Reviewed against D7 spirit (self-pin, internal review only — no upstream).
> Date: 2026-08-05

## What

`heretek:catalog` is the maintenance skill that grows the heretek marketplace
catalog. It ships inside the `skills-pack` plugin and exposes two modes:
`add-item` (research a candidate third-party item against the D7 bar and
append it to an existing plugin's `items[]` with a full vetting block and ADR)
and `add-plugin` (scaffold a brand-new plugin directory with its first
content files and a corresponding catalog entry). Both modes walk the same
research → ADR → catalog → content → validate → commit pipeline.

## Why first-party

This skill encodes heretek's own D7 vetting bar and the SP1 ADR template —
the catalog-add workflow is inseparable from the marketplace's review rules,
so it has to ship alongside the rules. Aggregating it from upstream would
mean re-encoding the D7 bar in someone else's repo, which would silently
drift the moment heretek's design evolves.

## Alternatives considered

- **Plain `/catalog` slash command with no SKILL.md**: rejected because the
  workflow is multi-step and conditional (different paths for `add-item`
  vs. `add-plugin`, plus D15 hook-ownership gates); a slash command cannot
  carry that decision tree without becoming a small program.
- **Generic `gh` CLI invocation by the model**: rejected because the skill's
  value is the curation rules (which candidates fail D7 and why), not the
  data-fetching steps.
- **`heretek:catalog` skill**: chosen — owns the D7 bar and the SP1 template
  in one place, versioned with the harness.

## Verdict

- [x] Approved (first-party)
- [ ] Rejected

## Target plugin

`skills-pack`

## Vetting checklist (D7 spirit)

- [x] Internal review by maintainer recorded (date: 2026-08-05)
- [x] No external code execution surface beyond documented SKILL.md / hooks.json
- [x] No external network calls beyond declared MCP
- [x] License: MIT
