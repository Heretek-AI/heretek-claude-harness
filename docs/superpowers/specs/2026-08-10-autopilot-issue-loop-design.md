---
date: 2026-08-10
topic: autopilot-issue-loop
status: design
parent: docs/superpowers/specs/2026-08-09-issue-loop-refactor-adr.md
---

# Autopilot Issue Loop — Design

> Date: 2026-08-10. Extends the issue-loop infrastructure shipped via PR #192
> and the refactor ADR (`2026-08-09-issue-loop-refactor-adr.md`). Adds a fully
> autonomous session mode where the loop handles its own triage, investigation,
> spec generation, breakdown, code review, and PR merge without human gating.

## Context

The existing issue-loop (`scripts/issue_loop/`) runs as a one-shot drain: user
invokes the `issue-loop` skill, Claude orchestrates per-issue subagent
dispatches, opens PRs, waits for green, squash-merges. The user has been
manually invoking the drain periodically (e.g., 2026-08-10 drained 30 open
issues) but cannot keep up with the constant flow of new issues.

The current pipeline short-circuits on most enhancement / tracking / audit /
research issues: the planner prompt's "30 lines" rule and the executor's
"touch only files named in the original scanner report" rule force BLOCKED.
The drain logs these as `skipped` in the ledger but leaves them open on
GitHub — they still need real human attention for v2 plugin scaffolding,
hostile audits, research docs, etc.

Goal: a single Claude session that, when the user invokes the skill, runs the
loop with no human gating inside the session, handling every issue end-to-end
on its own, generating SDD specs when needed, breaking large issues into
sub-issues, investigating out-of-scope issues, and auto-merging clean PRs.

## Decisions

The following decisions came out of brainstorming on 2026-08-10:

| Question | Decision |
|---|---|
| Trigger | **Manual invocation** — user runs `/issue-loop` skill when ready. No cron, no webhook. |
| BLOCKED handling | **Aggressive investigation + break-down, leave issue open.** When a path subagent BLOCKs, the orchestrator re-routes through INVESTIGATE or BREAK-DOWN rather than marking skipped. Issues are never auto-closed. |
| Merge policy | **Auto-merge on all-green.** Squash-merge when CI + Copilot + SonarCloud + verifier all clean. No human review gate. |
| Halt conditions | **System limits only.** Loop halts only on hard operational limits (GitHub rate limit, infra failure, Anthropic errors). Quality / policy gates do not halt the loop. |
| Design-heavy issues | **Generate SDD spec + auto-implement.** Spec-writer subagent runs the brainstorming flow, writes the design doc, critic reviews, orchestrator implements the spec. |
| Cost ceiling | **Unlimited per session.** No token cap, no per-issue budget, no wall-clock cap. User can monitor via periodic summaries. |
| Observability | **Periodic summary messages every 30 min.** Aggregate throughput + current issue + ETA. No per-issue noise. |

## Architecture

```
                            ┌──────────────────────────────┐
                            │  Manual invocation (user)    │
                            │  /issue-loop skill           │
                            └──────────────┬───────────────┘
                                           │
                                           ▼
                            ┌──────────────────────────────┐
                            │  Loop tick (per issue)       │
                            │  1. select-next              │
                            │  2. classify path            │
                            │  3. dispatch subagent(s)     │
                            │  4. poll gate                │
                            │  5. finalize (merge|skip|    │
                            │               report)        │
                            └──────────────┬───────────────┘
                                           │
                ┌────────┬────────┬────────┴────────┬────────┐
                ▼        ▼        ▼                 ▼        ▼
              FIX    INVESTIGATE  SPEC          BREAK-DOWN  SKIP
              (executor) (deep-dive) (SDD flow)   (sub-issues) (no-op)
                │        │        │                 │        │
                ▼        ▼        ▼                 ▼        ▼
              PR+merge  may pivot to fix  spec→critic→impl  log
                            │        │
                            ▼        ▼
                          fix path  implementation PR
```

### Five paths

1. **FIX** — Issue has a clear scanner-flagged site (file:line in body).
   Pipeline: `explore → planner → executor → test-engineer → verifier`.
   Open PR, poll gate, squash-merge on green, `mark-merged`.

2. **INVESTIGATE** — Issue seems out-of-scope but might have a hidden fix
   site. Spawn `investigator` subagent: read related files, search for
   similar patterns, propose findings.
   - If findings yield a fix site (file:line): pivot to FIX.
   - If not: post GitHub comment with findings, log-event, mark
     `investigated` in ledger, leave issue open.

