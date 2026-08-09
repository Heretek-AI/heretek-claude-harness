---
name: research-doc-vetter
description: Use when assessing an external research document (white paper, audit, vendor benchmark, AI-generated analysis) before integrating its recommendations into a roadmap, spec, or plan. Triggers on uploaded docs with citations, forward-dated arXiv IDs, vendor benchmarks, or speculative architecture claims. Also use when an upload's cited repos, model names, or protocol versions are unverified.
---

# Research Document Vetter

## Overview

Treat every substantive claim in an external research doc as a hypothesis to verify before encoding it. The dominant failure mode is **encoding speculative architecture as committed roadmap items** — the doc looks authoritative, but its citations are forward-dated, its benchmarks are unverifiable, and its "X is best practice" recommendations are vendor marketing.

## The Tri-State Pattern

| State | When | Outcome |
|---|---|---|
| **✅ Adopt** | Verified citation (real repo, reproducible benchmark, citable paper) + clear acceptance criteria | Add to roadmap with citation + D7 pass |
| **🔬 Spike** | At least one source, but no reproducible benchmark OR D7 pending OR scope unclear | Write ADR with research question + promotion criteria |
| **❌ Reject** | Hallucinated citation, duplicate of existing work, or out of scope | Note in rejection log with one-line reason |

## Five Triage Questions

Before recording any claim as ✅ adopt:

1. **Citation exists?** Does `github.com/owner/repo` resolve? Last commit recent?
2. **Date plausible?** Are arXiv IDs reasonable for the current date? (Doc from 2026-08 citing `2607.xxxxx` = paper doesn't exist yet.)
3. **Reproducible?** Specific benchmark number (rerunnable) or handwavy ("up to 12–17 percentage points")?
4. **Methodology shown?** Does the author show their work, or just assert?
5. **Net-new?** Will encoding this add new work, or duplicate existing tracked work?

## Red Flags — Treat Speculative Until Verified

- arXiv IDs with month/year in the future at evaluation time
- GitHub repos that don't resolve or last-commit > 12 months ago
- Benchmarks for model names not in the public catalog
- "Up to X% improvement" with no methodology citation
- Forward references to "upcoming" papers/posts that don't exist yet
- Self-citation loops (authors citing their own prior work to bootstrap authority)

## Output Format

Per-claim table:

```
| Claim | Source | Verified? | Tri-state |
|---|---|---|---|
| AutoMCP for REST→MCP | github.com/jroakes/AutoMCP | ✅ exists, recent | ✅ adopt |
| TB 2.1 score 88% for Opus 5 | tbench.ai leaderboard | ✅ matches table | ✅ adopt |
| arXiv 2607.xxxxx | arxiv.org/abs/2607.xxxxx | ❌ doesn't exist | ❌ reject |
| "industry consensus" | none | ❌ no source | 🔬 spike |
```

**Scope summary**: "Of N claims, X ✅ adopt, Y 🔬 spike, Z ❌ reject. Net-new from documents: N' candidates requiring new sub-specs, ADRs, or rejection notes."

## When NOT to Use

- Academic papers with formal peer review (already vetted upstream)
- First-party deliverables from this project
- Documents already tri-stated (reuse the existing record)

## Common Mistakes

- Taking cited URLs at face value — citations are hypotheses
- "Trends toward X" ≠ "X is true" — forward-looking claims are not evidence
- Skipping repo existence checks (two API calls prevent fictional projects)
- Encoding recommendations as commitments — "might be a good approach" ≠ "must be done"
- Trusting academic tone over reproduced numbers — most surveys are summaries, not primary sources
- Promoting spikes to adopt prematurely — the ADR exists to defer the decision
