# Roadmap Restructure Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the heretek-claude-harness repo from the current v1.x→v4-vision roadmap structure to the new v2→v6 phased structure defined in `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md`.

**Architecture:** Documentation + GitHub issue actions only. No code changes. The migration produces: (1) a new `docs/superpowers/roadmap.md` as the canonical structure, (2) a migration spec documenting the close/mutate/open sequence, (3) 9 spike ADRs and 3 rejection notes for tri-stated items, (4) 6 phase tracking issues (3 new + 3 mutated), (5) 3 closed issues, (6) a slimmed `PLAN.md`.

**Tech Stack:** Markdown docs, ruamel.yaml-free editing, GitHub MCP for issue actions.

## Global Constraints

- Branch: `learned-walrus` (worktree `/home/john/.paseo/worktrees/2np77f99/learned-walrus`).
- All commits end with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Markdown files use `# h1` for top-level, `## h2` for sections, `### h3` for subsections.
- Use GitHub MCP tools (`mcp__github__*`), NOT `gh` CLI — per `memory:issue-30-issue-drafter-plan.md`.
- ADR template at `catalog/reviews/0000-template.md` is the format for spike ADRs.
- Tri-state promotion rules per spec §8.

---

## Task 1: Write the new roadmap doc

**Files:**
- Create: `docs/superpowers/roadmap.md`

**Interfaces:**
- Consumes: spec sections 3, 4, 5, 9, 10
- Produces: canonical home for the new roadmap structure

- [ ] **Step 1: Create the roadmap doc**

Write `docs/superpowers/roadmap.md` with these sections, copied/condensed from the spec:

```markdown
# Heretek Roadmap

**Status:** Active. Last restructured 2026-08-08.

## Phase Structure

| Phase | Scope | Status |
|---|---|---|
| v1.x | Shipped (frozen) | v1.0.0 in CHANGELOG |
| v2 | Hooks hardening + security | New |
| v3 | MCP/ACI expansion | New |
| v3.5 | Observability | In flight (#109-#124) |
| v4 | Workflow patterns + eval | New |
| v5 | BYOK + local inference | New |
| v6 | Meta-harness + ACP research | New |

## Per-Phase Scope

### v2 — Hooks + Security (✅ 3 / 🔬 1 / ❌ 2)

- ✅ Hooks: graceful tool-output truncation
- ✅ Hooks: JSON payload stdin parsing (cchook-style)
- ✅ Hooks: checkpoint commits + PreCompact squash
- 🔬 Slopsquatting-aware install gate → `docs/superpowers/spikes/2026-08-08-v2-slopsquatting-install-gate.md`
- ❌ AGENTS.md/CLAUDE.md prompt injection scanning → see #70
- ❌ OSV validation → see #52

### v3 — MCP/ACI Expansion (✅ 2 / 🔬 1 / ❌ 0)

- ✅ AutoMCP integration
- ✅ Semantic codebase memory protocol spec
- 🔬 Re-evaluate Context7/Serena ADRs → `docs/superpowers/spikes/2026-08-08-v3-context7-serena-audit.md`

### v3.5 — Observability (in flight)

- #109-#113 collector
- #114-#118 test pipeline
- #119-#124 eval harness

### v4 — Workflow + Eval (✅ 3 / 🔬 1 / ❌ 0)

- ✅ Orchestrator-Workers + Plan-then-Execute
- ✅ Parallelization (voting/sectioning)
- ✅ Terminal-Bench 2.1 evaluation harness
- 🔬 Prompt chaining → `docs/superpowers/spikes/2026-08-08-v4-prompt-chaining.md`

### v5 — BYOK + Local (✅ 0 / 🔬 2 / ❌ 1)

- 🔬 BYOK endpoint abstraction → `docs/superpowers/spikes/2026-08-08-v5-byok-abstraction.md`
- 🔬 Local inference (ROCm/Vulkan/KV cache) → `docs/superpowers/spikes/2026-08-08-v5-local-inference.md`
- ❌ Vendor-specific hardware recommendations → see rejection notes

### v6 — Meta-Harness + ACP (✅ 0 / 🔬 4 / ❌ 0)

- 🔬 Meta-harness self-rewrite loop → `docs/superpowers/spikes/2026-08-08-v6-meta-harness.md`
- 🔬 ACP research/design doc → `docs/superpowers/spikes/2026-08-08-v6-acp-research.md`
- 🔬 Session forking → `docs/superpowers/spikes/2026-08-08-v6-emerging-patterns.md`
- 🔬 AgentPool bidirectional ACP → `docs/superpowers/spikes/2026-08-08-v6-emerging-patterns.md`

## Phase-Done Definitions

- **v2:** hooks hardening ADRs merged, fast_gate covers new patterns, no regression on existing tests.
- **v3:** AutoMCP integration smoke-tested, semantic memory protocol spec published.
- **v3.5:** harness-observability #109-#124 closed, smoke test green.
- **v4:** workflow patterns ADRs merged, evaluator-optimizer running against harness fixtures, TB 2.1 score recorded.
- **v5:** BYOK endpoint switched in test harness, local inference smoke test on reference hardware.
- **v6:** meta-harness loop demonstrably improves harness metric on a held-out task.

## Rollout Cadence

v2 → v3 (sequential) || v3.5 (parallel from now) → v4 (gated on v3.5 eval) → v5/v6 (research-only).

## Cross-references

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md`
- Migration spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md`
- Rejection notes: `docs/superpowers/roadmap-rejected-candidates.md`
- Spike ADRs: `docs/superpowers/spikes/2026-08-08-*.md`
```

