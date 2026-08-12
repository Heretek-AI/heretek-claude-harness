---
date: 2026-08-12
topic: aggregate-results-aggregator
status: draft
---

# Aggregator: harbor trial `result.json` → `summary.json`

> Date: 2026-08-12. Follow-on to
> [2026-08-11-harbor-terminal-bench-ab-design.md](2026-08-11-harbor-terminal-bench-ab-design.md).
> Closes [issue #236](https://github.com/Heretek-AI/heretek-claude-harness/issues/236).

## 1. Summary

A small post-processing script (`scripts/aggregate_results.py`) that walks
harbor's per-trial `result.json` files and emits a top-level
`summary.json` per agent. Invoked from `scripts/terminal_bench_ab.sh`
after each `harbor run`. Closes the only remaining functional gap in the
Terminal-Bench A/B pipeline shipped in
[#235](https://github.com/Heretek-AI/heretek-claude-harness/pull/235):
without an aggregator, `comparison_report.py` would exit 1 with
`FileNotFoundError` on a real harbor run.

## 2. Harbor 0.21.0 trial schema (verified 2026-08-12)

Read from `harbor/models/trial/paths.py` and
`harbor/models/trial/result.py` in the installed harbor source.

**Per-trial directory** (one per trial, sibling to `result.json`,
`config.json`, `lock.json`, `trial.log`):

```
<jobs-dir>/<job-name>/<trial-name>/
├── agent/         # Subdirectory; harbor's claude-code adapter writes here.
├── verifier/      # Subdirectory; contains reward.txt + reward.json.
├── artifacts/
├── config.json
├── lock.json
├── result.json    # TrialResult (pydantic model, JSON-encoded).
└── trial.log
```

**Per-trial `result.json`** is a `TrialResult` (harbor's pydantic model).
Relevant fields for aggregation:

| Path | Type | Meaning |
|---|---|---|
| `task_name` | `str` | Task ID (e.g. `tb-001-fix-permissions`). |
| `verifier_result.rewards` | `dict[str, float\|int]` | Verifier-written rewards. Pass = any value == `1.0`. |
| `agent_result.n_input_tokens` | `int` | Input tokens (includes cache). |
| `agent_result.n_cache_tokens` | `int` | Cache-hit tokens. |
| `agent_result.n_output_tokens` | `int` | Output tokens. |
| `agent_result.cost_usd` | `float` | Total USD cost (harbor's own basis). |
| `started_at` | `datetime` (ISO 8601) | Trial start. |
| `finished_at` | `datetime` (ISO 8601) | Trial end. |
| `agent_info.model_info.name` | `str` | Model name (e.g. `claude-sonnet-5`). |

> **Note:** `HARBOR_NOTES.md` carries a stale schema (claims a `trials/`
> subdir, `trajectory.json`, `agent.log`, `env.log`, `verifier.log` files).
> Harbor 0.21.0 ships the layout above. Corrected as part of this spec.

> **Note:** Harbor DOES write a job-level `<jobs-dir>/<job-name>/result.json`
> (a `JobResult` with aggregated `JobStats` and the same `trial_results`
> list). Issue #236 framed this as "harbor does NOT produce a top-level
> summary.json" — technically true (different filename) but the data is
> there. We choose per-trial walking anyway (see §3).

## 3. Architecture

**File layout.**

```
scripts/
├── aggregate_results.py             # NEW — per-trial walker → summary.json
├── terminal_bench_ab.sh             # MODIFIED — invokes aggregator after each harbor run
├── comparison_report.py             # EXISTING — unchanged; consumes summary.json
└── HARBOR_NOTES.md                  # MODIFIED — schema corrected, Follow-up section replaced

tests/
├── test_aggregate_results.py        # NEW — 6+ hermetic tests
└── fixtures/aggregate_results/
    └── mixed-3/                     # NEW — synthetic trial dirs for fixture-based tests (optional)
```

**Single-responsibility split.** `aggregate_results.py` does ONE thing:
turn harbor's per-trial output into the `summary.json` shape that
`comparison_report.load_summary` expects. Pure stdlib. No harbor import
(the script runs after harbor is done; reading the JSON files harbor
wrote is enough).

**Why per-trial walking instead of harbor's job-level `result.json`.**

- Robust to partial runs. If harbor dies mid-job (Docker timeout, API
  error, OOM), the trial dirs that completed are still usable. The
  job-level file is written only after the run completes.
- Hermetic tests. Synthetic trial dirs (each containing a single
  `result.json` matching harbor's `TrialResult` shape) cover all edge
  cases without touching harbor internals.
- Issue #236's design. The issue explicitly chose per-trial walking;
  this spec confirms the choice now that the actual schema is known.

**Why not import harbor.** Two reasons: (1) harbor isn't installed in
the bare CI image; (2) the aggregator only needs JSON parsing + path
arithmetic — harbor's pydantic models would add coupling without value.

## 4. Aggregation logic

```bash
scripts/aggregate_results.py \
  --jobs-dir    ./results/agent-a/jobs \
  --agent-label agent-a-with-heretek \
  --model       "$ANTHROPIC_MODEL" \
  --commit-sha  "$GITHUB_SHA" \
  --output      ./results/agent-a/summary.json
```

**Per-trial field extraction** (pure-Python, no harbor import):

```python
trial = json.loads((trial_dir / "result.json").read_text())

rewards = (trial.get("verifier_result") or {}).get("rewards") or {}
if not rewards:
    log_warning(f"trial {trial['task_name']}: no verifier_result.rewards, skipping")
    continue
verdict = "pass" if any(v == 1.0 for v in rewards.values()) else "fail"
ctx = trial.get("agent_result") or {}
tokens = (ctx.get("n_input_tokens") or 0) + (ctx.get("n_output_tokens") or 0)

started = parse_iso(trial.get("started_at"))
finished = parse_iso(trial.get("finished_at"))
wall_clock_sec = int((finished - started).total_seconds()) if started and finished else 0

per_task.append({
    "task_id": trial["task_name"],
    "verdict": verdict,
    "wall_clock_sec": wall_clock_sec,
    "tokens": tokens,
})
```

**Token counting policy.** `n_input_tokens + n_output_tokens`. The
`n_input_tokens` field already includes cache reads per harbor's
docstring, and this is the basis harbor's own `cost_usd` uses. Documented
in the script's module docstring.

**Aggregate.** Match the `Summary` dataclass in `scripts/comparison_report.py:36-48` exactly:

```python
n_tasks = len(per_task)
passed = sum(1 for t in per_task if t["verdict"] == "pass")
failed = n_tasks - passed
pass_rate = passed / n_tasks if n_tasks else 0.0
wall_clock_sec_total = sum(t["wall_clock_sec"] for t in per_task)
wall_clock_sec_p50 = median(t["wall_clock_sec"] for t in per_task) if per_task else 0
tokens_total = sum(t["tokens"] for t in per_task)

summary = {
    "agent": agent_label,
    "model": model,
    "commit_sha": commit_sha,
    "heretek_harness": agent_label.endswith("with-heretek"),
    "n_tasks": n_tasks,
    "passed": passed,
    "failed": failed,
    "pass_rate": pass_rate,
    "wall_clock_sec_total": wall_clock_sec_total,
    "wall_clock_sec_p50": wall_clock_sec_p50,
    "tokens_total": tokens_total,
    "per_task": per_task,
}
output_path.write_text(json.dumps(summary, indent=2))
```

The `heretek_harness` flag is derived from the agent label
(endswith `with-heretek`). This avoids a new CLI flag.

## 5. Edge cases

| Case | Behavior |
|---|---|
| `--jobs-dir` empty / doesn't exist | Emit zero summary (n_tasks=0, all counts 0). Exit 0. |
| No `result.json` in any trial dir | Same as empty. |
| Trial `result.json` malformed JSON | Log warning to stderr, skip trial, count neither pass nor fail. |
| `verifier_result.rewards` absent or empty | Skip trial (counts as not-pass), log warning. |
| `verifier_result.rewards` has values but none == 1.0 | Verdict = "fail". (Rewards can be floats; we only credit 1.0.) |
| `agent_result` absent | tokens=0, wall_clock=0 for that trial. Don't skip — verdict still counts. |
| `started_at` / `finished_at` missing or unparseable | wall_clock=0. Don't skip. |
| Multiple job dirs under `--jobs-dir` (harbor resume) | Use the most recently modified one (`max(p.stat().st_mtime for p in jobs_dir.iterdir())`). |
| `comparison_report.load_summary` rejects output | Round-trip test in `test_aggregate_results.py` catches drift between aggregator schema and `Summary` dataclass. |

`comparison_report.py` is unchanged. It already handles `n_tasks=0`
gracefully (zero deltas across all metrics).

## 6. Wiring into `terminal_bench_ab.sh`

After each `harbor run` (10 new lines total, mirrored for both agents):

```bash
echo "[terminal_bench_ab] aggregating results for agent A -> ${RESULTS_DIR}/agent-a/summary.json"
python scripts/aggregate_results.py \
  --jobs-dir    "$AGENT_A_JOBS" \
  --agent-label agent-a-with-heretek \
  --model       "$ANTHROPIC_MODEL" \
  --commit-sha  "${GITHUB_SHA:-local}" \
  --output      "${RESULTS_DIR}/agent-a/summary.json"

echo "[terminal_bench_ab] aggregating results for agent B -> ${RESULTS_DIR}/agent-b/summary.json"
python scripts/aggregate_results.py \
  --jobs-dir    "$AGENT_B_JOBS" \
  --agent-label agent-b-baseline \
  --model       "$ANTHROPIC_MODEL" \
  --commit-sha  "${GITHUB_SHA:-local}" \
  --output      "${RESULTS_DIR}/agent-b/summary.json"
```

`scripts/ci.sh` already runs `pytest -q` (no glob) — new test file is
picked up automatically.

## 7. Testing

`tests/test_aggregate_results.py` — 6 hermetic tests, each builds
synthetic trial dirs under `tmp_path`:

| Test | Asserts |
|---|---|
| `test_all_pass` | 4 trials, all pass. `pass_rate=1.0`, `failed=0`, `per_task` has 4 entries. |
| `test_all_fail` | 4 trials, all fail. `pass_rate=0.0`, `passed=0`. |
| `test_mixed_split` | 3 trials (2 pass, 1 fail). `passed=2`, `failed=1`, `pass_rate≈0.667`. |
| `test_empty_jobs_dir` | Empty `tmp_path` dir. `n_tasks=0`, exit 0, file written with zeros. |
| `test_verdict_absent` | Trial with no `verifier_result.rewards`. Logged warning, skipped from `n_tasks`, no crash. |
| `test_tokens_and_wall_clock_aggregated` | 3 trials with varied tokens + wall_clock. `tokens_total` is sum, `wall_clock_sec_p50` is median, `wall_clock_sec_total` is sum. |
| `test_round_trip_through_summary_dataclass` | Output file round-trips through `comparison_report.load_summary` without raising. |

A small fixture helper:

```python
def _write_trial(jobs_dir: Path, task_name: str, *, pass_: bool, tokens_in: int = 0,
                 tokens_out: int = 0, started: str = "2026-08-12T00:00:00Z",
                 finished: str = "2026-08-12T00:01:00Z") -> None:
    job_dir = jobs_dir / "job-1"
    trial_dir = job_dir / task_name
    trial_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_name": task_name,
        "verifier_result": {"rewards": {"reward": 1.0 if pass_ else 0.0}},
        "agent_result": {"n_input_tokens": tokens_in, "n_output_tokens": tokens_out},
        "started_at": started,
        "finished_at": finished,
    }
    (trial_dir / "result.json").write_text(json.dumps(payload))
```

This helper is the only fixture the tests share — extracted into
`tests/_factories.py` per the existing convention (`tests/_factories.py`
already exists for `test_terminal_bench_*` factories).

## 8. HARBOR_NOTES.md corrections

Two changes:

1. **Remove** the "Follow-up: `summary.json` aggregation" section
   (lines 123-137 of the current file). **Replace** with a one-line
   note: "Per-agent `summary.json` is aggregated from per-trial
   `result.json` by `scripts/aggregate_results.py`."

2. **Correct** the "Output directory structure" section (lines 45-65).
   Replace the stale `trials/<trial-id>/...` shape with the verified
   harbor 0.21.0 layout from §2 of this spec. Notes on `agent/`
   (subdir, not file), `verifier/` (subdir), and the absence of
   `trajectory.json` / `agent.log` / `env.log` files.

These are pure-doc corrections. No runtime behavior change.

## 9. Out of scope

- `--install-only` smoke testing of harbor. Issue #236 mentions it as a
  "smoke test" path; deferred. The hermetic tests in §7 cover the
  aggregator logic without needing harbor.
- Statistical significance (McNemar's test, bootstrap CIs). Excluded
  from [#235](https://github.com/Heretek-AI/heretek-claude-harness/pull/235);
  the spec deliberately ships raw Δ until we run more than 8 tasks.
- Per-concurrency timing breakdown, resume-from-checkpoint, custom
  Harbor-native `BaseInstalledAgent` subclass.
- Splitting `tokens` into `n_input_tokens` / `n_cache_tokens` /
  `n_output_tokens` in `summary.json`. Flat `tokens_total` keeps
  `comparison_report.py` unchanged.

## 10. Estimated scope

| File | Δ lines |
|---|---|
| `scripts/aggregate_results.py` | +170 (new) |
| `tests/test_aggregate_results.py` | +110 (new) |
| `tests/_factories.py` | +25 (factory helper) |
| `scripts/terminal_bench_ab.sh` | +22 (two aggregator invocations + comments) |
| `scripts/HARBOR_NOTES.md` | ~10 (schema correction + replace Follow-up) |
| **Total** | ~340 |

## 11. References

- [Issue #236](https://github.com/Heretek-AI/heretek-claude-harness/issues/236)
- [PR #235](https://github.com/Heretek-AI/heretek-claude-harness/pull/235) — terminal-bench-ab
- [`docs/superpowers/specs/2026-08-11-harbor-terminal-bench-ab-design.md`](2026-08-11-harbor-terminal-bench-ab-design.md) — parent spec
- [`scripts/comparison_report.py`](../../scripts/comparison_report.py) — `Summary` and `PerTaskResult` dataclasses
- [`scripts/HARBOR_NOTES.md`](../../scripts/HARBOR_NOTES.md) — current (stale) harbor notes
- Harbor 0.21.0 source (installed via `uv tool install harbor==0.210`): `${HOME}/.local/share/uv/tools/harbor/lib/python3.14/site-packages/harbor/models/trial/paths.py`, `harbor/models/trial/result.py`, `harbor/models/agent/context.py`, `harbor/models/verifier/result.py`, `harbor/job.py`
