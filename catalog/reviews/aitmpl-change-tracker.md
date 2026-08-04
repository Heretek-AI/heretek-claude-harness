---
slug: aitmpl-change-tracker
date: 2026-08-04
status: rejected
---

# aitmpl.com/development-tools/change-tracker

## What

A `PostToolUse` hook that appends `[YYYY-MM-DD HH:MM:SS] File modified/created: <path>` to `~/.claude/changes.log` on every `Edit|MultiEdit|Write`. Source: `davila7/claude-code-templates/cli-tool/components/hooks/development-tools/change-tracker.json`.

## Why

This hook is the only one of the five that doesn't shell out to a subprocess — it uses shell builtins (`echo`, `$(date)`, `>>`, redirect). The D7 source-audit criterion says "shelling out to a subprocess is not" trivial; shell builtins *are* trivial. So on the strict source-audit reading **this hook is eligible**.

It is rejected on design grounds instead.

## Alternatives

- **Layer 3 (pre-commit framework)** — git already tracks every change. Heretek's pre-commit config plus `git log` already gives the user a full audit trail keyed by commit, author, and timestamp. The aitmpl hook would write a parallel log that is *less* useful than `git log`.
- **`/quality-gate:run` history** — Layer 2 records each run with the diff it produced. More actionable than a timestamped log of file paths.

## Verdict

- [ ] Approved
- [x] Rejected

Reason: D7 source-audit would *pass* (trivial shell, no subprocess), but the hook is rejected on D5/D15/architecture grounds. heretek's hooks plugin owns all hooks firing on `Edit`/`Write` (D15), and this hook's value (a log of file changes) is already provided by git (the very thing Layer 3 wraps). Adding it would create a parallel, less-useful audit trail.

## Target plugin

Would target `hooks` (per D15) if approved. Not approved.

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** upstream 30,106 stars.
- [x] last commit ≤ 12 months — **PASS** upstream last push 2026-08-04.
- [x] OSI-approved license — **PASS** MIT.
- [ ] source-audit pass — **PASS-with-reservation** the hook command is `echo "[$(date '+%Y-%m-%d %H:%M:%S')] File modified: $CLAUDE_TOOL_FILE_PATH" >> ~/.claude/changes.log` (and the `Write` variant says "File created" instead). This is shell builtins only — no subprocess. D7 calls trivial hooks like this acceptable. Source-audit verdict: **pass**. Failure shifts to design grounds (D5/D15 overlap with git + Layer 3).
- [ ] no critical CVEs in 24 months — **PASS-with-flag** upstream GHSA-79wm-x847-7cvg (CVSS 8.8, HIGH) same concern; not strictly critical by D7.
- [ ] **Architecture overlap (D5/D15)** — **FAIL** git already tracks changes; heretek's Layer 3 wraps git with pre-commit. Adding a fourth parallel audit trail (`~/.claude/changes.log`) for the agent loop is duplicative and writes outside the user's repo (privacy/durability concerns: that file lives in the user's home dir, not in any tracked location).
