---
date: 2026-08-08
topic: harness-observability
status: draft
parent: 2026-08-03-heretek-marketplace-design.md (D1–D17 inherited), 2026-08-05-security-monitoring-pipeline-design.md (D18–D22 inherited)
related_issues: [2, 80, 82, 83]
---

# Harness Observability — Design Spec (parent)

> Date: 2026-08-08. Parent spec. Decomposes into three sibling sub-specs. Inherits D1–D22 from parent specs unchanged. Adds D23–D29.

## 1. Summary

A three-layer system for capturing, replaying, and scoring harness behavior — turning every Claude Code session into a measurable artifact.

1. **Sub-spec 1 — Collector:** Hook event capture. Local-first JSONL telemetry. Closes issue #2 acceptance criterion 1.
2. **Sub-spec 2 — Test pipeline:** GitHub Action that runs Claude Code with heretek plugins against curated OSS fixtures. Captures session + patch + telemetry per fixture.
3. **Sub-spec 3 — Eval harness:** Three-layer scoring (auto-graded → LLM-judge → human-in-loop) over captured runs. Publishes weekly scorecard. Opens regression + gap detection issues.

The three sub-specs ship in order (collector → test pipeline → eval harness). Each is independently useful and de-risks the next.

## 2. Motivation

### What's missing

- **Issue #2 (Monitor plugins):** Defined v2-phase observability plugins but no concrete event-capture design. Acceptance criterion 1 ("At least 1 monitor plugin ships in v2") is the heretek-built fast-gate report — this spec builds its substrate.
- **Issues #80, #82, #83 (long-term test framework):** Define 24-month methodology-effectiveness measurement but lack a concrete mechanism for capturing harness output. The "Catalog telemetry (when available)" placeholder in #80 becomes concrete via sub-spec 1's JSONL schema.
- **No diagnostic feedback when hooks fail to fire.** D15 gives the `hooks` plugin exclusive hook ownership but provides no signal about whether hooks actually fired. A `fast_gate` that fails-open under load is invisible.
- **No regression detection.** When a refactor changes hook behavior, there's no baseline to compare against.

### What 2026 harness-evaluation work demands

- Anthropic's SWE-bench evaluation methodology ([arxiv:2310.06770](https://arxiv.org/abs/2310.06770)) demonstrated that harness behavior is measurable via deterministic task fixtures. The collector + test pipeline + eval harness is the heretek-local equivalent.
- Issue #2 explicitly names "custom dashboards, hook firing reports" as v2 scope. This spec builds the data substrate those dashboards consume.

## 3. Locked decisions (parent)

| # | Decision | Choice |
|---|---|---|
| D1–D17 (parent) | Marketplace D-rules | Inherited unchanged |
| D18–D22 (parent) | Security monitoring D-rules | Inherited unchanged (D20 SHA-pinning applies to all new workflows in this spec) |
| **D23** | **Decomposition** | **Three sibling sub-specs: collector, test pipeline, eval harness. Parent spec thin; each sub-spec fat. Mirrors the parent/companion pattern from security-monitoring-pipeline-design.md.** |
| **D24** | **Phasing** | **Sub-spec 1 (collector) ships first, sub-spec 2 (test pipeline) second, sub-spec 3 (eval harness) third. Foundation-up. Each layer is independently useful.** |
| **D25** | **Storage posture** | **Layered. Local-by-default under `~/.heretek/telemetry/`. Opt-in to upload via `heretek telemetry export`. CI artifact upload is automatic but redact-paths always on. `redact_paths: true` is the default.** |
| **D26** | **Eval layering** | **Three ranked layers. Layer 1 (auto-graded, deterministic, sub-second) ships with sub-spec 3 phase 1. Layer 2 (LLM-judge, rubric-aware, non-deterministic) ships phase 2. Layer 3 (human-in-loop, /heretek:telemetry-review skill) ships phase 3. Failures escalate upward; successes stay in lower layers.** |
| **D27** | **Task fixtures (sub-spec 2)** | **Hybrid: phase 1 = curated fixtures (5-10 hand-picked tasks per repo with known ground truth); phase 2 = historical PR replay (real merged PRs, diff similarity grading); phase 3 = open-ended directives (LLM-judge + human review).** |
| **D28** | **Issue #2 relationship** | **Issue #2 stays open. Sub-spec 1 absorbs + extends its acceptance criterion 1 (heretek-built monitor plugin). Sub-specs 2 + 3 are pure consumers of sub-spec 1's JSONL schema. No overlapping scope.** |
| **D29** | **D15 strict hooks ownership** | **Sub-spec 1's `telemetry_collector.py` lives under `plugins/hooks/scripts/` — the hooks plugin is the sole owner of hook-event capture. Sub-specs 2 + 3 never declare hooks, never modify `hooks.json`. The collector hook is appended to `plugins/hooks/hooks/hooks.json` per the existing pattern.** |

## 4. Architecture

