---
slug: skills-pack-find-skills
date: 2026-08-04
status: rejected
---

# find-skills (no canonical upstream)

## What

A `find-skills` skill that would let the agent discover and install other agent skills when a user asks "how do I do X" / "is there a skill that can..." / "find a skill for X". Common name in the Claude Code skills ecosystem.

## Why considered

Useful in principle: a meta-skill that helps users extend their Claude Code without knowing what's already installed. Lowers the activation energy for the whole skills-pack concept.

## Alternatives investigated (all failed D7 verification)

Searched for an upstream canonical home using `gh api`, `gh search repos`, `gh search code`, and WebSearch. Results:

1. **`anthropics/skills`** (166,240★, `pushed_at` 2026-07-24) — does NOT contain a `find-skills` directory under `skills/` (verified via `gh api repos/anthropics/skills/contents/skills/find-skills` → 404). The GitHub repo license endpoint returns 404 (no top-level LICENSE; README says "many skills are Apache 2.0" but other skills are explicitly "source-available, not open source"). Mixed-license + no canonical find-skills skill → cannot attest D7 license for a vendored copy.
2. **`obra/superpowers`** (266,415★, MIT) — has 14 skills under `skills/` (brainstorming, dispatching-parallel-agents, executing-plans, finishing-a-development-branch, receiving-code-review, requesting-code-review, subagent-driven-development, systematic-debugging, test-driven-development, using-git-worktrees, using-superpowers, verification-before-completion, writing-plans, writing-skills). No `find-skills` in the list (verified via `gh api repos/obra/superpowers/contents/skills`).
3. **`JuliusBrussee/caveman`** (95,783★, MIT) — no `find-skills`.
4. **`davila7/claude-code-templates`** (30,106★, MIT) — collection of snippets, no `find-skills` skill as a first-class entity.
5. **`gh search repos "find-skills"`** — top matches are unrelated projects: `futantan/agent-skills.md` (238★, no license), `Neeeophytee/finding-unknowns-skills` (298★, "Other" license), `davepoon/buildwithclaude` (3,252★, MIT — but this is a tutorial repo, not the canonical home). All below 500 stars except `buildwithclaude`, which doesn't ship a `find-skills` skill.
6. **`gh search code "find-skills" --owner anthropics`** — zero matches.

`find-skills` appears to exist only as a concept or in a personal/closed collection — no public repo passes D7 verification.

## Verdict

- [ ] Approved
- [x] Rejected

Reason: D7 source provenance cannot be verified — no public repo with ≥ 500★ + MIT/Apache that ships a canonical `find-skills/SKILL.md`. Per D7 vetting bar (which requires a real upstream repo with verifiable license and source-audit), `find-skills` cannot be approved. The skill is also trivially re-implementable inside heretek (a one-paragraph system prompt pointing to `gh` search) so blocking the marketplace on its absence has minimal user impact.

## Target plugin

Would target `skills-pack` if approved. Not approved.

## Vetting checklist (D7)

- [ ] stars ≥ 500 — **FAIL** no canonical repo found. `davepoon/buildwithclaude` (3,252★) is the highest-star match but is a tutorial repo, not a home for the skill.
- [ ] last commit ≤ 12 months — **N/A** cannot evaluate without a canonical repo.
- [ ] OSI-approved license — **N/A** cannot evaluate without a canonical repo.
- [ ] source-audit pass — **N/A** cannot evaluate without a canonical repo.
- [ ] no critical CVEs in 24 months — **N/A** cannot evaluate without a canonical repo.

## Implementation note

Re-evaluate if a canonical upstream appears (e.g., Anthropic ships an official `find-skills` skill in a future `anthropics/skills` release under Apache 2.0). Until then, do not ship.
