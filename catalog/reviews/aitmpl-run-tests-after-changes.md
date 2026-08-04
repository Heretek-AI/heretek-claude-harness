---
slug: aitmpl-run-tests-after-changes
date: 2026-08-04
status: rejected
---

# aitmpl.com/post-tool/run-tests-after-changes

## What

A `PostToolUse` hook on `Edit` that runs `npm run test:quick` if `package.json` exists, swallowing all output and printing only a ✅/⚠️ emoji. Source: `davila7/claude-code-templates/cli-tool/components/hooks/post-tool/run-tests-after-changes.json`.

## Why

The "run tests after every edit" idea is what CI is for. Hooks in the agent loop exist to surface information *during* the loop, not to duplicate CI. This hook literally throws away the test output (`>/dev/null 2>&1`) and only emits an emoji — so neither the agent nor the user knows what actually failed.

## Alternatives

- **Layer 2 (`/quality-gate:run`)** — runs `tdd-guard`, `megalinter`, `jscpd`, `sonarqube`, with full output. The `tdd-guard` hook specifically gives the agent feedback between failing tests and the next edit, which is the design we want.
- **CI** — every push runs the test suite. Heretek should not duplicate that on every Edit.
- **Layer 3 (pre-commit)** — runs quick tests on commit, before the agent even knows the user pressed save.

## Verdict

- [ ] Approved
- [x] Rejected

Reason: D7 source-audit fails (shells out to `npm run test:quick`); D7 design fails (running full test suites from `PostToolUse` is a CI concern, not a hook concern); the hook silently swallows output, which is the opposite of what heretek's hooks are supposed to do (per the brief: hooks "wire into the agent loop" to surface information).

## Target plugin

Would target `hooks` (per D15) if approved. Not approved.

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** upstream 30,106 stars.
- [x] last commit ≤ 12 months — **PASS** upstream last push 2026-08-04.
- [x] OSI-approved license — **PASS** MIT.
- [ ] source-audit pass — **FAIL** runs `npm run test:quick --silent >/dev/null 2>&1`. The shell-out is non-trivial (spawns a node process via npm), and the silent-failure design is a correctness smell: the hook can report "✅ Tests passed" even when `test:quick` exits non-zero, because the `if` checks the exit code of the whole pipeline and the pipeline always succeeds (the `>/dev/null 2>&1` only redirects stdout/stderr, the exit code is preserved — but the `if`-clause prints "✅" on success and "⚠️" on failure, which is fine; the real failure is that the agent never sees the actual failing test names). Per D7: "shelling out to a subprocess is not" trivial. **Fail**.
- [ ] no critical CVEs in 24 months — **PASS-with-flag** same GHSA-79wm-x847-7cvg (CVSS 8.8, HIGH); not strictly critical.
