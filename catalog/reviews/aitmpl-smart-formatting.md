---
slug: aitmpl-smart-formatting
date: 2026-08-04
status: rejected
---

# aitmpl.com/development-tools/smart-formatting

## What

A `PostToolUse` hook on `Edit|MultiEdit` that dispatches by file extension to the language-appropriate formatter (`prettier`, `black`, `gofmt`, `rustfmt`, `php-cs-fixer`). Source: `davila7/claude-code-templates/cli-tool/components/hooks/development-tools/smart-formatting.json`.

## Why

The intent ("auto-format on edit") is exactly what heretek's Layer 1 fast gates already do for the languages heretek supports — but the Level 1 design is **check, not format**. The hook in scope *formats* (writes back to the file), which puts it in direct conflict with the agent loop: Claude edits a file, this hook edits it back, and the diff Claude sees no longer matches the diff the user already approved.

## Alternatives

- **Layer 1 (fast gates, `<100ms`)** — heretek already runs `ruff --check` / `rustfmt --check` / `biome check` on the staged content before the Edit lands; the agent is told to fix before write. This is the right place for "is the file formatted?" checks.
- **Layer 3 (pre-commit)** — runs `pre-commit` framework with `black`, `prettier`, `rustfmt` configured to *fix* on commit. That's the correct moment for auto-formatting — after CI, not during the agent loop.
- **Editor-side formatting** — `editor.formatOnSave` in LSP clients handles this with no shell-out cost.

## Verdict

- [ ] Approved
- [x] Rejected

Reason: D7 source-audit fails (`shelling out to a subprocess is not` trivial — five different formatter binaries); D7 design fails (the hook rewrites the file in `PostToolUse`, racing with the agent's mental model of the edit); D5/D15 conflict (the `hooks` plugin owns all format-related gates; adding this would create ordering ambiguity with `fast_gate.py`).

## Target plugin

Would target `hooks` (per D15) if approved. Not approved.

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** upstream 30,106 stars.
- [x] last commit ≤ 12 months — **PASS** upstream last push 2026-08-04.
- [x] OSI-approved license — **PASS** MIT.
- [ ] source-audit pass — **FAIL** shells out to `npx prettier`, `black`, `gofmt -w`, `rustfmt`, `php-cs-fixer`. Each chain ends in `|| true`. The most important failure here is conceptual: the hook **writes** to the file in `PostToolUse`, which is the wrong tool for the job. Per D7: "shelling out to a subprocess is not" trivial. **Fail**.
- [ ] no critical CVEs in 24 months — **PASS-with-flag** same GHSA-79wm-x847-7cvg (CVSS 8.8, HIGH) as the upstream concern; not strictly critical by D7.
