---
slug: skills-pack-review-work
date: 2026-08-04
status: rejected
---

# review-work (no canonical upstream)

## What

A `review-work` skill that would have the agent act as a thorough, constructive code reviewer — structured PR-style review with a verdict (approve/request changes/comment), per-file findings with line references, severity tags, and a severity-tagged summary. Common concept in the Claude Code skills ecosystem.

## Why considered

Useful in principle: a one-shot slash command that turns the current diff into a structured self-review is a natural heretek primitive, especially for users running heretek without a human reviewer in the loop.

## Alternatives investigated (all failed D7 verification)

Searched for an upstream canonical home using `gh api`, `gh search repos`, `gh search code`, and WebSearch. Results:

1. **`anthropics/skills`** (166,240★, `pushed_at` 2026-07-24) — WebSearch initially surfaced a hit pointing to `anthropics/skills/skills/review-work/SKILL.md`, but **direct API verification failed**: `gh api repos/anthropics/skills/contents/skills/review-work` returns HTTP 404. The top-level `skills/` listing (verified via `gh api repos/anthropics/skills/contents/skills`) returns 17 entries (algorithmic-art, brand-guidelines, canvas-design, claude-api, doc-coauthoring, docx, frontend-design, internal-comms, mcp-builder, pdf, pptx, skill-creator, slack-gif-creator, theme-factory, web-artifacts-builder, webapp-testing, xlsx) — no `review-work`. The WebSearch snippet appears to have been hallucinated. License status also mixed (no top-level LICENSE; README disclaims some skills as "source-available, not open source").
2. **`obra/superpowers`** (266,415★, MIT) — has `requesting-code-review` and `receiving-code-review` (different verbs, different scope) but no `review-work`. Verified via `gh api repos/obra/superpowers/contents/skills`.
3. **`anthropics/claude-code`** (Claude Code's own repo) — has a `code-review` plugin under `plugins/` but the WebSearch snippet that referenced `plugins/plugin-dev/skills/plugin-structure/references/component-patterns.md` mentioned only `code-review-workflow` as an example structure, not a shipped skill. Verified: no `review-work/SKILL.md` shipped in `anthropics/claude-code` either.
4. **`JuliusBrussee/caveman`** — has `caveman-review` as a related skill, but it operates under caveman style, not the general "PR-style structured review" the name implies.
5. **`gh search repos "review-work"`** — top matches are unrelated (`wm94i/Work-Review` 1,687★ MIT — but it's an HR work-review system, not a Claude Code skill; `Chachamaru127/claude-code-harness` 3,042★ MIT — Claude Code harness, not a skill; etc.). None ship a `review-work` Claude Code skill as their primary deliverable.

`review-work` appears to exist only as a concept name or in private/personal collections — no public repo passes D7 verification.

## Verdict

- [ ] Approved
- [x] Rejected

Reason: D7 source provenance cannot be verified — no public repo with ≥ 500★ + OSI-approved license that ships a canonical `review-work/SKILL.md`. WebSearch's apparent hit on `anthropics/skills` was a hallucination (direct API call confirms the file does not exist). Per D7, the absence of a verifiable upstream means the marketplace cannot attest to license / source-audit / CVE status of the skill content. Reject.

The closest *related* skill — `obra/superpowers/requesting-code-review` — is shipped indirectly via the approved `superpowers` item above and provides the same "request a review" workflow that the user would have wanted from `review-work`. The user is not blocked.

## Target plugin

Would target `skills-pack` if approved. Not approved.

## Vetting checklist (D7)

- [ ] stars ≥ 500 — **FAIL** no canonical repo found.
- [ ] last commit ≤ 12 months — **N/A** cannot evaluate without a canonical repo.
- [ ] OSI-approved license — **N/A** cannot evaluate without a canonical repo.
- [ ] source-audit pass — **N/A** cannot evaluate without a canonical repo.
- [ ] no critical CVEs in 24 months — **N/A** cannot evaluate without a canonical repo.

## Implementation note

Re-evaluate if Anthropic ships an official `review-work` skill under Apache 2.0 in `anthropics/skills`. Until then, do not ship. If user demand materializes, an internal heretek-authored skill (vendored under heretek-claude-harness's own license, marked `upstream: Heretek-AI/heretek-claude-harness` per the `hooks` plugin precedent) is the right next step — see the self-vendoring pattern in `catalog/reviews/0000-template.md`.
