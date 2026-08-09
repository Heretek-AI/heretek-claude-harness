# Issue ↔ Codebase Audit (2026-08-08)

## Goal

Cross-reference every open GitHub issue against the current `heretek-claude-harness`
codebase to detect drift: work that's shipped but the issue is still open, issues
that are blocked by closed PRs, work that's stalled, and any orphaned follow-ups.

Deliverable: a triage report (this document's sibling) with per-issue cards,
categorized status, and recommended action. Output lives in
`catalog/reviews/audit-2026-08-08.md` once written.

## Scope

- All 55 OPEN issues on `Heretek-AI/heretek-claude-harness` at audit time.
- Codebase state on `main` and recent merges into `main` (last ~30 commits).
- Already-known merges referenced via memory (Tier-2 ADR #54, security-scan #134,
  housekeeping #51/#52/#55/#57/#59, #130 #129).
- Does NOT cover closed issues, PR queue, or external repos.

## Cluster breakdown (8 parallel research lanes)

Each cluster is one Explore-agent dispatch with a fixed schema (see below).
Clusters are designed to be independent — no shared state needed.

| ID | Cluster | Issues | Why a cluster |
|----|---------|--------|---------------|
| A | harness-observability | #109–#124 (16) | One initiative; explicit `harness-observability` label; per the 2026-08-08 design specs already on disk |
| B | roadmap tracking / version meta | #89, #90, #91, #92, #126, #127, #128 (7) | `tracking`-labeled version meta-issues; cross-cutting blockers for downstream work |
| C | v3 follow-ups (production-integration) | #84, #85, #86 (3) | All labeled `v3-follow-up`; integration tasks for already-shipped v3 spikes |
| D | v1 test framework / long-term measurement | #80, #81, #82, #83 (4) | Long-horizon measurement experiments; all carry `testing`+`enhancement` |
| E | v4 vision spikes | #77, #78, #79 (3) | Research spikes for v4 (counterfactual / SVoK / staleness metric) |
| F | v1 freshness + v2 detection | #67–#74 (8) | Primitives & detection rules — `security-scan`, `freshness`, `tech-debt` |
| G | Tier-2 + housekeeping leftovers | #8, #51, #55, #59 (4) | Tier-2 partially-shipped via #54; doc/cleanup leftovers from housekeeping batch #51,#52,#55,#57,#59 |
| H | v2 plugin backlog | #1, #3, #4, #5, #6, #7, #17, #18, #19, #132 (10) | Long-running `help wanted` plugin/feature backlog; #132 mirrors a research-doc skill |

## Per-issue schema (each cluster agent returns one card per issue)

```yaml
- number: 109
  title: "[harness-observability] Add telemetry JSONL schema fixture"
  created: 2026-08-08
  labels: [enhancement, harness-observability]
  status: in_flight | shipped_but_open | stalled | blocked | on_track | needs_decision | obsolete
  evidence:
    code_refs: ["tests/fixtures/harness-observability/...", "..."]   # if shipped
    merged_in: "abc1234"                                              # commit SHA, if shipped
    linked_specs: ["docs/superpowers/specs/2026-08-08-harness-observability-collector.md"]
    linked_prs: [#NNN]
  recommended_action: close | keep | escalate | split | supersede
  rationale: "<one sentence>"
  drift_signals: []   # e.g. "issue references v3 but spec is now v3.5"
```

`status` enum:
- `shipped_but_open`: code/spec merged but issue not closed
- `in_flight`: PR linked or recent activity < 14d
- `stalled`: no activity > 30d and no clear blocker
- `blocked`: depends on something not yet started
- `on_track`: in roadmap/plan, not started but expected
- `needs_decision`: ambiguity or scoping question only the user can resolve
- `obsolete`: superseded by newer issue/spec

## Synthesis

After all 8 cluster agents return, one synthesis pass produces:
1. A summary table sorted by `status` then number.
2. A "drift findings" section listing every `shipped_but_open` issue with the
   commit SHA that closed the work — candidates for bulk close.
3. A "needs decision" section: aggregated items the user must resolve.
4. A coverage gap section: places where the code has issues but no GitHub issue
   tracks them (e.g. TODO/FIXME in shipped code).

The synthesis is a single markdown report written to
`catalog/reviews/audit-2026-08-08.md`.

## Verification

- Cluster agent output validated against schema (every required field present).
- Synthesis cross-checks against the 5 most-recent merged PRs (#129, #130, plus
  any open PRs) to confirm `shipped_but_open` claims.
- Drift findings cross-referenced with `git log` for each cited commit.
- No new issues are created by this audit — it only produces a report.

## Out of scope

- Code changes (no edits to source/tests).
- New ADR drafting (this audit is triage, not authoring).
- Auto-closing issues. The user reviews the report and decides.

## Risks / failure modes

- Agent hallucination of merged SHAs: mitigated by requiring `git log` cross-check
  in the synthesis pass.
- Cluster overlap (e.g. #109–#124 vs the roadmap tracking issue #126 which is
  about v3.5 observability): the synthesis pass will dedupe and call out overlap
  explicitly.
- Stale memory: the synthesis pass re-verifies any auto-recalled memory facts
  before citing (per the memory-drift-refresh protocol).
