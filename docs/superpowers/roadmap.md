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
