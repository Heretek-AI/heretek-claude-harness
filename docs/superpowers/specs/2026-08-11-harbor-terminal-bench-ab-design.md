---
date: 2026-08-11
topic: harbor-terminal-bench-ab
status: draft
---

# Harbor + Terminal-Bench A/B Eval (main-branch GitHub Action)

> Date: 2026-08-11. Stands alone. Pivot from per-plugin eval design to
> Terminal-Bench A/B (see § Deferred).

## 1. Summary

A GitHub Action that triggers on `push` to `main` (and `workflow_dispatch`).
Spawns two Claude Code agent instances via Harbor Framework against the
same Terminal-Bench 2 dataset:

- **Agent A** — Claude Code + the heretek harness (marketplace + all 11 plugins loaded via local `--plugin-dir`).
- **Agent B** — Claude Code baseline (no heretek plugins).

Same model, same `ANTHROPIC_BASE_URL`, same `ANTHROPIC_AUTH_TOKEN`, same
task set. Only the harness differs. The action diffs the two result sets,
generates a Markdown comparison, and opens a per-run GitHub issue tagged
`terminal-bench-ab`. Maintains a durable, searchable history of harness
regressions and improvements over time.

## 2. Background and pivot

The original brainstorm (Sections 1-3 of the conversation) proposed building
a custom per-plugin behavioral eval (`scripts/plugin_eval.py` + per-plugin
fixtures). That design is **deferred** (§ Deferred) after discovering Harbor
Framework + Terminal-Bench as a more general, battle-tested alternative for
measuring harness impact.

Terminal-Bench A/B tests one question: **does the heretek harness, on
average, make Claude better at terminal-based coding tasks?** It is
broad-but-shallow. A future spec may reintroduce per-plugin fixtures for
narrow-but-deep localization.

## 3. Architecture

**Two-paragraph summary.** A GitHub Action triggers on `push` to `main` and
`workflow_dispatch`. It spawns two `harbor run` invocations on the same
Ubuntu runner, sequentially. Agent A is a Claude Code instance with the
heretek harness installed (marketplace + all 11 plugins via local
`--plugin-dir`). Agent B is the same Claude Code instance with no heretek
plugins. Both run Terminal-Bench 2 (or a curated subset) under the same
model, same `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` /
`ANTHROPIC_MODEL`. Harbor writes per-task results to disk; a Python script
(`scripts/comparison_report.py`) diffs the two result sets, generates a
Markdown comparison, and opens (or updates) a tracking GitHub issue.

**Why this shape.** Harbor natively supports `claude-code` as an agent with
`--ak config=...` for plugin configuration, but each `harbor run` is
single-agent. A/B is achieved by running the action twice in the same
workflow job with different configs and diffing offline.

**File layout.**

```
.github/workflows/
└── terminal-bench-ab.yml         # NEW — GH Action, push-to-main + manual

scripts/
├── terminal_bench_ab.sh          # NEW — runs both harbor invocations sequentially, captures outputs
└── comparison_report.py          # NEW — diffs results, generates Markdown, opens/updates GH issue

tests/
├── test_terminal_bench_ab_sh.py  # NEW — hermetic, mocks harbor subprocess
├── test_comparison_report.py     # NEW — golden fixture diffing
├── test_comparison_diff.py       # NEW — edge cases (all-fail, partial, missing)
├── test_issue_body_schema.py     # NEW — Markdown structure validation
├── test_no_secret_leak_in_issue.py # NEW — scans comparison.md for token-shaped strings
└── test_concurrency_group_yaml.py # NEW — verifies workflow YAML has concurrency + permissions blocks

tests/fixtures/terminal_bench_ab/
├── case-quick-8-pass-5/          # known good A/B pair (5 of 8 tasks pass for A)
├── case-all-fail/                # both agents score 0
├── case-agent-b-missing/         # partial run (B did not complete)
├── case-identical-results/       # Δ is 0
└── case-task-id-with-secret/     # negative test for no_secret_leak

scripts/ci.sh                      # EXISTING — extended to include new tests + actionlint
plugins/                           # EXISTING — local plugin source, referenced via --plugin-dir
.claude-plugin/marketplace.json    # EXISTING — NOT used by this workflow
```

**Per-job env (from repo secrets).**

```yaml
env:
  ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
  ANTHROPIC_MODEL: ${{ secrets.ANTHROPIC_MODEL }}
  ANTHROPIC_AUTH_TOKEN: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
  HERETEK_PLUGIN_DIR: ${{ github.workspace }}/plugins
  HERETEK_MARKETPLACE_FILE: ${{ github.workspace }}/.claude-plugin/marketplace.json
```

**Trigger and matrix.**

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      n_tasks:
        description: "Terminal-Bench task count (default 8, full = all)"
        default: "8"
      n_concurrent:
        description: "Per-agent concurrency"
        default: "8"