3. **SPEC** — Issue is large or design-heavy (v2 plugin, audit, research,
   cross-cutting refactor). Spawn `spec_writer` subagent that runs the
   brainstorming flow (clarifying questions → approaches → design → spec
   doc). Critic reviews the spec. Implementation runs against the spec.
   Issue stays open with the spec linked from a comment.

4. **BREAK-DOWN** — Issue is large but decomposable. Spawn `breakdowner`
   subagent: explores the issue, splits into sub-issues via GitHub sub-issue
   API, registers each child in the ledger via `register-sub-issue`. Each
   sub-issue is added to the queue and gets its own tick in subsequent
   iterations of the loop. The parent issue stays open until all children
   reach a terminal status, at which point the parent is marked complete.

5. **SKIP** — Permanent no-op (duplicate, won't-fix, "by design").
   Log-event, post comment, mark-skipped.

### Selection logic

Per issue: `classifier.classify(issue) -> Path`. Heuristic:

- **FIX**: body contains `path/to/file.ext:NNN` regex match AND scope words
  ≤ "small fix" / "patch" / "fix".
- **SPEC**: body contains scope words ("research", "audit", "design",
  "plugin", "skill", "system") AND no file:line anchors.
- **BREAK-DOWN**: body contains scope words ("split", "decompose",
  "sub-tasks", "phase") OR explicit checklist with > 5 items.
- **INVESTIGATE**: no anchors + vague scope + no clear spec/break-down cue.
- **SKIP**: body contains "duplicate", "won't fix", "by design", "not
  applicable", or matches an already-merged PR.

When classification is wrong, the subagent's BLOCKED signal sends the issue
back to the classifier for re-routing.

## Components

### New files

| Path | Purpose |
|---|---|
| `scripts/issue_loop/classifier.py` | Pure function `classify(IssueRef) -> Path`. Heuristic-based, no LLM. ~50 lines. |
| `scripts/issue_loop/prompts/investigator.md` | Investigator subagent. ~50 lines. |
| `scripts/issue_loop/prompts/spec_writer.md` | Spec-writer subagent (SDD flow). ~80 lines. |
| `scripts/issue_loop/prompts/breakdowner.md` | Breakdowner subagent. ~40 lines. |
| `tests/test_issue_loop_classifier.py` | Pure-function tests for classifier. ~15 cases. |
| `tests/test_issue_loop_prompts.py` | Golden snapshot tests for new prompts. |
| `docs/superpowers/specs/<date>-<topic>-design.md` | Generated spec docs (one per SPEC-path issue). |

### Extended files

| Path | Change |
|---|---|
| `scripts/issue_loop/cli.py` | New subcommands: `log-event`, `register-sub-issue`, `classify`. ~50 lines added. |
| `scripts/issue_loop/prompts/critic.md` | Extended to support spec review (verdict: `SPEC_READY`/`NEEDS_REVISION`). ~15 lines added. |
| `.claude/skills/issue-loop/SKILL.md` | Rewritten autopilot flow. |
| `.heretek/issue-loop-config.json` | Optional: `paths_enabled: ["fix", "investigate", "spec", "break-down", "skip"]` (default: all). `periodic_summary_minutes: 30` (default). |

### Ledger schema additions (backward-compatible)

```json
{
  "1": {
    "status": "investigated" | "merged" | "skipped" | "failed",
    "path": "fix" | "investigate" | "spec" | "break-down" | "skip",
    "sub_issues": [3, 4],
    "spec_path": "docs/superpowers/specs/...-design.md",
    "events": [{"ts": "...", "kind": "info|warn|error", "msg": "..."}]
  }
}
```

New statuses: `investigated` (terminal — investigator didn't find a fix).
Other statuses unchanged. Existing ledger entries remain valid. The
`investigated` status requires a new `Ledger.mark_investigated(issue_number,
findings_path)` method (and corresponding CLI wrapper) that records the
path to the investigator's `findings.json` so humans can re-pick-up the
investigation later.

## Data Flow

```
Per-issue tick (orchestrator, in this Claude session):
  1. python -m scripts.issue_loop.cli select-next   → IssueRef | {}
  2. If {}: emit periodic summary, then halt cleanly
  3. python -m scripts.issue_loop.cli mark-attempt <N>
  4. python -m scripts.issue_loop.cli classify <N>   → Path enum
  5. Dispatch path-specific subagent(s) via Agent tool
  6. Poll gate (CI + Copilot + SonarCloud) via GitHub MCP
  7. Finalize:
       FIX green → squash-merge → mark-merged
       FIX red   → retry once → if still red, leave PR open + log-event "needs-human"
       INVESTIGATE pivot → goto FIX
       INVESTIGATE no-fix → log-event + post GitHub comment + mark-investigated
       SPEC impl green → squash-merge → mark-merged + comment "spec: <path>"
       SPEC impl red   → leave PR open
       BREAK-DOWN → register-sub-issue per child → children get own ticks later
       SKIP → log-event + mark-skipped

Periodic summary (every 30 min):
  - Count issues processed since last summary by path + outcome
  - Total elapsed time + token estimate
  - Current issue in flight + ETA
  - Aggregate halt-condition warnings
```

## Error Handling

| Failure | Action |
|---|---|
| Subagent crash | Retry once with same prompt; on second failure, mark failed + log-event |
| CI fail (transient: timeout, network) | Auto-retry once; on persistent fail, leave PR open + comment "CI failed, needs human" |
| CI fail (test failure) | Leave PR open + comment with test output excerpt |
| Copilot HIGH/CRITICAL | Treat as CI failure; auto-handle only if trivially mechanical (lint fix, comment); else leave PR open |
| SonarCloud Quality Gate fail | Leave PR open + comment "SonarCloud blocked"; do not auto-suppress |
| Verifier reject (subagent) | Per existing ledger: retry up to `max_per_issue_attempts=3`, then mark failed |
| GitHub API rate limit | Exponential backoff with jitter (max 5min); resume on 200 |
| Token budget | Unlimited per user choice — no per-tick cap; trust Anthropic limits |
| Wall-clock | None — user chose unlimited |

### Auto-handle rubric for review feedback

- **Trivial** (auto-fix in same PR): lint warnings, comment typos, missing
  imports, docstring format, ruff violations, line-length.
- **Substantive** (leave PR open + human gate): design changes, API changes,
  schema changes, breaking changes, security-sensitive refactors.

The classifier for trivial-vs-substantive is the same `critic` subagent
used for spec review, with a `feedback_kind: trivial | substantive` output
field.

## Trust Boundaries

The user explicitly waived all policy-level gates inside a session. The
loop's only hard halts are operational (rate limit, infra failure). The
following are NOT halt conditions:

- Cross-issue verifier rejects. The existing
  `halt_after_cross_issue_rejects: 5` config remains in
  `.heretek/issue-loop-config.json` for non-autopilot runs but is ignored
  when the autopilot skill is invoked (skill sets an in-memory override).
- Quality gate failures (left as PRs for human triage).
- SonarCloud blocks (left as PRs for human triage).
- Token or wall-clock limits (unlimited per session).

The user can interrupt at any time by sending `stop` to the terminal. The
ledger is durable across interruptions — re-invoking the skill resumes from
the last pending entry.

## Testing

| Layer | Coverage |
|---|---|
| `classifier.py` | Pure-function tests: each path from canned issue bodies. ~15 cases. |
| New CLI subcommands | `tests/test_issue_loop_cli.py` extension: `log-event`, `register-sub-issue`, `classify`. ~8 tests. |
| New prompts | Golden snapshot tests: each prompt with canned input → expected structure. Verifies prompts don't drift. |
| Integration | Drain of 4 representative issues end-to-end: 1 FIX-able (existing security pattern), 1 SPEC (small design), 1 INVESTIGATE (no clear site), 1 BREAK-DOWN (decomposable). Verify ledger state + GH state. |
| Smoke | Spec generation flow: hand an issue that triggers SPEC, verify spec.md exists + critic reviewed + impl PR opened. |

### Verification gate before declaring "autopilot ready"

1. All unit tests pass (`pytest -q`).
2. Integration drain covers all 4 active paths.
3. Ledger snapshot matches expected schema (forward + backward compat).
4. Manual smoke test: spec generation produces a valid design doc.

## Out of Scope

- Multi-session continuity beyond ledger durability (no resumable LLM
  state across sessions — each session starts fresh).
- Token-budget tracking (user explicitly chose unlimited).
- Human-review notification channels (OMC `configure-notifications` skill
  handles this separately).
- Cron / webhook / scheduled triggers (user explicitly chose manual).
- Cross-repo coordination (single-repo scope).

## Followups

- After autopilot is operational, consider adding a `paths_enabled` config
  to allow per-session path filtering (e.g., only run FIX for security
  sweeps).
- Periodic `refresh_pins.py` integration: catalog vetting bar may drift;
  autopilot could trigger re-vetting on a schedule.
- Adversarial test fixtures: codify known-tricky issues to verify
  classifier and subagent prompts.

## Verification

`pytest -q tests/test_issue_loop_*.py -v` covers all unit tests.
Integration drain of 4 issues exercises all paths. Spec doc generation is
spot-checked against the brainstorming template.
