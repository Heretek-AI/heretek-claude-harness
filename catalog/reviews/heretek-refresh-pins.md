# heretek:refresh-pins

> First-party item. Reviewed against D7 spirit (self-pin, internal review only — no upstream).
> Date: 2026-08-05

## What

`heretek:refresh-pins` is the quarterly D7-bar verification skill. It wraps
`scripts/refresh_pins.py` so a maintainer can re-check every catalog entry
against GitHub for stars, last commit, license drift, and critical CVEs.
The skill lives in the `skills-pack` plugin and emits a 4-column status
table (`ok` / `skipped` / `stale_*` / `cve_alert` / `license_drift`) that
drives the manual follow-up: bump SHA, mark rejected, or re-vet.

## Why first-party

The refresh-pins workflow is tightly coupled to heretek's specific D7
schema (`stars ≥ 500`, `last_commit ≤ 12 months`, critical-CVE check) and
to the project's `catalog/catalog.yaml` shape. There is no upstream
counterpart — only heretek's own vetting bar produces this report, and
the bar can change at any time.

## Alternatives considered

- **Cron-driven GitHub Action**: rejected because the action would
  auto-bump SHAs without maintainer judgment; the workflow's value is
  the human re-evaluation step.
- **One-off `scripts/refresh_pins.py` invocation without a skill**:
  rejected because the interpretation of the status table
  (`cve_alert` → mark rejected immediately) and the per-status
  follow-up steps are the load-bearing part of the workflow.
- **`heretek:refresh-pins` skill**: chosen — captures the offline-mode
  fallback (no `GITHUB_TOKEN` → all items `skipped`), the status
  semantics, and the tri-age steps in one place.

## Verdict

- [x] Approved (first-party)
- [ ] Rejected

Runtime: .claude/skills/ + .agents/skills/ (Claude Code / opencode top-level — see `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §3; skills ship outside `plugins/skills-pack/` so both runtimes can invoke them).

## Vetting checklist (D7 spirit)

- [x] Internal review by maintainer recorded (date: 2026-08-05)
- [x] No external code execution surface beyond documented SKILL.md / hooks.json
- [x] No external network calls beyond declared MCP
- [x] License: MIT
