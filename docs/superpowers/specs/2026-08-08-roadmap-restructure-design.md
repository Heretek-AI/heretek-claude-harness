# Roadmap Restructure — v2 through v6 Phased Plan

**Date:** 2026-08-08
**Status:** Draft (awaiting user review)
**Trigger:** Review of two uploaded documents — `Improving Claude Agent Harness.md` and `Command Line Coding Agents Audit.md` — against the existing 55-issue backlog and the in-flight harness-observability workstream.

## 1. Purpose

Replace the existing v1.x→v4-vision phase structure with a restructured v2→v6 phased roadmap that absorbs strategic vectors surfaced by the two documents, while preserving the in-flight harness-observability workstream as its own lane.

**Inputs reviewed:**
- `Improving Claude Agent Harness.md` — ETCLOVG taxonomy mapping + 5 strategic vectors
- `Command Line Coding Agents Audit.md` — 2026 CLI agent landscape audit (Claude Code, Factory Droid, Qwen Code, OpenCode, Kimi Code, Hermes, Stakpak, Kaku, DeepSeek-Reasonix)

**Outputs:**
- `docs/superpowers/roadmap.md` — top-level roadmap (replaces this spec's role post-adoption)
- 14-15 themed sub-specs across 6 phases
- 6 phase tracking issues (replacing #87-#92)
- Per-phase implementation plans

## 2. Decisions Locked

| # | Decision | Choice |
|---|---|---|
| D-R1 | Scope of roadmap update | Full rewrite |
| D-R2 | Phase restructure | Full restructure: v1.x frozen, v2-v6 new |
| D-R3 | Document trust | Tri-state validation per candidate |
| D-R4 | Harness-observability placement | Own lane, slotted as v3.5 |
| D-R5 | Sub-spec granularity | Themed: 2-3 sub-specs per phase (~14-15 total) |
| D-R6 | Tracking artifacts | Roadmap doc + 6 phase tracking issues + sub-specs |
| D-R7 | Issue migration | Close #87/#88/#92, mutate #89/#90/#91, open new v3.5/v5/v6 |

## 3. Phase Structure

```
v1.x  (shipped)              ← frozen, v1.0.0 in CHANGELOG
v2    (hooks + security)     ← highest priority post-v1.x
v3    (MCP/ACI expansion)    ← catalog breadth
v3.5  (observability)        ← in-flight, #109-#124 stays as-is
v4    (workflow + eval)      ← Anthropic patterns + TB 2.1
v5    (BYOK + local)         ← hardware flexibility
v6    (meta-harness + ACP)   ← long-horizon research
```

**Rationale:**
- v2 ships closest to existing architecture (fast_gate, quality_gate hooks) — lowest risk
- v3 ships catalog breadth before workflow complexity pays off
- v3.5 observability is required infra for v4 (eval harness needs the collector)
- v4 evaluation gives empirical evidence for v5 (BYOK) and v6 (meta-harness) decisions
- v5/v6 are research-heavy; deferred by design

## 4. Per-Phase Scope (Tri-state)

Tri-state key: **✅ adopt** (evidence strong) / **🔬 spike** (needs research) / **❌ reject** (duplicate or evidence fails).

### 4.1 v2 — hooks + security

| Item | State | Evidence |
|---|---|---|
| Hooks: graceful tool-output truncation (PostToolUse, parse BashOutput) | ✅ | Doc 1 §Vector 1 + reverse-engineering harness paper (real, reproducible) |
| Hooks: JSON payload stdin parsing (cchook-style conditional exec) | ✅ | syou6162/cchook — real repo, established pattern |
| Hooks: checkpoint commits + PreCompact squash | ✅ | Real workflow pattern from Claude Code community |
| Slopsquatting-aware install gate (PyPI/npm validation) | 🔬 | DZone article only — needs spike on OSV-Scanner integration |
| AGENTS.md/CLAUDE.md prompt injection scanning | ❌ | Already on roadmap via #70 forbidden-pattern registry |
| OSV validation in install path | ❌ | Already on roadmap via #52 dependabot verify |

### 4.2 v3 — MCP/ACI expansion

| Item | State | Evidence |
|---|---|---|
| AutoMCP for dynamic REST-to-MCP wrapping | ✅ | jroakes/AutoMCP — real repo, needs D7 pass |
| Semantic codebase memory protocol standardization | ✅ | Serena already in `mcp-pack` ADRs; promote to first-class protocol spec |
| Re-evaluate shipped Context7/Serena ADRs against 2026 best practice | 🔬 | Qwen Code Architect/Editor pattern (real) — spike on Serena interface match |

### 4.3 v3.5 — observability (in flight)

| Item | State | Evidence |
|---|---|---|
| Collector (#109-#113) | ✅ | Filed 2026-08-08 |
| Test pipeline (#114-#118) | ✅ | Filed 2026-08-08 |
| Eval harness (#119-#124) | ✅ | Filed 2026-08-08 |

Terminal-Bench 2.1 evaluation harness is canonical in **v4-b** (Section 4.4); not duplicated here.

### 4.4 v4 — workflow + eval

| Item | State | Evidence |
|---|---|---|
| Orchestrator-Workers + Plan-then-Execute | ✅ | Doc 1 §Vector 4 + Qwen Code Architect/Editor — well-documented pattern |
| Parallelization (voting/sectioning) | ✅ | Anthropic "Building Effective Agents" — established pattern |
| Terminal-Bench 2.1 evaluation harness | ✅ | laude-institute/terminal-bench — real benchmark; canonical home for TB integration |
| Prompt chaining decomposition utilities | 🔬 | Doc 1 §Vector 4 — spike on chains-vs-subagents trade-off |

### 4.5 v5 — BYOK + local

| Item | State | Evidence |
|---|---|---|
| BYOK endpoint abstraction layer | 🔬 | GDevelop-BYOK issue #7932 — spike on Claude Code API surface |
| Local inference (ROCm/Vulkan/KV cache reuse) | 🔬 | lemonade-cachy-build — needs hardware spike |
| Vendor-specific hardware recommendations | ❌ | Too speculative; spec lives at abstraction layer |

### 4.6 v6 — meta-harness + ACP

| Item | State | Evidence |
|---|---|---|
| Meta-harness self-rewrite loop | 🔬 | Doc 1 §Vector 5 — research-stage; defer to last phase |
| ACP research/design doc | 🔬 | ACP (Zed → Linux Foundation) — protocol still evolving |
| Session forking (Kimi Code pattern) | 🔬 | Doc 2 cite #30 — spike on Claude Code session model compatibility |
| AgentPool bidirectional ACP | 🔬 | Doc 2 cite #39 — niche, low priority |

### 4.7 Totals

Counts include in-flight v3.5 items (collector, test pipeline, eval) that are already shipped-approved and tracked elsewhere — those rows are ✅ here only for roadmap inventory completeness.

| State | v2 | v3 | v3.5 | v4 | v5 | v6 | Total |
|---|---|---|---|---|---|---|---|
| ✅ adopt | 3 | 2 | 3 | 3 | 0 | 0 | **11** |
| 🔬 spike | 1 | 1 | 0 | 1 | 2 | 4 | **9** |
| ❌ reject | 2 | 0 | 0 | 0 | 1 | 0 | **3** |
| **phase total** | 6 | 3 | 3 | 4 | 3 | 4 | **23** |

Net-new from the two documents (excluding in-flight v3.5 already-tracked items): 8 ✅ / 9 🔬 / 3 ❌ = 20 net-new candidates requiring new sub-specs, ADRs, or rejection notes.

## 5. Sub-spec Decomposition

~14-15 themed sub-specs following the harness-observability design pattern.

### v2 (2 sub-specs)
- **v2-a hooks hardening** — graceful truncation + JSON payload stdin parsing + checkpoint commits + PreCompact squash (3 ✅ items, 1 spec)
- **v2-b security hardening** — slopsquatting-aware install gate (🔬 spike)

### v3 (2 sub-specs)
- **v3-a MCP server expansion** — AutoMCP integration + semantic memory protocol spec (2 ✅ items)
- **v3-b catalog MCP audit** — re-evaluate Context7/Serena ADRs against 2026 best practice (🔬)

### v3.5 (3 sub-specs, already filed)
- **v3.5-a collector** — #109-#113 (in flight)
- **v3.5-b test pipeline** — #114-#118 (in flight)
- **v3.5-c eval harness** — #119-#124 (in flight)

### v4 (2 sub-specs)
- **v4-a workflow patterns** — Orchestrator-Workers + Plan-then-Execute + Parallelization + Prompt chaining (🔬)
- **v4-b Terminal-Bench 2.1 evaluation harness** — adopts TB 2.1 as the formal eval target for the v3.5-c eval harness

### v5 (2 sub-specs)
- **v5-a BYOK endpoint abstraction** — 🔬
- **v5-b local inference** — 🔬

### v6 (3 sub-specs)
- **v6-a meta-harness self-rewrite loop** — 🔬
- **v6-b ACP research/design doc** — 🔬
- **v6-c emerging patterns** — session forking + AgentPool (🔬)

### Spec doc locations
- `docs/superpowers/specs/YYYY-MM-DD-<phase>-<sub>-<topic>.md`
- ADR template (0000-template.md) for each 🔬 spike item
- Design + plan + impl cycle per harness-observability precedent

## 6. Tracking Artifacts

| Artifact | Path / Issue | Purpose |
|---|---|---|
| Roadmap doc | `docs/superpowers/roadmap.md` (new) | Top-level roadmap. Replaces this spec's role. |
| Plan companion | `PLAN.md` (slimmed) | One-page TL;DR + cross-references. |
| Phase tracking | 6 GitHub issues | v2-v6 + v3.5. `tracking` label. |
| Sub-specs | `docs/superpowers/specs/...` | ~14-15 files. |
| Plan docs | `docs/superpowers/plans/...` | Implementation plans per sub-spec. |
| Migration doc | `docs/superpowers/specs/2026-08-08-roadmap-restructure-migration.md` | Close-out of #87-#92. |

## 7. Issue Migration

```
#87  [ROADMAP] index              → close, replaced by roadmap doc
#88  v1.x active maintenance       → close as completed (v1.0.0 shipped)
#89  v2 backlog                    → mutate title/scope → v2 hooks + security
#90  v3 freshness/model-cards      → mutate title/scope → v3 MCP/ACI expansion
#91  v4-vision spike               → mutate title/scope → v4 workflow + eval
#92  cross-cutting ideation test   → keep, reassign to v4
NEW   v3.5 observability           → open
NEW   v5 BYOK + local              → open
NEW   v6 meta-harness + ACP        → open
```

## 8. Validation Rules

**Tri-state promotion criteria:**

- ✅ **adopt → GitHub issue** when:
  1. At least one verified citation OR reproducible benchmark
  2. D7-vetted if external, self-pinned if first-party
  3. Clear acceptance criteria (specific, testable)
- 🔬 **spike → ADR** when:
  1. At least one cited source
  2. But no reproducible benchmark, OR D7 pass pending, OR scope unclear
  3. ADR defines: research question, deliverable, decision criteria for promotion/demotion
- ❌ **reject → one-line reason** when:
  1. Duplicate of existing work (cite the existing issue)
  2. Evidence fails (e.g., forward-dated arXiv IDs only, no underlying repo)
  3. Out of scope for heretek marketplace (e.g., vendor-specific hardware)

**State transitions:**
- 🔬 → ✅: spike closes with positive research, item promotes
- 🔬 → ❌: spike closes with negative result, item dropped
- ✅ → 🔬: if evidence degrades (e.g., upstream dies), demote back to spike
- ✅ → ❌: if D7 fail surfaces, demote + add to `catalog/rejected.md` if external

## 9. Phase-Done Definitions

- **v2:** hooks hardening ADRs merged, fast_gate covers new patterns, no regression on existing tests
- **v3:** AutoMCP integration smoke-tested, semantic memory protocol spec published
- **v3.5:** harness-observability #109-#124 closed, smoke test green
- **v4:** workflow patterns ADRs merged, evaluator-optimizer running against harness fixtures, TB 2.1 score recorded
- **v5:** BYOK endpoint switched in test harness, local inference smoke test on reference hardware
- **v6:** meta-harness loop demonstrably improves harness metric on a held-out task

## 10. Rollout Cadence

- v2 first (closest to existing architecture, lowest risk)
- v3 once v2 lands (no architectural interference)
- v3.5 in parallel from now (already in flight)
- v4 gated on v3.5 eval harness being usable
- v5/v6 research-only until v4 produces benchmark evidence

## 11. Open Questions

1. **#92 reassignment:** cross-cutting ideation test could move to v4 or stay in current label. Decision deferred to v4 plan phase.
2. **Sub-spec ordering within v4:** workflow patterns vs eval harness. Default: workflow patterns first (eval needs orchestrator infra).
3. **TB 2.1 scoring baseline:** when v4-b spec is written, define the baseline score from `claude-code` + `Opus 5` against TB 2.1 to anchor v6's meta-harness improvement target.

## 12. Cross-references

- `PLAN.md` — current state (to be slimmed post-migration)
- `docs/superpowers/specs/2026-08-08-harness-observability-design.md` — v3.5 precedent
- `docs/superpowers/specs/2026-08-06-freshness-enforced-coding-roadmap-design.md` — analogous precedent
- Issue #87 — current roadmap index (to be closed)
- Issue #109-#124 — in-flight observability workstream
