---
slug: skills-pack-caveman
date: 2026-08-04
status: approved
---

# JuliusBrussee/caveman

## What

`caveman` is a Claude Code skill (and an opinionated text-compression style) that drops articles, filler words, hedging, and tool-call narration to reduce token usage by ~65% in conversational replies. The repo is a fully-shaped Claude Code plugin (`/.claude-plugin/plugin.json`, `/skills/caveman/SKILL.md`, plus six companion sub-skills: `cavecrew`, `caveman-commit`, `caveman-compress`, `caveman-help`, `caveman-review`, `caveman-stats`). Home page: https://caveman.so/. License: MIT. Last commit on `main`: 2026-08-04 (`ec83e5bace4c20484d704dea21e12fc4eb94e9aa`).

## Why

The heretek `skills-pack` ships a small set of generic (not language-specific) skills that improve every Claude Code session regardless of stack. Caveman is a strong fit because:

1. **Token-economy in tight loops** — Claude Code sessions can blow through context quickly when the agent narrates every tool call (`"I'll run the build, then check the diff..."`). Caveman's terse style directly reduces the per-turn token cost that D7/D6 budgets exist to control.
2. **Community reach** — 95,783 stars at time of review, well above the D7 500-star floor, indicating broad adoption and sustained testing by users outside the heretek team.
3. **Active maintenance** — `pushed_at` 2026-08-04 (same day), and `open_issues_count: 461` against `forks_count: 5500` shows a living project, not a one-shot meme.
4. **Composition** — pairs naturally with `superpowers:brainstorming` (which still uses full sentences for plan output) without overlapping concerns.

## Alternatives

- **davila7/claude-code-templates** (30,106★) — repository of snippets, not a single skill. Contains no equivalent caveman-style skill at the time of review.
- **Hand-rolled system prompt fragment** — possible but not portable across projects, and every user would have to copy-paste the same paragraph.
- **obra/superpowers** (266,415★) — complementary, not a substitute. Superpowers covers process (brainstorming, TDD, debugging); caveman covers text style. They stack.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 95,783★, last commit 2026-08-04. Source-audit pass: `SKILL.md` is pure prose — it instructs the model to drop articles and filler in conversation. No shell, no subprocess, no network, no file-write. The other six sub-skills (`cavecrew`, `caveman-commit`, `caveman-compress`, `caveman-help`, `caveman-review`, `caveman-stats`) are also prose-only. No critical CVEs in GitHub Security Advisories for `JuliusBrussee/caveman`.

## Target plugin

`skills-pack` (as the `caveman` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 95,783 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD commit `ec83e5bace4c20484d704dea21e12fc4eb94e9aa`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo root, `license.key = "mit"` in GitHub API response).
- [x] source-audit pass — **PASS** the v1 candidate ships `skills/caveman/SKILL.md` which contains only prose instructions to the model (drop articles, drop filler, no tool-call narration). No executable code in the v1 vendored skill, no subprocess calls, no network IO. Trivial source-audit per D7.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories endpoint returned zero advisories for `JuliusBrussee/caveman` at time of review.

## Implementation note

Vendoring strategy for v1 (per brief scope): ship a minimal stub at `plugins/skills-pack/skills/caveman/SKILL.md` whose `description:` frontmatter advertises the skill ("terse token-saving replies") and whose body is a one-paragraph usage pointer. Vendoring the actual upstream `SKILL.md` body is beyond v1 scope; the stub is sufficient for Claude Code auto-discovery and the actual style behavior is a system-prompt concern that the upstream README instructs users to wire into CLAUDE.md / AGENTS.md. Future task can decide whether to vendor full content or just the stub.