```

**Per-agent invocation.**

```bash
# Agent A — with heretek
harbor run \
  -d terminal-bench/terminal-bench-2 \
  -a claude-code \
  -m "anthropic/${ANTHROPIC_MODEL}" \
  --ak "config={\"plugin_dir\":\"${HERETEK_PLUGIN_DIR}\"}" \
  -n "${N_CONCURRENT}" \
  -o ./results/agent-a

# Agent B — baseline
harbor run \
  -d terminal-bench/terminal-bench-2 \
  -a claude-code \
  -m "anthropic/${ANTHROPIC_MODEL}" \
  -n "${N_CONCURRENT}" \
  -o ./results/agent-b
```

**Single job, sequential calls.** Two jobs in one workflow, or one job with
sequential calls? Single job with sequential calls. Reasons: simpler state
sharing (results dir), no need to coordinate secrets across two jobs,
wall-clock dominated by harbor's internal concurrency, not spawn overhead.

**What we deliberately don't build.**

- No new scoring system — Terminal-Bench has its own.
- No per-plugin fixtures — deferred.
- No LLM-judge layer — Harbor's pass/fail is the truth.
- No PR gating — runs only on `main` and `workflow_dispatch`.

## 4. Task selection + scoring + output schema

**Task selection.** Terminal-Bench 2 ships ~100+ tasks. Running all is
expensive + slow + noisy for fast A/B feedback. Three-tier approach:

| Tier    | Count  | Source                                            | When                                   |
|---------|--------|---------------------------------------------------|----------------------------------------|
| `quick` | 8      | hand-picked (`scripts/tb_subset_quick.txt`)       | every push to main                     |
| `full`  | all    | harbor default                                     | workflow_dispatch, `tier=full`        |
| `custom`| user   | `--ak 'config={"task_filter":"<glob>"}'`          | workflow_dispatch                      |

The `quick` subset is version-controlled (`scripts/tb_subset_quick.txt`):
a plain-text file, one Terminal-Bench task ID per line, eight IDs total.
Selection criteria: short wall-clock (<2 min/task at Sonnet-equivalent),
representative diversity (terminal ops, file editing, build system, networking, etc.),
deterministic oracle (low flakiness). The eight task IDs are picked during
Phase 1 implementation and updated as Terminal-Bench 2 evolves.

**Per-task scoring.** Terminal-Bench's own oracle decides pass/fail per task.
We consume it as-is. No custom judge layer.

**Per-agent aggregation.** `scripts/terminal_bench_ab.sh` produces:

```
results/
├── agent-a/
│   ├── harbor-log.txt         # full harbor stdout
│   ├── per-task.jsonl         # one JSON per task: {"task_id": "...", "verdict": "pass"|"fail", "wall_clock_sec": N, "tokens": {...}}
│   └── summary.json
└── agent-b/                   # same shape
```

**`summary.json` schema (per agent).**

```json
{
  "agent": "agent-a-with-heretek",
  "model": "MiniMax-M3[1m]",
  "commit_sha": "abc1234",
  "heretek_harness": true,
  "n_tasks": 8,
  "passed": 5,
  "failed": 3,
  "pass_rate": 0.625,
  "wall_clock_sec_total": 845,
  "wall_clock_sec_p50": 92,
  "tokens_total": 412345,
  "per_task": [
    {"task_id": "tb-001-fix-permissions", "verdict": "pass", "wall_clock_sec": 45, "tokens": 12345}
  ]
}
```

**Comparison diff (between agent-a and agent-b).**

```json
{
  "commit_sha": "abc1234",
  "delta_pass_rate": +0.125,
  "delta_passed": +1,
  "tasks_agent_a_passed_b_failed": ["tb-005-network-fetch"],
  "tasks_agent_b_passed_a_failed": [],
  "tasks_both_passed": ["tb-001-fix-permissions", "tb-002-edit-json"],
  "tasks_both_failed": ["tb-004-build-system"],
  "wall_clock_delta_sec": -42,
  "tokens_delta": -12300
}
```

**No statistical significance** in v1. With 8 tasks per run, any p-value
would be theater. We surface raw counts (`X more pass, Y more fail`) and
the per-task list; humans judge.

## 5. Data flow + issue tracking

**Pipeline.**

```
push to main (or workflow_dispatch)
  ↓
runner: ubuntu-latest
  ├─ checkout
  ├─ setup-python
  ├─ uv tool install harbor
  ├─ docker info (verify Docker; fail-fast if missing)
  ├─ scripts/terminal_bench_ab.sh
  │    ├─ harbor run (agent A, with heretek) → results/agent-a/
  │    └─ harbor run (agent B, baseline)    → results/agent-b/
  ├─ actions/upload-artifact@v4: results/ (30-day retention)
  ├─ python scripts/comparison_report.py
  │    ├─ reads results/agent-a/summary.json + results/agent-b/summary.json
  │    ├─ generates diff.json
  │    ├─ renders comparison.md
  │    └─ writes /tmp/comparison.md
  └─ gh issue create --label terminal-bench-ab --body-file /tmp/comparison.md