- [ ] **Step 2: Verify the file**

Run: `wc -l docs/superpowers/roadmap.md`
Expected: 60-80 lines.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/roadmap.md
git commit -m "docs(roadmap): add new v2-v6 phased roadmap structure"
```

---

## Task 2: Write the migration spec

**Files:**
- Create: `docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md`

**Interfaces:**
- Consumes: spec section 7 (issue migration)
- Produces: executable close/mutate/open sequence

- [ ] **Step 1: Create the migration spec**

Write `docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md`:

```markdown
# Roadmap Restructure — Migration Spec

**Date:** 2026-08-08
**Purpose:** Close out the old v1.x→v4-vision tracking structure and open the new v3.5/v5/v6 phase tracking issues.

## Pre-conditions

- New `docs/superpowers/roadmap.md` exists (Task 1).
- All 9 spike ADRs exist (Task 3).
- All rejection notes exist (Task 3).
- `PLAN.md` slimmed (Task 4).

## Issue Migration Sequence

### Close (3 issues)

1. **#87 [ROADMAP] All open issues prioritized index** → close as completed. Add comment:

   > Replaced by `docs/superpowers/roadmap.md` (canonical home for the new v2-v6 phased roadmap). See migration spec `docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md`.

2. **#88 v1.x (active maintenance + v1.1 hardening)** → close as completed (`state_reason: completed`). Add comment:

   > v1.0.0 shipped 2026-08-05 (CHANGELOG). Phase frozen; v1.x maintenance continues via PR-by-PR triage rather than a tracking issue.

3. **#92 cross-cutting: long-term test of 4 ideation approaches** → keep open, reassign to v4. Add comment:

   > Reassigned to v4 (workflow + eval). Cross-cutting ideation measurement continues; v4 phase tracking now at the mutated #91.

### Mutate (3 issues)

4. **#89 v2: backlog (new plugins, packs, tooling)** → update title to `v2: hooks hardening + security`. Update body to match the v2 scope from `docs/superpowers/roadmap.md` (3 ✅ + 1 🔬 + 2 ❌, 2 sub-specs: v2-a hooks hardening, v2-b security hardening).

