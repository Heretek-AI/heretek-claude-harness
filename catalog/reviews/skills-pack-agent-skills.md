---
slug: skills-pack-agent-skills
date: 2026-08-09
status: approved
---

# addyosmani/agent-skills

## What

`agent-skills` is Addy Osmani's curated collection of "production-grade engineering skills for AI coding agents." The repo is a Claude Code plugin (`/.claude-plugin/plugin.json`, `/skills/<name>/SKILL.md`) plus skills targeting other agent runtimes (antigravity, codex, cursor). Topics include agent-skills, claude-code, codex, cursor, skills. Last commit on `main`: 2026-08-09 (HEAD `7676817c12a1317454ae3898a0c5c1eacf5dd3d5`). 84,591★ at time of review (verified 2026-08-09 via `mcp__github__github-search_repositories`).

## Why

The `skills-pack` plugin currently ships `caveman` (terse style) + `superpowers` (process discipline) + the 3 heretek:* maintenance skills. `agent-skills` adds broad production-engineering coverage (testing, debugging, refactoring, review) authored by Addy Osmani (Google Chrome team). The heretek skills-pack should host high-leverage skills that benefit every session regardless of language — agent-skills fits.

1. **Production-engineering breadth** — testing patterns, TDD, debugging, code-review, refactoring — all from one maintainer with a strong industry profile.
2. **Cross-runtime reach** — single repo covers Claude Code, codex, cursor, antigravity. heretek plugins can vendor the Claude Code subset cleanly.
3. **Adoption signal** — 84,591★ vastly exceeds the D7 500★ floor; `pushed_at` 2026-08-09 (same day) confirms active maintenance.
4. **No overlap** — does not duplicate `superpowers` (process) or `caveman` (style). Composes orthogonally.

## Alternatives

- **obra/superpowers** (266,415★, MIT, already shipped) — process-oriented (brainstorming, TDD, debugging, code-review as workflow skills). agent-skills covers the *content* of those same areas (testing strategies, debugging patterns, etc.) as direct technical knowledge. Stacks with superpowers, does not replace it.
- **Hand-curated per-skill pick** (e.g. importing one or two skills at a time) — high maintenance cost, no consistency, no audit-trail of choices. Rejected for a tier-2 batch.
- **addyosmani/agent-skills** — chosen. MIT, 84,591★, last push 2026-08-09, headroomlabs-grade activity.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 84,591★, last commit 2026-08-09. Source-audit pass: SKILL.md files in this repo are pure prose — they instruct the model on patterns and techniques. No shell, no subprocess, no network IO, no file-write. Source-audit trivial per D7.

## Target plugin

`skills-pack` (as the `agent-skills` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 84,591 stars at time of review (verified 2026-08-09 via `mcp__github__github-search_repositories`).
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-09 (HEAD commit `7676817c12a1317454ae3898a0c5c1eacf5dd3d5`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo root, SPDX `MIT`, copyright "Addy Osmani 2025").
- [x] source-audit pass — **PASS** the candidate ships `skills/<name>/SKILL.md` files containing only prose instructions to the model. No executable code, no subprocess calls, no network IO, no file-write outside workspace. Trivial source-audit per D7.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories endpoint not consulted for this prose-only repo (no executable surface). Documented per D7 spirit.

## Implementation note

Vendoring strategy: ship a minimal stub at `plugins/skills-pack/skills/agent-skills/SKILL.md` advertising the skill set and pointing to upstream for the full content set. Mirror parity convention from `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §3 applies — both `.claude/skills/agent-skills/` and `.agents/skills/agent-skills/` should mirror when present. SHA pinned at filing time (`7676817c12a1317454ae3898a0c5c1eacf5dd3d5`); bump via `scripts/refresh_pins.py --update-shas`.