```

**Issue model: per-run issue** (not single tracking issue). Reasons:
- Each main push gets a discrete, searchable artifact.
- Title `Terminal-Bench A/B: <7-char-sha> — <YYYY-MM-DD>` filters cleanly.
- `label: terminal-bench-ab` lets maintainers enumerate all runs.
- "Previous run" link via `gh issue list --label terminal-bench-ab --limit 1`.

**Issue body template.**

```markdown
# Terminal-Bench A/B — `<short-sha>`

**Trigger:** `push` | `workflow_dispatch`
**Actor:** <github-actor>
**Tier:** `quick` (8 tasks) | `full` (N tasks)
**Model:** `<model-name>` (via `<base-url>`)

## Headline
| Agent | Pass rate | Passed | Failed | Wall-clock | Tokens |
|---|---|---|---|---|---|
| **A — with heretek** | 62.5% | 5/8 | 3/8 | 845s | 412k |
| **B — baseline** | 50.0% | 4/8 | 4/8 | 887s | 425k |
| **Δ** | **+12.5%** | **+1** | **−1** | **−42s** | **−13k** |

## Per-task
| Task | A | B | Notes |
|---|---|---|---|
| tb-001-fix-permissions | ✓ (45s) | ✓ (52s) | both |
| tb-005-network-fetch | ✓ (120s) | ✗ (60s) | A wins |
| tb-004-build-system | ✗ (180s) | ✗ (175s) | both fail |

## Tasks where heretek helped
- `tb-005-network-fetch` (A pass, B fail)

## Tasks where heretek hurt
- (none)

## Artifacts
- [`results/agent-a/`](link) · [`results/agent-b/`](link)
- [Workflow run](link)

## Previous run
- [<short-sha> — <date>](link)
```

**`comparison_report.py` interface.**

```bash
scripts/comparison_report.py \
  --results-dir results/ \
  --commit-sha $GITHUB_SHA \
  --trigger push \
  --actor $GITHUB_ACTOR \
  --tier quick \
  --model "$ANTHROPIC_MODEL" \
  --base-url "$ANTHROPIC_BASE_URL" \
  --output /tmp/comparison.md
```

**Workflow permissions.**

```yaml
permissions:
  contents: read
  issues: write       # for gh issue create
  actions: write      # for actions/upload-artifact@v4
```

**Failure as data.** If harbor run partially fails (e.g., 3/8 tasks complete
before timeout), we still post an issue — the body shows the partial result
with a `INCOMPLETE` badge so the regression is visible.

**Artifact retention.** 30 days for `results/`. After that, the issue is the
durable record.

## 6. Error handling

| Failure | Detection point | Response |
|---|---|---|
| Docker not available on runner | `docker info` step | fail-fast; abort workflow; no issue posted |
| `uv tool install harbor` fails | install step | fail workflow; no issue posted |
| Repo secrets missing | workflow env resolution | fail with clear error in workflow summary |
| Agent A run fails entirely | post-run check | post issue tagged `FAIL` with "agent A did not complete" |
| Agent B run fails entirely | post-run check | post issue tagged `FAIL` with "agent B did not complete"; partial comparison shown |
| Per-task timeout | harbor per-task verdict | task marked `fail` (harbor's own verdict); surfaced in per-task table |
| Task count vs available tasks mismatch | harbor | harbor fails; surfaced as workflow error |
| Partial completion | harbor summary count vs tasks input | post issue tagged `INCOMPLETE` with "N of M completed" |
| `gh issue create` fails | wrapper step | append comparison.md to `$GITHUB_STEP_SUMMARY` so the body still lands in the run summary; log the error so maintainers can retry manually |
| Marketplace conflict (`heretek` already registered) | n/a | conflict is impossible by design (use `--plugin-dir`, not marketplace add) |
| Two pushes in quick succession | workflow concurrency group | cancel-in-progress for the older run |
| Secret leakage into issue body | post-creation assertion step | if `comparison.md` contains token-shaped patterns (`sk-*`, `sk-cp-*`, `ghp_*`), comment in issue with redacted warning |
| Result dir already exists (resumed runner) | shell check | wipe with `rm -rf results/` before harbor runs |

**Concurrency group.**

```yaml
concurrency:
  group: terminal-bench-ab
  cancel-in-progress: true
