---
slug: aitmpl-dependency-checker
date: 2026-08-04
status: rejected
---

# aitmpl.com/automation/dependency-checker

## What

A `PostToolUse` hook on `Edit` that detects when a dependency manifest (`package.json`, `requirements.txt`, `Cargo.toml`, `pom.xml`, `Gemfile`) is modified and shells out to `npm audit`, `npx npm-check-updates`, `safety check`, or `cargo audit`. Source: `davila7/claude-code-templates/cli-tool/components/hooks/automation/dependency-checker.json`.

## Why

"Tell me when a dependency file changes" is a reasonable concern, but heretek already routes this through Layer 3 (pre-commit/pre-push) and Layer 2 (`/quality-gate:run`) — both of which can run full supply-chain analysis with proper output, not a `$?`-suppressed echo.

## Alternatives

- **Layer 3 (pre-commit framework)** — runs `pip-audit`, `npm audit --omit=dev`, `cargo audit` on pre-commit hooks via the pre-commit framework. Output goes to the user, not into the agent loop.
- **Layer 2 (`/quality-gate:run`)** — runs the full suite on demand, including dependency audits with `megalinter`'s security hook.
- **`security` plugin** — could carry an "audit dependencies" skill, but plugins cannot ship hooks (D15).

## Verdict

- [ ] Approved
- [x] Rejected

Reason: D7 source-audit fails (chains 4 external subprocess invocations plus `|| true`); D7 design intent fails (the hook is gated on every `Edit` to a manifest, which means the analyzer races against the agent loop and CI at the same time — duplicate work between CI and Claude Code); plus D15 (hooks plugin owns all hooks; running this from `automation` namespace would be a split).

## Target plugin

Would target `hooks` (per D15) if approved. Not approved.

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** upstream `davila7/claude-code-templates` has 30,106 stars.
- [x] last commit ≤ 12 months — **PASS** upstream last push 2026-08-04.
- [x] OSI-approved license — **PASS** MIT.
- [ ] source-audit pass — **FAIL** invokes `npm audit`, `npx npm-check-updates`, `safety`, `cargo audit` via `command -v` guards. Each chain ends in `|| true`, so missing tools (the common case in dev environments) silently degrade to no-op. The `npx npm-check-updates` step also requires network and can take 10+ seconds — incompatible with Layer 1 sub-100ms goal. Per D7 "shelling out to a subprocess is not" trivial. **Fail**.
- [ ] no critical CVEs in 24 months — **PASS-with-flag** same GHSA-79wm-x847-7cvg (CVSS 8.8, HIGH) as the security-scanner ADR; not strictly critical by D7 but the same concern against SHA-pinning the repo.