```
                ┌─────────────────────────────────────────────────────┐
                │  Claude Code session (user machine OR CI runner)    │
                │  runs with heretek plugins installed                │
                └─────────────────────────────────────────────────────┘
                              │
                              │ hook events flow
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  plugins/hooks/scripts/telemetry_collector.py           │  ← sub-spec 1
        │  - subscribes to every PreToolUse / PostToolUse         │
        │  - captures tool_name, file_path, hook_decision, etc.   │
        │  - writes to ~/.heretek/telemetry/session-<id>.jsonl    │
        └─────────────────────────────────────────────────────────┘
                              │
                              │ session JSONL consumed by
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  .github/workflows/harness-test.yml                     │  ← sub-spec 2
        │  - weekly cron Sunday 02:00 UTC                         │
        │  - matrix: [fixture-1, fixture-2, ...]                  │
        │  - each job: run claude CLI with plugins + capture      │
        └─────────────────────────────────────────────────────────┘
                              │
                              │ artifacts uploaded (CI)
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  .github/workflows/harness-eval.yml                     │  ← sub-spec 3
        │  - layer 1: auto-graded (run tests + diff similarity)   │
        │  - layer 2: LLM-judge (rubric on reasoning trace)       │
        │  - layer 3: human-in-loop (/heretek:telemetry-review)   │
        └─────────────────────────────────────────────────────────┘
                              │
                              │ results roll up to
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Weekly scorecard + regression + gap detection          │
        │  - scorecard-YYYY-WW.md published as GitHub issue       │
        │  - regression detector opens harness-regression issue   │
        │  - gap detector opens harness-gap issue                  │
        └─────────────────────────────────────────────────────────┘
```

## 5. Interface contracts

| From → To | Contract |
|---|---|
| Sub-1 → Sub-2 | `Session` schema: one JSONL file per Claude Code session. Line types: `hook_event`, `tool_call`, `tool_result`, `agent_message`, `session_end`. Schema in `tests/fixtures/telemetry_schema.json`. |
| Sub-2 → Sub-3 | Per-fixture artifact bundle: `patch.diff` + `telemetry.jsonl` + `task_prompt.md` + `eval_input.json`. SHA-pinned for reproducibility. |
| Sub-3 → parent | Per-week scorecard: `scorecard-YYYY-WW.md` (auto) + `human-review-YYYY-WW.md` (when maintainer reviews). |
| Sub-1 ↔ local CLI | `heretek telemetry {show,grep,diff,export}` subcommands. Read-only on local JSONL. |

## 6. Phasing

| Phase | Deliverable | Sub-spec | Exit criteria |
|---|---|---|---|
| **A — collector** | `telemetry_collector.py` + `heretek telemetry` CLI + JSONL schema | sub-spec 1 | local install shows hook events under `~/.heretek/telemetry/`; `heretek telemetry show` works; #2 acceptance criterion 1 met |
| **B — test pipeline** | `harness_test.py` + `harness-test.yml` + 5 curated fixtures | sub-spec 2 | weekly cron runs 5 fixtures, produces artifact bundles, no human in loop |
| **C — eval harness** | `harness_auto_grade.py` + `harness_judge.py` + `/heretek:telemetry-review` skill + `scorecard.py` + `harness-eval.yml` | sub-spec 3 | weekly scorecard published; regression + gap detectors open issues on drops |

## 7. Open risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Collector adds latency to every tool call | Async (`async: true`), 200ms timeout, fail-open. P95 latency < 50ms asserted in test |
| 2 | LLM-judge non-determinism poisons scorecards | `temperature: 0`, model version pinned, recorded LLM-output fixtures for tests |
| 3 | Curator workload grows unbounded | Phase-B caps at 10 curated fixtures; phase-C opens curator-tooling issue if maintenance cost spikes |
| 4 | Local telemetry leaks PII to heretek repo by accident | `upload_opt_in: false` default; export requires `--i-understand-pii-implications`; `redact_paths: true` default |
| 5 | OSS repo in fixture goes private / deleted mid-test | Fixture validation step in `setup.sh`: fail-fast if `git clone` 404s; quarterly cron re-validates fixture URLs |
| 6 | Multi-day sessions exhaust disk | Compression after 30 days; configurable retention; never auto-uploads |

## 8. Out of scope (parent)

- Real-time streaming dashboards (issue #2 says "v3")
- SaaS-hosted telemetry (issue #2 says "self-host only")
- Cross-user aggregation of local telemetry
- Auto-merge of harness-test patches (sub-spec 2 is read-only on harness's output)
- Replacing existing `validate.yml` workflow
- Per-session telemetry metrics (we measure produced artifacts, not thinking process — same posture as issue #80)

## 9. References

- `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` — parent spec (D1–D17)
- `docs/superpowers/specs/2026-08-05-security-monitoring-pipeline-design.md` — sibling spec (D18–D22)
- `docs/superpowers/specs/2026-08-08-harness-observability-collector.md` — sub-spec 1
- `docs/superpowers/specs/2026-08-08-harness-observability-test-pipeline.md` — sub-spec 2
- `docs/superpowers/specs/2026-08-08-harness-observability-eval.md` — sub-spec 3
- Issue #2 — v2 Monitor plugins
- Issue #80 — v1 test framework: external-data triangulation
- Issue #82 — v1 test framework: failure-mode-driven ideation
- Issue #83 — v1 test framework: cross-domain transfer ideation
- `plugins/hooks/README.md` — existing hooks plugin
- `plugins/hooks/scripts/fast_gate.py` — existing Layer 1 dispatcher (model for collector)
