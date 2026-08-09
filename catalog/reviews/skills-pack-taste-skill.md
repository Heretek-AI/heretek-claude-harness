---
slug: skills-pack-taste-skill
date: 2026-08-09
status: approved
---

# Leonxlnx/taste-skill

## What

`taste-skill` is "gives your AI good taste. stops the AI from generating boring, generic slop." It is a Claude Code skill (and one targeting codex, cursor, vibecoding workflows) that injects design-taste instructions into the model so it produces more opinionated, less-generic output. Last commit on `main`: 2026-08-09 (HEAD `e988add20dab0fa97d7a76781c48961c8184288e`). 74,284★ at time of review (verified 2026-08-09 via `mcp__github__github-search_repositories`). License: MIT.

## Why

The two existing tone-and-style skills in skills-pack — `caveman` (terse token-saver) and `superpowers` (process discipline) — both reduce *verbosity* but neither adds *taste*. taste-skill fills the complementary slot: keep the words, but make them less generic. Pairs naturally with caveman: caveman cuts the noise, taste-skill raises the floor of what's left.

1. **Distinct value from existing skills** — caveman targets token economy; superpowers targets process. taste-skill targets *output quality*, which neither addresses. No overlap.
2. **Strong adoption signal** — 74,284★ dwarfs the D7 500★ floor; 5,088 forks indicate broad experimentation; `pushed_at` 2026-08-09 (same day).
3. **Cross-runtime reach** — covers Claude Code, codex, cursor, vibecoding workflows. heretek plugins can vendor the Claude Code subset cleanly.

## Alternatives

- **Hand-rolled "no generic output" skill** — every user would re-author the same system-prompt fragment. Rejected for duplication.
- **No design-taste slot in skills-pack** — current state. The model defaults to generic output without explicit injection. Rejected because taste-skill already codifies this and is D7-clean.
- **Leonxlnx/taste-skill** — chosen. MIT, 74,284★, last push 2026-08-09.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 74,284★, last commit 2026-08-09. Source-audit pass: SKILL.md is pure prose — it instructs the model on taste criteria. No shell, no subprocess, no network IO, no file-write. Trivial source-audit per D7.

## Target plugin

`skills-pack` (as the `taste-skill` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 74,284 stars at time of review (verified 2026-08-09).
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-09 (HEAD commit `e988add20dab0fa97d7a76781c48961c8184288e`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo root, SPDX `MIT`, copyright "Leonxlnx 2026").
- [x] source-audit pass — **PASS** the candidate ships `skills/<name>/SKILL.md` containing only prose instructions to the model on design-taste criteria. No executable code, no subprocess calls, no network IO, no file-write. Trivial source-audit per D7.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories endpoint not consulted for this prose-only repo (no executable surface). Documented per D7 spirit.

## Implementation note

Vendoring strategy: ship a minimal stub at `plugins/skills-pack/skills/taste-skill/SKILL.md` advertising the skill ("design-taste injection to avoid generic output") and pointing to upstream for the full criteria set. Mirror parity convention applies — both `.claude/skills/taste-skill/` and `.agents/skills/taste-skill/` should mirror when present. SHA pinned at filing time (`e988add20dab0fa97d7a76781c48961c8184288e`).
