---
date: 2026-08-05
topic: marketplace-versioning
status: accepted
closes: "#14"
parent: docs/superpowers/specs/2026-08-05-v1-launch-remediation-design.md
---

# Marketplace Manifest Versioning — Decision

> Date: 2026-08-05. Resolves issue #14. Author: agent-led per
> `2026-08-05-v1-launch-remediation-design.md` §6 step 1.

## Context

`PLAN.md` decision **D11** pins every plugin's effective version to the
marketplace repo commit SHA ("SHA-ride; revisit if churn becomes noise"),
and **D8** makes `catalog/catalog.yaml` the source of truth that
`scripts/generate_marketplace.py` projects into
`.claude-plugin/marketplace.json` (CI verifies the generation diff is
empty). The marketplace manifest itself does not currently carry a
`metadata.version` field; Claude Code's `/plugin marketplace update`
flow pulls the latest commit regardless.

Issue #14 asks whether the marketplace manifest should also carry an
explicit `metadata.version` for human readability / release-announcement
purposes. The decision gates the v1.0 release-tag format used by Task 9
(issue #13): a `metadata.version` field implies bumping it on every
release; no field means the `v1.0.0` git tag stands alone.

## Options considered

### A. Add `metadata.version: 1.0.0` and bump per release
- Pro: matches user expectations (a marketplace has a version);
  `gh release create` can stamp it.
- Pro: README / announcement can quote a single canonical version string.
- Con: drift risk — maintainer must remember to bump; CI lint required.
- Con: redundant with the SHA pin (D11 already pins the marketplace).

### B. Keep SHA-only; release is `v1.0.0` tag, not manifest field
- Pro: zero drift risk; manifest stays pure-data.
- Pro: aligns with D11's "version = commit SHA" worldview.
- Pro: keeps D8's generation contract unchanged — no new field in
  `catalog.yaml`, no new branch in `generate_marketplace.py`, no CI
  bump workflow.
- Pro: Task 9 (issue #13) stays simple — `gh release create v1.0.0`
  and `git push --tags` is the entire release mechanic.
- Con: `gh release create` tag has no in-manifest anchor; humans must
  look at git history or the GitHub Release page for the version.

### C. Hybrid — `metadata.version: "1.0.0 (commit <short-sha>)"`
- Pro: human-readable + SHA-anchored in one place.
- Con: redundant with `metadata.commit` (which Claude Code already
  exposes); requires maintaining a derived field.
- Con: would require `scripts/generate_marketplace.py` to inject the
  current short SHA at generation time — yet another drift surface.

## Decision

**Option B chosen.** Rationale: D11 and D8 already encode the
"commit SHA *is* the version" worldview at the architectural level;
adding a `metadata.version` field contradicts both decisions and
introduces a new drift surface (manifest field, catalog source field,
generator branch, CI bump hook) for information Claude Code and git
already expose trivially. Issue #14's own option (a) — "stay SHA-ride
only, add a v1.0.0 git tag for the public announcement" — matches
Option B and is the recommended path. The `v1.0.0` git tag created by
Task 9 (issue #13) becomes the canonical human-readable anchor without
changing the generated manifest. If release cadence later proves
"latest main" is too noisy (D11's stated revisit trigger), we reopen
the question with evidence in hand rather than adding the field
prophylactically today.

## Consequences

- **No code change.** `.claude-plugin/marketplace.json`,
  `catalog/catalog.yaml`, `scripts/generate_marketplace.py`, and
  `tests/schemas/marketplace.schema.json` are untouched. No regression
  test is added (per the test matrix in
  `2026-08-05-v1-launch-remediation-design.md` §8, only #9, #10, #11,
  #15, #16 carry test additions; #14 is design-only).
- **Task 9 (issue #13) stays simple:** `gh release create v1.0.0
  --title "heretek v1.0.0" --notes-file CHANGELOG.md` plus
  `git push --tags`. No manifest field bump is required alongside the
  tag.
- **Future releases** (v1.1.0, v2.0.0, …) follow the same pattern:
  git tag only. The tag's annotated message carries the changelog; the
  GitHub Release page carries the human-readable narrative.
- **Schema note:** `tests/schemas/marketplace.schema.json` already
  permits `metadata.version` (via `metadata.additionalProperties: true`)
  and a top-level `version` field, so this ADR does not close those
  schema doors — a future task can revisit without a schema migration.
- **Tracking:** issue #14 closes when this ADR merges; the
  v1-launch-remediation tracking issue's step 1 checkbox flips to done.