5. **#90 v3: freshness enforcement, model cards, tokens** → update title to `v3: MCP/ACI expansion`. Update body to match the v3 scope (2 ✅ + 1 🔬, 2 sub-specs: v3-a MCP server expansion, v3-b catalog MCP audit).

6. **#91 v4-vision: spike research** → update title to `v4: workflow + eval`. Update body to match the v4 scope (3 ✅ + 1 🔬, 2 sub-specs: v4-a workflow patterns, v4-b Terminal-Bench 2.1 evaluation harness). Note that #92 cross-cutting test is reassigned here.

### Open (3 new issues)

7. **v3.5: observability** (parent of #109-#124) → use the `tracking` label. Body: scope, sub-specs list, acceptance criteria from `docs/superpowers/roadmap.md` §v3.5.

8. **v5: BYOK + local inference** → use the `tracking` label. Body: scope, sub-specs list (v5-a BYOK, v5-b local inference), acceptance criteria.

9. **v6: meta-harness + ACP research** → use the `tracking` label. Body: scope, sub-specs list (v6-a meta-harness, v6-b ACP, v6-c emerging patterns), acceptance criteria.

## Execution Order

Tasks 5-7 implement this spec. Sequence: open new issues first (so they exist before mutations), then mutate existing, then close.

## Verification

After all 9 actions:
- 6 phase tracking issues exist with `tracking` label
- 3 closed issues (#87, #88 done; #92 open with reassignment comment)
- 0 untracked v1.x→v4-vision references in new artifacts
```

- [ ] **Step 2: Verify the file**

Run: `wc -l docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md`
Expected: 50-70 lines.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md
git commit -m "docs(spec): roadmap restructure migration spec"
```

---

## Task 3: Write rejection notes + 9 spike ADRs

**Files:**
- Create: `docs/superpowers/roadmap-rejected-candidates.md`
- Create: `docs/superpowers/spikes/2026-08-08-v2-slopsquatting-install-gate.md`
- Create: `docs/superpowers/spikes/2026-08-08-v3-context7-serena-audit.md`
- Create: `docs/superpowers/spikes/2026-08-08-v4-prompt-chaining.md`
- Create: `docs/superpowers/spikes/2026-08-08-v5-byok-abstraction.md`
- Create: `docs/superpowers/spikes/2026-08-08-v5-local-inference.md`
- Create: `docs/superpowers/spikes/2026-08-08-v6-meta-harness.md`
- Create: `docs/superpowers/spikes/2026-08-08-v6-acp-research.md`
- Create: `docs/superpowers/spikes/2026-08-08-v6-emerging-patterns.md`

**Interfaces:**
- Consumes: ADR template at `catalog/reviews/0000-template.md`
- Produces: tri-state records for all 12 items

- [ ] **Step 1: Write rejection notes**

Create `docs/superpowers/roadmap-rejected-candidates.md`:

```markdown
# Roadmap Restructure — Rejected Candidates

Generated 2026-08-08 from `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.

## v2

- **AGENTS.md/CLAUDE.md prompt injection scanning** — rejected as duplicate. Already on roadmap via #70 (forbidden-pattern registry).
- **OSV validation in install path** — rejected as duplicate. Already on roadmap via #52 (dependabot verify).

## v5

- **Vendor-specific hardware recommendations (AMD ROCm 7, Vulkan, etc.)** — rejected as out of scope. heretek marketplace is at the abstraction layer; vendor-specific recommendations live with the user, not the catalog.
```

- [ ] **Step 2: Write the v2 spike ADR**

Create `docs/superpowers/spikes/2026-08-08-v2-slopsquatting-install-gate.md` using the ADR template format from `catalog/reviews/0000-template.md`:

```markdown
# v2: Slopsquatting-aware install gate

**Status:** 🔬 Spike
**Phase:** v2 (hooks + security)
**Date:** 2026-08-08

## Research question

Can we intercept `pip install` and `npm install` calls in the hooks plugin to validate package names against OSV-Scanner before allowing the install to proceed?

## Why

"Slopsquatting" — agents hallucinate package names; threat actors pre-register those names on PyPI/npm. The agent then unknowingly installs malware.

## Deliverable

- Spike: integrate OSV-Scanner into the hooks plugin's PreToolUse path for Bash commands matching install patterns.
- Decision criteria for promotion to ✅: prototype detects at least one known hallucinated package + integrates with existing fast_gate pattern.

## Evidence

- Doc 2 (Command Line Coding Agents Audit) cite #51 (DZone, Slopsquatting).
- Existing #70 (forbidden-pattern registry) covers post-install scanning; this is the pre-install gate.

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.1
- Roadmap: `docs/superpowers/roadmap.md` §v2
```

- [ ] **Step 3: Write the v3 spike ADR**

Create `docs/superpowers/spikes/2026-08-08-v3-context7-serena-audit.md`:

```markdown
# v3: Context7/Serena ADR re-evaluation

**Status:** 🔬 Spike
**Phase:** v3 (MCP/ACI expansion)
**Date:** 2026-08-08

## Research question

Do the Context7 and Serena MCP server ADRs in `catalog/reviews/` (filed 2026-08-04) still represent best practice given Qwen Code's Architect/Editor pattern (2026)?

## Why

Doc 2 (CLI Coding Agents Audit) cite #24 highlights the Architect/Editor pattern as solving hallucination-execution loops. Our existing Serena ADR may predate this insight.

## Deliverable

- Audit report comparing Context7 + Serena interfaces to the Qwen Code pattern.
- Decision criteria for promotion: re-validate interface contracts OR file spec change requests.

## Evidence

- Doc 2 cite #24 (QwenLM/qwen-code discussion #8340).
- Existing ADRs: `catalog/reviews/mcp-pack-context7.md`, `catalog/reviews/mcp-pack-serena.md`.

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.2
- Roadmap: `docs/superpowers/roadmap.md` §v3
```

- [ ] **Step 4: Write the v4 spike ADR**

Create `docs/superpowers/spikes/2026-08-08-v4-prompt-chaining.md`:

```markdown
# v4: Prompt chaining decomposition utilities

**Status:** 🔬 Spike
**Phase:** v4 (workflow + eval)
**Date:** 2026-08-08

## Research question

Should prompt chaining (Doc 1 §Vector 4) be a first-class utility in the heretek harness, or is it subsumed by subagent delegation?

## Why

Prompt chaining decomposes a task into sequential LLM calls. Subagent delegation does the same thing with isolation. Trade-off: chaining shares context (efficient); subagents get fresh context (clean).

## Deliverable

- Decision document comparing chaining vs subagents in the heretek context.
- Decision criteria for promotion: clear use case where chaining beats subagents, OR explicit defer with rationale.

## Evidence

- Doc 1 cite #18 (Anthropic "Building Effective Agents" 5 patterns).
- Doc 2 cite #24 (Qwen Code Architect/Editor uses chaining in the Planner→Coder path).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.4
- Roadmap: `docs/superpowers/roadmap.md` §v4
```

- [ ] **Step 5: Write the v5 spike ADRs**

Create `docs/superpowers/spikes/2026-08-08-v5-byok-abstraction.md`:

```markdown
# v5: BYOK endpoint abstraction layer

**Status:** 🔬 Spike
**Phase:** v5 (BYOK + local)
**Date:** 2026-08-08

## Research question

Can we add a Bring-Your-Own-Key (BYOK) abstraction to the heretek marketplace that allows routing inference to OpenAI-compatible endpoints, local Ollama, or specialized coding models?

## Why

Doc 1 §Vector 3 + Doc 2 cite #39 (GDevelop-BYOK issue #7932) describe demand for endpoint-agnostic harnesses.

## Deliverable

- Spike: identify the Claude Code API surface that would need abstraction.
- Decision criteria: prototype routes a non-Anthropic model through the marketplace hooks without breakage.

## Evidence

- Doc 1 §Vector 3 (BYOK paradigm).
- Doc 2 cite #39 (GDevelop-BYOK feature request).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.5
- Roadmap: `docs/superpowers/roadmap.md` §v5
```

Create `docs/superpowers/spikes/2026-08-08-v5-local-inference.md`:

```markdown
# v5: Local inference (ROCm/Vulkan/KV cache reuse)

**Status:** 🔬 Spike
**Phase:** v5 (BYOK + local)
**Date:** 2026-08-08

## Research question

What is the minimum hardware spec for running the heretek harness against a local inference backend, and what backend (llama.cpp, CachyLLama, Ollama) is most compatible?

## Why

Doc 1 §Vector 3 cites lemonade-cachy-build and AMD ROCm 7 / Vulkan backends as the path for low-spec hardware acceleration.

## Deliverable

- Spike: benchmark heretek harness against 3 candidate local inference backends on a reference hardware configuration.
- Decision criteria: tokens/sec > 5 sustained + KV cache reuse demonstrably reduces latency.

## Evidence

- Doc 1 §Vector 3 (BYOK + local).
- Doc 1 cite #41 (lemonade-cachy-build issue #2471).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.5
- Roadmap: `docs/superpowers/roadmap.md` §v5
```

- [ ] **Step 6: Write the v6 spike ADRs**

Create `docs/superpowers/spikes/2026-08-08-v6-meta-harness.md`:

```markdown
# v6: Meta-harness self-rewrite loop

**Status:** 🔬 Spike
**Phase:** v6 (meta-harness + ACP)
**Date:** 2026-08-08

## Research question

Can a meta-harness loop — reading uncompressed filesystem traces + proposing harness rewrites — improve heretek harness metrics on held-out tasks?

## Why

Doc 1 §Vector 5 (Meta-Harness) frames this as the path past hand-crafted harness performance ceilings.

## Deliverable

- Spike: scope report on harness-as-code boundaries + causal intervention learning feasibility.
- Decision criteria: prototype loop improves TB 2.1 score by ≥ 2pp on a held-out task set.

## Evidence

- Doc 1 §Vector 5 (Meta-Harness optimization paradigm).
- Doc 1 cite #17 (Meta-Harness paper, arXiv).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.6
- Roadmap: `docs/superpowers/roadmap.md` §v6
```

Create `docs/superpowers/spikes/2026-08-08-v6-acp-research.md`:

```markdown
# v6: ACP (Agent Client Protocol) research

**Status:** 🔬 Spike
**Phase:** v6 (meta-harness + ACP)
**Date:** 2026-08-08

## Research question

Is the Agent Client Protocol (ACP) stable enough to integrate with heretek marketplace, or should heretek remain MCP-only for now?

## Why

Doc 2 §ACP describes ACP as Zed-originated, now Linux Foundation. Adoption by JetBrains, Google, GitHub suggests industry alignment. But OpenClaw wrappers show "protocol drift" problems (Doc 2 cite #9).

## Deliverable

- Spike: protocol stability assessment + integration vs monitoring decision.
- Decision criteria: explicit go/no-go with rationale.

## Evidence

- Doc 2 §ACP vs MCP.
- Doc 2 cite #9 (OpenClaw protocol gaps audit).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.6
- Roadmap: `docs/superpowers/roadmap.md` §v6
```

Create `docs/superpowers/spikes/2026-08-08-v6-emerging-patterns.md`:

```markdown
# v6: Emerging patterns (session forking + AgentPool)

**Status:** 🔬 Spike
**Phase:** v6 (meta-harness + ACP)
**Date:** 2026-08-08

## Research question

Do session forking (Kimi Code) and AgentPool bidirectional ACP (Stakpak) map onto Claude Code's session model and heretek's hook architecture?

## Why

Doc 2 cite #30 (Kimi Code session forking) and cite #39 (Stakpak AgentPool) describe patterns from competitors. Worth assessing for heretek applicability.

## Deliverable

- Spike: compatibility report for each pattern against Claude Code's session API + heretek hook architecture.
- Decision criteria: explicit adopt/reject with rationale.

## Evidence

- Doc 2 cite #30 (Kimi Code CLI).
- Doc 2 cite #39 (Stakpak AgentPool).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.6
- Roadmap: `docs/superpowers/roadmap.md` §v6
```

- [ ] **Step 7: Verify all files exist**

Run:
```bash
ls -1 docs/superpowers/roadmap-rejected-candidates.md docs/superpowers/spikes/2026-08-08-*.md
```
Expected: 10 files (1 rejection + 9 spikes).

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/roadmap-rejected-candidates.md docs/superpowers/spikes/
git commit -m "docs(spikes): 9 spike ADRs + rejection notes for roadmap restructure"
```

---

## Task 4: Slim PLAN.md

**Files:**
- Modify: `PLAN.md`

**Interfaces:**
- Consumes: existing `PLAN.md` content
- Produces: one-page TL;DR + cross-references

- [ ] **Step 1: Replace PLAN.md content**

Replace `PLAN.md` content with:

```markdown
# Heretek Marketplace — Plan

> One-page TL;DR. Full roadmap at `docs/superpowers/roadmap.md`. Design spec at `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md`.

## Status

v1.0.0 shipped 2026-08-05 (CHANGELOG). v1.x frozen.

## Active phases

| Phase | Scope | Tracking |
|---|---|---|
| v2 | Hooks + security | #89 |
| v3 | MCP/ACI | #90 |
| v3.5 | Observability (in flight) | #109-#124 + new tracking issue |
| v4 | Workflow + eval | #91 |
| v5 | BYOK + local | new tracking issue |
| v6 | Meta-harness + ACP | new tracking issue |

## Common commands

```bash
pytest -q
python scripts/validate.py
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json
```

## See also

- `docs/superpowers/roadmap.md` — phased roadmap
- `docs/superpowers/specs/` — design specs
- `docs/superpowers/plans/` — implementation plans
- `catalog/` — source of truth for plugin catalog
- `CONTRIBUTING.md` — contribution guide
- `SECURITY.md` — security reporting
```

- [ ] **Step 2: Verify the file**

Run: `wc -l PLAN.md`
Expected: ≤ 40 lines.

- [ ] **Step 3: Commit**

```bash
git add PLAN.md
git commit -m "docs(plan): slim PLAN.md to TL;DR + cross-references"
```

---

## Task 5: Open 3 new phase tracking issues

**Files:** None (GitHub actions only).

**Interfaces:**
- Consumes: scope/acceptance text from `docs/superpowers/roadmap.md`
- Produces: 3 new GitHub issues with `tracking` label

- [ ] **Step 1: Open v3.5 tracking issue**

Use `mcp__github__github-issue_write` with:
- `method`: `create`
- `owner`: `Heretek-AI`
- `repo`: `heretek-claude-harness`
- `title`: `v3.5: observability (in flight)`
- `labels`: `["tracking"]`
- `body`:

```markdown
## Phase: v3.5 — Observability

**Parent:** roadmap doc at `docs/superpowers/roadmap.md` §v3.5.

## Scope

Sub-specs already filed 2026-08-08:
- #109-#113 collector
- #114-#118 test pipeline
- #119-#124 eval harness

## Acceptance criteria

- All #109-#124 closed.
- Smoke test green against the new eval harness.
- No regression on existing fast_gate / quality_gate coverage.

## Cross-references

- Spec: `docs/superpowers/specs/2026-08-08-harness-observability-design.md`
- Migration: `docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md`
```

- [ ] **Step 2: Open v5 tracking issue**

Use `mcp__github__github-issue_write` with:
- `title`: `v5: BYOK + local inference`
- `labels`: `["tracking"]`
- `body`:

```markdown
## Phase: v5 — BYOK + Local Inference

**Parent:** roadmap doc at `docs/superpowers/roadmap.md` §v5.

## Scope

Spike items:
- 🔬 v5-a BYOK endpoint abstraction → `docs/superpowers/spikes/2026-08-08-v5-byok-abstraction.md`
- 🔬 v5-b Local inference (ROCm/Vulkan/KV cache) → `docs/superpowers/spikes/2026-08-08-v5-local-inference.md`

Rejected (out of scope): vendor-specific hardware recommendations.

## Acceptance criteria

- BYOK endpoint switched in test harness against a non-Anthropic model.
- Local inference smoke test on reference hardware (sustained > 5 tokens/sec).
- No regression on Claude Code (Anthropic) path.

## Cross-references

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.5
- Roadmap: `docs/superpowers/roadmap.md` §v5
```

- [ ] **Step 3: Open v6 tracking issue**

Use `mcp__github__github-issue_write` with:
- `title`: `v6: meta-harness + ACP research`
- `labels`: `["tracking"]`
- `body`:

```markdown
## Phase: v6 — Meta-Harness + ACP Research

**Parent:** roadmap doc at `docs/superpowers/roadmap.md` §v6.

## Scope

Spike items:
- 🔬 v6-a Meta-harness self-rewrite loop → `docs/superpowers/spikes/2026-08-08-v6-meta-harness.md`
- 🔬 v6-b ACP research/design doc → `docs/superpowers/spikes/2026-08-08-v6-acp-research.md`
- 🔬 v6-c Emerging patterns (session forking, AgentPool) → `docs/superpowers/spikes/2026-08-08-v6-emerging-patterns.md`

## Acceptance criteria

- Meta-harness loop demonstrably improves harness metric on a held-out task.
- ACP go/no-go decision documented.
- Compatibility report on session forking + AgentPool against Claude Code.

## Cross-references

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.6
- Roadmap: `docs/superpowers/roadmap.md` §v6
```

- [ ] **Step 4: Verify**

Run: `gh issue list --repo Heretek-AI/heretek-claude-harness --label tracking --state open`
Expected: 7+ issues (3 new + existing v1.x-v4-vision).

---

## Task 6: Mutate 3 existing tracking issues

**Files:** None (GitHub actions only).

**Interfaces:**
- Consumes: existing #89, #90, #91 content
- Produces: mutated titles + bodies matching new scope

- [ ] **Step 1: Mutate #89 (v2)**

Use `mcp__github__github-update_pull_request` — wait, that's for PRs. Use `mcp__github__github-issue_write` with `method: update`:

```
issue_number: 89
owner: Heretek-AI
repo: heretek-claude-harness
title: v2: hooks hardening + security
body: [match roadmap.md §v2]
labels: ["tracking"]
```

- [ ] **Step 2: Mutate #90 (v3)**

Same pattern:
```
issue_number: 90
title: v3: MCP/ACI expansion
body: [match roadmap.md §v3]
labels: ["tracking"]
```

- [ ] **Step 3: Mutate #91 (v4)**

Same pattern:
```
issue_number: 91
title: v4: workflow + eval
body: [match roadmap.md §v4]
labels: ["tracking"]
```

- [ ] **Step 4: Verify**

Read each issue via `mcp__github__github-issue_read` and confirm title + body match the new scope.

---

## Task 7: Close 2 issues + comment on #92

**Files:** None (GitHub actions only).

**Interfaces:**
- Consumes: closure rationale from migration spec §"Close"
- Produces: 2 closed issues, 1 commented issue

- [ ] **Step 1: Close #87**

Use `mcp__github__github-issue_write`:
```
method: update
issue_number: 87
state: closed
state_reason: completed
```

Then `mcp__github__github-add_issue_comment` with:
```
Replaced by `docs/superpowers/roadmap.md` (canonical home for the new v2-v6 phased roadmap). See migration spec `docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md`.
```

- [ ] **Step 2: Close #88**

Same pattern with `state_reason: completed`. Comment:
```
v1.0.0 shipped 2026-08-05 (CHANGELOG). Phase frozen; v1.x maintenance continues via PR-by-PR triage rather than a tracking issue.
```

- [ ] **Step 3: Comment on #92 (reassignment)**

Use `mcp__github__github-add_issue_comment`:
```
Reassigned to v4 (workflow + eval). Cross-cutting ideation measurement continues; v4 phase tracking now at the mutated #91.
```

Do NOT close #92 — keep open per migration spec.

- [ ] **Step 4: Verify**

Read #87, #88, #92 via `mcp__github__github-issue_read` and confirm state + comments.

---

## Task 8: Final verification

**Files:** None.

- [ ] **Step 1: Verify roadmap doc**

Run:
```bash
test -f docs/superpowers/roadmap.md && wc -l docs/superpowers/roadmap.md
```
Expected: file exists, 60-80 lines.

- [ ] **Step 2: Verify migration spec**

Run:
```bash
test -f docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md && wc -l docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md
```
Expected: file exists, 50-70 lines.

- [ ] **Step 3: Verify rejection notes + spike ADRs**

Run:
```bash
ls docs/superpowers/roadmap-rejected-candidates.md docs/superpowers/spikes/2026-08-08-*.md | wc -l
```
Expected: 10.

- [ ] **Step 4: Verify PLAN.md slimmed**

Run: `wc -l PLAN.md`
Expected: ≤ 40 lines.

- [ ] **Step 5: Verify GitHub issues**

List open `tracking` issues via `mcp__github__github-list_issues`:
- `owner`: `Heretek-AI`
- `repo`: `heretek-claude-harness`
- `state`: `OPEN`
- `labels`: `["tracking"]`

Expected: at least 6 (3 mutated + 3 new).

List closed issues today via `mcp__github__github-list_issues`:
- `state`: `CLOSED`
- (filter results to today's `updated_at`)

Expected: at least #87, #88.

- [ ] **Step 6: Verify #92 still open with reassignment**

Read #92 — confirm state is `open` and the reassignment comment is present.

- [ ] **Step 7: Verify spec→plan→migration traceability**

Run:
```bash
grep -l "2026-08-08-roadmap-restructure-design" docs/superpowers/roadmap.md docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md PLAN.md
```
Expected: all 3 files reference the spec.

- [ ] **Step 8: Final commit (if any uncommitted changes)**

```bash
git status --short
```
If clean, no commit needed. If changes, commit with appropriate message.

---

## Self-Review

**1. Spec coverage:**

- §3 Phase structure → Task 1 (roadmap.md), Task 5 (open new tracking), Task 6 (mutate existing).
- §4 Per-phase scope → Task 1 (roadmap.md), Task 3 (spike ADRs + rejection notes).
- §5 Sub-spec decomposition → Task 1 (roadmap.md references 14 sub-specs).
- §6 Tracking artifacts → Task 1, 2, 4, 5, 6, 7.
- §7 Issue migration → Task 2 (migration spec), Tasks 5-7 (execution).
- §8 Validation rules → embedded in Task 3 spike ADRs.
- §9 Phase-done definitions → Task 1 (roadmap.md §Phase-Done).
- §10 Rollout cadence → Task 1 (roadmap.md §Rollout).
- §11 Open questions → handled via comments in Task 7.

**2. Placeholder scan:**

No "TBD", "TODO", "implement later" anywhere. Each step contains concrete content (file paths, code, command syntax, GitHub MCP call shapes).

**3. Type consistency:**

Consistent terminology throughout: "phase tracking issue", "spike ADR", "rejection notes", "migration spec". File paths match the spec's section references.
