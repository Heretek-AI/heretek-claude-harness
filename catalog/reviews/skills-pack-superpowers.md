---
slug: skills-pack-superpowers
date: 2026-08-04
status: approved
---

# obra/superpowers

## What

`superpowers` is an opinionated, MIT-licensed Claude Code **skills framework** and software development methodology. It ships 14 first-party skills under `skills/` (brainstorming, dispatching-parallel-agents, executing-plans, finishing-a-development-branch, receiving-code-review, requesting-code-review, subagent-driven-development, systematic-debugging, test-driven-development, using-git-worktrees, using-superpowers, verification-before-completion, writing-plans, writing-skills) that establish a process discipline ("invoke the relevant skill BEFORE any response, including clarifying questions") and provide repeatable workflows for every phase of an agentic session. The repo is written primarily in Shell (installer + scripts) with Markdown skills. Last commit on `main`: 2026-08-04 (`44c9b2d6e889982ac18c27d05a19fefe335194e1`).

## Why

The heretek `skills-pack` ships a small set of generic (not language-specific) skills that improve every Claude Code session regardless of stack. Superpowers is the strongest available match because:

1. **Process discipline** — the `using-superpowers` skill explicitly instructs the agent to invoke relevant skills BEFORE any response, which prevents the agent from "winging it" on tasks that have a known good workflow. This is the single highest-leverage behavior change heretek can ship in a generic plugin.
2. **Coverage of the SDLC** — brainstorming, planning, TDD, debugging, verification, code-review-request, code-review-receive, subagent-driven-development. Between the 14 first-party skills, almost every phase of a heretek user's day has a corresponding skill.
3. **Massive adoption** — 266,415 stars at time of review, the highest-starred Claude Code skill repo and one of the highest-starred repos on GitHub overall. 23,821 forks. Maintained actively.
4. **MIT + Apache-compatible** — `LICENSE` is MIT, no CLA surprises.
5. **Pairing with heretek layers** — superpowers is process; heretek's hooks layer is gating. They complement each other: superpowers tells the agent to use TDD; heretek's fast-gate verifies the test was actually run before allowing commits.

## Alternatives

- **anthropics/skills** (166,240★) — Anthropic's official skills repo. Apache 2.0 for most skills but no single `LICENSE` file at repo root (GitHub `/license` endpoint returns 404). Per-skill licenses are Apache but the repo is mixed-license (some "source-available, not open source" per the README). Cannot cleanly attest "OSI-approved license" at the repo level for D7.
- **davila7/claude-code-templates** (30,106★) — collection of snippets, not a cohesive methodology. Several aitempl hooks fail source-audit (see `aitmpl-*.md` ADRs in this repo).
- **Hand-rolled process prompts** — possible but each user would re-invent the same TDD/debugging checklists; no community vetting.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 266,415★, last commit 2026-08-04. Source-audit pass: the install path is `install.sh` / `install.ps1` that copies skills into `~/.claude/skills/` (or the project-local `.claude/skills/`); at runtime each skill's `SKILL.md` is read by Claude Code as instructions — there is no always-running daemon, no network IO at skill-execution time, no write outside the workspace. The CLI under `cli/` (which is what `install.sh` calls) is also local-only. No critical CVEs in GitHub Security Advisories for `obra/superpowers`.

## Target plugin

`skills-pack` (as the `superpowers` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 266,415 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD commit `44c9b2d6e889982ac18c27d05a19fefe335194e1`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo root, `license.key = "mit"` in GitHub API response).
- [x] source-audit pass — **PASS** the v1 vendored skill is `using-superpowers` (the entry-point skill that mandates the skill-first discipline). Its `SKILL.md` is pure prose; no shell, no subprocess, no network. Other superpowers skills are also prose-first by design; the `install.sh` / `cli/` code is only invoked at install time (outside the agent loop). Trivial source-audit for the runtime path; install-time path is one-shot and can be SHA-pinned via the repo SHA in `catalog.yaml`.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories endpoint returned zero advisories for `obra/superpowers` at time of review.

## Implementation note

Vendoring strategy for v1 (per brief scope): ship a minimal stub at `plugins/skills-pack/skills/superpowers/SKILL.md` whose `description:` frontmatter advertises "process discipline: invoke relevant skill BEFORE any response" and whose body is a one-paragraph pointer to the upstream `using-superpowers` skill. Vendoring the full upstream skill tree (14 skills × ~200 lines each) is beyond v1 scope; the stub is sufficient for Claude Code to discover the entry-point skill name. Future task can decide whether to vendor the full tree (preferred for users who want the complete methodology without an `install.sh` step) or keep the stub + install-prompt pattern.
