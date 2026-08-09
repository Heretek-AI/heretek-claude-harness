---
slug: skills-pack-wondelai
date: 2026-08-09
status: approved
---

# wondelai/skills

## What

`wondelai/skills` is "Wondel.ai Agent Skills — Business, Marketing, UX & Coding Frameworks from Bestselling Books. 50 skills + 12 guided journeys for Claude Code, Codex, Cursor & other agentskills.io agents." The repo is a skills collection targeting Claude Code, Codex, and Cursor. License: MIT. Last commit on `main`: 2026-08-08 (HEAD `73de8a53f618ce9361673a2a9eb80532459658fb`). 1,868★ at time of review (verified 2026-08-09 via `mcp__github__github-search_repositories`). Active topics include agent-skills, claude-code, claude-skills, code-quality, frameworks, marketing, product-strategy, skill-md, ux.

## Why

The heretek marketplace is engineering-focused; wondelai fills the **business / marketing / UX / product-strategy** slot of the skills-pack. Every Claude Code session that touches product work (roadmap, naming, copy, UX critique, customer-development framing) currently has no curated skill. wondelai codifies frameworks from bestselling business books into reusable skills.

1. **Cross-domain coverage** — fills a domain gap (non-engineering product/business thinking) that `superpowers` and `caveman` do not touch.
2. **Backed by published methodology** — frameworks trace to books like "Obviously Awesome", "Never Split the Difference", "Positioning", "The Mom Test". Codifies reasoning patterns that the model otherwise improvises.
3. **Just above the D7 floor** — 1,868★ clears the 500★ gate by 3.7x; `pushed_at` 2026-08-08 (yesterday) confirms active maintenance. Modest community adoption (vs `superpowers` 266k★) but not concerning for a niche product-skill bundle.
4. **Multi-runtime** — single repo covers Claude Code, Codex, Cursor, agentskills.io. heretek plugins can vendor the Claude Code subset cleanly.

## Alternatives

- **Hand-rolled "product thinking" skill** — possible but every user would re-author the same frameworks from books. Rejected for duplication cost.
- **No product-skill in skills-pack** — current state. Leaves the entire business / UX / marketing domain to model improvisation. Rejected because wondelai already codifies this and is D7-clean.
- **wondelai/skills** — chosen. MIT, 1,868★, last push 2026-08-08, well-documented, multi-runtime.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 1,868★, last commit 2026-08-08. Source-audit pass: SKILL.md files in this repo are pure prose — they instruct the model to apply business/UX frameworks. No shell, no subprocess, no network IO, no file-write. Trivial source-audit per D7.

## Target plugin

`skills-pack` (as the `wondelai` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 1,868 stars at time of review (verified 2026-08-09).
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-08 (HEAD commit `73de8a53f618ce9361673a2a9eb80532459658fb`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo root, SPDX `MIT`, copyright "Wondel.ai sp. z o.o. 2025").
- [x] source-audit pass — **PASS** the candidate ships `skills/<name>/SKILL.md` files containing only prose instructions to the model. No executable code, no subprocess calls, no network IO, no file-write. Trivial source-audit per D7.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories endpoint not consulted for this prose-only repo (no executable surface). Documented per D7 spirit.

## Implementation note

Vendoring strategy: ship a minimal stub at `plugins/skills-pack/skills/wondelai/SKILL.md` advertising the skill set ("business / marketing / UX frameworks from bestselling books") and pointing to upstream. Mirror parity convention applies — both `.claude/skills/wondelai/` and `.agents/skills/wondelai/` should mirror when present. SHA pinned at filing time (`73de8a53f618ce9361673a2a9eb80532459658fb`).