```

**Idempotence.** Each run is independent (fresh checkout, fresh results dir,
fresh issue). Re-running the same commit produces a new issue with identical
content. We accept this — issues dedup via label filter, not title match.

## 7. Testing

**Unit tests (run via `pytest tests/test_terminal_bench_*.py` as part of
`scripts/ci.sh`).**

| Test file | What it covers |
|---|---|
| `test_terminal_bench_ab_sh.py` | Hermetic: mocks `harbor` via `tmp_path`; asserts script invokes twice with correct args; asserts results dir shape; asserts partial results tolerated |
| `test_comparison_report.py` | Golden file: given known `agent-a/` + `agent-b/` fixtures, generated `comparison.md` matches expected |
| `test_comparison_diff.py` | Edge cases: identical results, all-fail, one agent missing, both missing, single-task run, empty `passed` lists |
| `test_issue_body_schema.py` | Markdown structure: required headings present, table columns, no `<!--TEMPLATE-->` placeholders |
| `test_no_secret_leak_in_issue.py` | Critical: scans `comparison.md` for token-shaped strings (`sk-*`, `sk-cp-*`, `ghp_*`); fails if found |
| `test_concurrency_group_yaml.py` | Verifies workflow YAML has required `concurrency:` and `permissions:` blocks |

**CI integration.**

- All tests run as part of `scripts/ci.sh` (mandatory pre-commit per CLAUDE.md).
- Lint: `shellcheck scripts/terminal_bench_ab.sh`, `ruff check scripts/comparison_report.py tests/test_terminal_bench_*.py`, `actionlint .github/workflows/terminal-bench-ab.yml`.

**Coverage targets.**

- `scripts/comparison_report.py`: ≥85%.
- `scripts/terminal_bench_ab.sh`: ≥75% (via subprocess + output inspection).

**What we don't test.**

- Actual `harbor run` execution (requires Docker + API — too expensive for unit CI; tested implicitly via the GH Action on every push).
- The GH issue creation step (tested manually in a forked repo).

**Workflow self-test (one-shot, before merge).**

```bash
# Run the script directly on the runner (bypassing GH Action layer)
scripts/terminal_bench_ab.sh \
  --tier quick \
  --results-dir ./results \
  --plugin-dir ./plugins \
  --n-concurrent 2

# Verify generated comparison
python scripts/comparison_report.py \
  --results-dir ./results \
  --commit-sha deadbeef \
  --trigger local \
  --actor test-runner \
  --tier quick \
  --model test-model \
  --base-url http://localhost \
  --output /tmp/c.md

# Manually inspect /tmp/c.md
```

## 8. Phases

| Phase | Deliverable | Exit |
|---|---|---|
| 1 | `scripts/terminal_bench_ab.sh` + `scripts/tb_subset_quick.txt` | script runs end-to-end on dev machine; results/ structure matches spec |
| 2 | `scripts/comparison_report.py` + golden fixtures | golden `comparison.md` regenerates byte-identical |
| 3 | `tests/test_terminal_bench_*.py` | `pytest` passes; coverage targets met; `scripts/ci.sh` clean |
| 4 | `.github/workflows/terminal-bench-ab.yml` + `scripts/ci.sh` extension | workflow lints; dry run on a fork posts a comparison issue |
| 5 | Initial push-to-main run (live) | first issue opens with valid comparison; idempotence verified on a re-run |

## 9. References

- https://www.harborframework.com/docs/agents — Harbor Framework, agent integration
- https://www.harborframework.com/docs/tutorials/running-terminal-bench — Terminal-Bench 2 dataset
- https://github.com/harbor-framework/harbor — Harbor source, AGENTS.md, registry.json
- https://platform.minimax.io/docs/token-plan/claude-code — example settings.json with `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL` / `ANTHROPIC_AUTH_TOKEN` for non-Anthropic providers
- https://tbench.ai — Terminal-Bench task catalog and leaderboard
- `docs/superpowers/specs/2026-08-08-harness-observability-eval.md` — sibling harness-eval spec (different purpose; left untouched)
- `scripts/ci.sh` (existing) — extended with new tests + `actionlint`

## 10. Deferred

**Per-plugin behavioral eval** (Sections 1-3 of the original brainstorm): a
custom `scripts/plugin_eval.py` + per-plugin fixtures with task.md +
expected.json + rubric.md. Would test "does each plugin component work as
advertised?" — narrow-but-deep localization that Terminal-Bench A/B cannot
provide.

Defer trigger: if a Terminal-Bench A/B run surfaces a regression and we
cannot localize the cause to a specific plugin from the per-task table
alone, this spec becomes the natural follow-up. Concretely: if
`tb-005-network-fetch` flips from "A passes, B fails" to "A fails, B
passes" and we can't grep the diff to find why, we need per-plugin fixtures.

If a future spec reintroduces this, the existing design sections from this
brainstorm session are recoverable from git history.
