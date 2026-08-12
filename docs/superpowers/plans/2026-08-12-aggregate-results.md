# Aggregate Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `scripts/aggregate_results.py` which walks harbor 0.21.0 per-trial `result.json` files and emits a `summary.json` matching the existing `Summary` dataclass. Wire it into `terminal_bench_ab.sh` and correct the stale schema in `HARBOR_NOTES.md`.

**Architecture:** Single-purpose Python script (pure stdlib, ~170 lines) that globs the most recent `<jobs-dir>/<job-name>/<trial-name>/result.json`, extracts verdict/tokens/wall_clock via harbor's `TrialResult` schema, and writes `summary.json`. Called from `terminal_bench_ab.sh` after each `harbor run`. Hermetic tests with synthetic trial dirs under `tmp_path`.

**Tech Stack:** Python 3.10+ (datetime, statistics, json, argparse, pathlib), bash wiring, pytest. No harbor import.

## Global Constraints

These apply to every task. Copy values verbatim from the spec:

- **Spec:** `docs/superpowers/specs/2026-08-12-aggregate-results-design.md` — every requirement below traces to a section there.
- **Harbor 0.21.0 trial schema** (verified 2026-08-12 from `harbor/models/trial/paths.py` and `harbor/models/trial/result.py`):
  ```
  <jobs-dir>/<job-name>/<trial-name>/
  ├── agent/  verifier/  artifacts/
  ├── config.json  lock.json  result.json  trial.log
  ```
- **Per-trial `result.json` is a `TrialResult` pydantic model.** Relevant fields: `task_name`, `verifier_result.rewards` (dict[str, float|int]), `agent_result.{n_input_tokens, n_cache_tokens, n_output_tokens, cost_usd}`, `started_at`, `finished_at`, `agent_info.model_info.name`.
- **Verdict rule:** pass iff any value in `verifier_result.rewards` equals `1.0`. Empty rewards → skip trial.
- **Token counting policy:** `tokens = agent_result.n_input_tokens + agent_result.n_output_tokens`. `n_input_tokens` already includes cache per harbor's docstring; matches harbor's own `cost_usd` basis.
- **Wall-clock:** `int((finished_at - started_at).total_seconds())`. 0 if either timestamp missing.
- **`heretek_harness` flag: derived from `agent_label.endswith("with-heretek")`.** No new CLI flag.
- **`summary.json` schema** must match the `Summary` dataclass in `scripts/comparison_report.py:36-48` exactly — round-trip through `load_summary` must succeed.
- **Pure stdlib.** No harbor import. No pip install.
- **Pre-commit mandatory** on every commit (per project `CLAUDE.md`): `pre-commit run --all-files`.
- **`scripts/ci.sh` mandatory before PR** (per project `CLAUDE.md`).
- **Co-Authored-By** trailer required on every commit: `Co-Authored-By: Claude <noreply@anthropic.com>`.
- **No placeholders / TBD / TODO** in any committed file. Every step below contains the actual code.
- **Project conventions:** follow the existing script structure (shebang, `from __future__ import annotations`, `from pathlib import Path`, `if __name__ == "__main__": sys.exit(...)`).
- **Test factory convention:** share helpers via `tests/_factories.py` (already exists; extend it).

---

### Task 1: TDD `aggregate_jobs_dir` core aggregation

**Files:**
- Create: `scripts/aggregate_results.py`
- Create: `tests/test_aggregate_results.py`

**Interfaces:**
- Consumes: `jobs_dir: Path` (harbor's `--jobs-dir`); `agent_label: str`, `model: str`, `commit_sha: str` (kwargs).
- Produces: `aggregate_jobs_dir(jobs_dir, *, agent_label, model, commit_sha) -> dict` — returns a dict matching the `Summary` dataclass. No file I/O yet.

- [ ] **Step 1: Write failing tests in `tests/test_aggregate_results.py`**

Create `tests/test_aggregate_results.py`:

```python
"""Tests for scripts/aggregate_results.py — per-trial walker → summary dict."""

from __future__ import annotations

import json
from pathlib import Path

from aggregate_results import aggregate_jobs_dir


def _write_trial(
    jobs_dir: Path,
    task_name: str,
    *,
    verdict_pass: bool = True,
    n_input_tokens: int = 0,
    n_output_tokens: int = 0,
    started_at: str = "2026-08-12T00:00:00Z",
    finished_at: str = "2026-08-12T00:01:00Z",
    job_name: str = "job-1",
) -> None:
    """Write a single trial result.json under <jobs_dir>/<job_name>/<task_name>/."""
    trial_dir = jobs_dir / job_name / task_name
    trial_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_name": task_name,
        "verifier_result": {"rewards": {"reward": 1.0 if verdict_pass else 0.0}},
        "agent_result": {
            "n_input_tokens": n_input_tokens,
            "n_output_tokens": n_output_tokens,
        },
        "started_at": started_at,
        "finished_at": finished_at,
    }
    (trial_dir / "result.json").write_text(json.dumps(payload))


def _make_jobs_dir(tmp_path: Path) -> Path:
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    return jobs


def test_all_pass(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    for i in range(4):
        _write_trial(jobs, f"tb-{i:03d}", verdict_pass=True)
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 4
    assert summary["passed"] == 4
    assert summary["failed"] == 0
    assert summary["pass_rate"] == 1.0
    assert len(summary["per_task"]) == 4


def test_all_fail(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    for i in range(4):
        _write_trial(jobs, f"tb-{i:03d}", verdict_pass=False)
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["passed"] == 0
    assert summary["failed"] == 4
    assert summary["pass_rate"] == 0.0


def test_mixed_split(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    for tid in ["tb-001", "tb-002", "tb-003"]:
        _write_trial(jobs, tid, verdict_pass=(tid != "tb-003"))
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["pass_rate"] == 2 / 3
    assert [t["task_id"] for t in summary["per_task"]] == ["tb-001", "tb-002", "tb-003"]


def test_empty_jobs_dir(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 0
    assert summary["passed"] == 0
    assert summary["failed"] == 0
    assert summary["pass_rate"] == 0.0
    assert summary["per_task"] == []
    assert summary["wall_clock_sec_total"] == 0
    assert summary["wall_clock_sec_p50"] == 0
    assert summary["tokens_total"] == 0


def test_jobs_dir_does_not_exist(tmp_path: Path) -> None:
    """Missing jobs-dir is a no-op; emit zero summary."""
    summary = aggregate_jobs_dir(
        tmp_path / "does-not-exist",
        agent_label="agent-a-with-heretek",
        model="m",
        commit_sha="abc",
    )
    assert summary["n_tasks"] == 0
    assert summary["passed"] == 0


def test_verdict_absent_skips_trial(tmp_path: Path) -> None:
    """A trial with no verifier_result.rewards is skipped (not counted in n_tasks)."""
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-good", verdict_pass=True)
    # Manually overwrite the second trial to have no rewards.
    bad_dir = jobs / "job-1" / "tb-bad"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "result.json").write_text(json.dumps({
        "task_name": "tb-bad",
        "verifier_result": {"rewards": {}},
        "agent_result": {"n_input_tokens": 0, "n_output_tokens": 0},
        "started_at": "2026-08-12T00:00:00Z",
        "finished_at": "2026-08-12T00:01:00Z",
    }))
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 1
    assert summary["passed"] == 1
    assert summary["failed"] == 0
    assert [t["task_id"] for t in summary["per_task"]] == ["tb-good"]


def test_tokens_and_wall_clock_aggregated(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(
        jobs, "tb-001",
        n_input_tokens=100, n_output_tokens=50,
        started_at="2026-08-12T00:00:00Z", finished_at="2026-08-12T00:01:00Z",  # 60s
    )
    _write_trial(
        jobs, "tb-002",
        n_input_tokens=200, n_output_tokens=75,
        started_at="2026-08-12T00:01:00Z", finished_at="2026-08-12T00:03:00Z",  # 120s
    )
    _write_trial(
        jobs, "tb-003",
        n_input_tokens=300, n_output_tokens=100,
        started_at="2026-08-12T00:03:00Z", finished_at="2026-08-12T00:06:00Z",  # 180s
    )
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["tokens_total"] == 100 + 50 + 200 + 75 + 300 + 100
    assert summary["wall_clock_sec_total"] == 60 + 120 + 180
    assert summary["wall_clock_sec_p50"] == 120  # median of [60, 120, 180]


def test_heretek_harness_flag_derived_from_label(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-001", job_name="a-jobs")
    a = aggregate_jobs_dir(jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc")
    b = aggregate_jobs_dir(jobs, agent_label="agent-b-baseline", model="m", commit_sha="abc")
    assert a["heretek_harness"] is True
    assert b["heretek_harness"] is False


def test_picks_most_recent_job_dir(tmp_path: Path) -> None:
    """If harbor was resumed, multiple job dirs exist; use the most recent mtime."""
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-old", job_name="job-old")
    _write_trial(jobs, "tb-new", job_name="job-new")
    # Force job-new to be more recent.
    import os
    (jobs / "job-new").touch()
    os.utime(jobs / "job-new", (2_000_000_000, 2_000_000_000))
    os.utime(jobs / "job-old", (1_000_000_000, 1_000_000_000))
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert [t["task_id"] for t in summary["per_task"]] == ["tb-new"]


def test_malformed_json_skipped(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-good")
    bad_dir = jobs / "job-1" / "tb-bad"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "result.json").write_text("not json{{{")
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 1
    assert [t["task_id"] for t in summary["per_task"]] == ["tb-good"]


def test_missing_agent_result_zeros_tokens_and_wall_clock(tmp_path: Path) -> None:
    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-001")
    # Overwrite to remove agent_result.
    (jobs / "job-1" / "tb-001" / "result.json").write_text(json.dumps({
        "task_name": "tb-001",
        "verifier_result": {"rewards": {"reward": 1.0}},
        "started_at": "2026-08-12T00:00:00Z",
        "finished_at": "2026-08-12T00:01:00Z",
    }))
    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )
    assert summary["n_tasks"] == 1
    assert summary["passed"] == 1
    assert summary["tokens_total"] == 0
    assert summary["wall_clock_sec_total"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aggregate_results.py -v`
Expected: `ImportError: No module named 'aggregate_results'`.

- [ ] **Step 3: Implement `scripts/aggregate_results.py`**

Create `scripts/aggregate_results.py`:

```python
"""Aggregate harbor per-trial result.json files into a summary.json.

Walks <jobs-dir>/<job-name>/<trial-name>/result.json for each trial in
the most recent job directory, extracts verdict + tokens + wall_clock
from harbor's TrialResult schema, and writes a single summary.json
matching scripts.comparison_report.Summary.

Usage:
    python scripts/aggregate_results.py \\
        --jobs-dir ./results/agent-a/jobs \\
        --agent-label agent-a-with-heretek \\
        --model "$ANTHROPIC_MODEL" \\
        --commit-sha "$GITHUB_SHA" \\
        --output ./results/agent-a/summary.json

Token counting policy: tokens = agent_result.n_input_tokens +
agent_result.n_output_tokens. The n_input_tokens field already includes
cache reads per harbor's docstring; matches harbor's own cost_usd basis.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import median


def _log(msg: str) -> None:
    """Write a warning to stderr without breaking JSON output."""
    print(f"aggregate_results: {msg}", file=sys.stderr)


def _parse_iso(s: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp; return None on any failure."""
    if not s:
        return None
    try:
        # harbor writes 'Z' suffix; normalize for fromisoformat.
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_trial(result_path: Path) -> dict | None:
    """Extract per-trial fields from a harbor TrialResult result.json.

    Returns a dict with keys: task_id, verdict, wall_clock_sec, tokens.
    Returns None if the trial should be skipped (missing rewards, malformed JSON).
    """
    try:
        trial = json.loads(result_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        _log(f"trial {result_path.parent.name}: malformed JSON ({e}), skipping")
        return None

    task_name = trial.get("task_name")
    if not task_name:
        _log(f"trial {result_path.parent.name}: no task_name, skipping")
        return None

    rewards = (trial.get("verifier_result") or {}).get("rewards") or {}
    if not rewards:
        _log(f"trial {task_name}: no verifier_result.rewards, skipping")
        return None

    verdict = "pass" if any(v == 1.0 for v in rewards.values()) else "fail"

    ctx = trial.get("agent_result") or {}
    tokens = (ctx.get("n_input_tokens") or 0) + (ctx.get("n_output_tokens") or 0)

    started = _parse_iso(trial.get("started_at"))
    finished = _parse_iso(trial.get("finished_at"))
    if started and finished:
        wall_clock_sec = max(0, int((finished - started).total_seconds()))
    else:
        wall_clock_sec = 0

    return {
        "task_id": task_name,
        "verdict": verdict,
        "wall_clock_sec": wall_clock_sec,
        "tokens": tokens,
    }


def _latest_job_dir(jobs_dir: Path) -> Path | None:
    """Pick the most recently modified subdir of jobs_dir (harbor resume support)."""
    subdirs = [p for p in jobs_dir.iterdir() if p.is_dir()]
    if not subdirs:
        return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)


def aggregate_jobs_dir(
    jobs_dir: Path,
    *,
    agent_label: str,
    model: str,
    commit_sha: str,
) -> dict:
    """Aggregate harbor's per-trial result.json into a Summary dict.

    Returns a dict matching the Summary dataclass in
    scripts.comparison_report (load_summary can read it back).
    """
    per_task: list[dict] = []

    if jobs_dir.is_dir():
        job_dir = _latest_job_dir(jobs_dir)
        if job_dir is not None:
            for trial_dir in sorted(job_dir.iterdir()):
                if not trial_dir.is_dir():
                    continue
                result_path = trial_dir / "result.json"
                if not result_path.is_file():
                    continue
                record = _extract_trial(result_path)
                if record is not None:
                    per_task.append(record)

    n_tasks = len(per_task)
    passed = sum(1 for t in per_task if t["verdict"] == "pass")
    failed = n_tasks - passed
    pass_rate = passed / n_tasks if n_tasks else 0.0
    wall_clocks = [t["wall_clock_sec"] for t in per_task]

    return {
        "agent": agent_label,
        "model": model,
        "commit_sha": commit_sha,
        "heretek_harness": agent_label.endswith("with-heretek"),
        "n_tasks": n_tasks,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "wall_clock_sec_total": sum(wall_clocks),
        "wall_clock_sec_p50": int(median(wall_clocks)) if wall_clocks else 0,
        "tokens_total": sum(t["tokens"] for t in per_task),
        "per_task": per_task,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aggregate_results")
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--agent-label", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = aggregate_jobs_dir(
        args.jobs_dir,
        agent_label=args.agent_label,
        model=args.model,
        commit_sha=args.commit_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aggregate_results.py -v`
Expected: all 11 tests green.

If failures: re-check that the per-trial `result.json` shapes match the
test `_write_trial` helper, and that the verdict rule (any value == 1.0)
is implemented verbatim.

- [ ] **Step 5: Commit**

```bash
git add scripts/aggregate_results.py tests/test_aggregate_results.py
git commit -m "feat(scripts): aggregate_results.py per-trial walker

Reads harbor 0.21.0 per-trial result.json (verifier_result.rewards +
agent_result token fields + started_at/finished_at) and emits a dict
matching the Summary dataclass in scripts/comparison_report.py. Pure
stdlib, no harbor import. 11 hermetic tests with synthetic trial dirs.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Run pre-commit per project `CLAUDE.md`: `pre-commit run --all-files`.

---

### Task 2: Add `_write_trial` factory helper to `tests/_factories.py` + round-trip test

**Files:**
- Modify: `tests/_factories.py` (append helper)
- Modify: `tests/test_aggregate_results.py` (use factory + add round-trip test)

**Interfaces:**
- Consumes: same `_write_trial(jobs_dir, task_name, ...)` shape used in Task 1.
- Produces: shared factory for any future test that needs to synthesize harbor trial dirs.

**Why shared.** Right now `_write_trial` lives in `tests/test_aggregate_results.py`. The spec's "Mixed" smoke test in §6 may need trial dirs in the future, and the spec explicitly recommends extracting helpers into `tests/_factories.py` per the existing convention.

- [ ] **Step 1: Append `write_trial` to `tests/_factories.py`**

Add `import json` to the top of `tests/_factories.py` alongside the existing imports. Then append to the end of `tests/_factories.py`:

```python
def write_trial(
    jobs_dir: Path,
    task_name: str,
    *,
    verdict_pass: bool = True,
    n_input_tokens: int = 0,
    n_output_tokens: int = 0,
    started_at: str = "2026-08-12T00:00:00Z",
    finished_at: str = "2026-08-12T00:01:00Z",
    job_name: str = "job-1",
) -> None:
    """Write a single harbor-style trial result.json.

    Mirrors harbor 0.21.0's TrialResult schema (only the fields the
    aggregator reads). Used by aggregate_results tests; future harbor-
    related tests can reuse this.
    """
    trial_dir = jobs_dir / job_name / task_name
    trial_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_name": task_name,
        "verifier_result": {"rewards": {"reward": 1.0 if verdict_pass else 0.0}},
        "agent_result": {
            "n_input_tokens": n_input_tokens,
            "n_output_tokens": n_output_tokens,
        },
        "started_at": started_at,
        "finished_at": finished_at,
    }
    (trial_dir / "result.json").write_text(json.dumps(payload))
```

- [ ] **Step 2: Refactor `tests/test_aggregate_results.py` to use the factory**

Replace the local `_write_trial` function in `tests/test_aggregate_results.py` with an import:

```python
from tests._factories import write_trial as _write_trial  # noqa: F401
```

Remove the local `_write_trial` definition.

- [ ] **Step 3: Add round-trip test to `tests/test_aggregate_results.py`**

Append to `tests/test_aggregate_results.py`:

```python
def test_round_trip_through_summary_dataclass(tmp_path: Path) -> None:
    """Output dict must round-trip through comparison_report.load_summary."""
    from comparison_report import load_summary

    jobs = _make_jobs_dir(tmp_path)
    _write_trial(jobs, "tb-001", verdict_pass=True, n_input_tokens=100, n_output_tokens=50)
    _write_trial(jobs, "tb-002", verdict_pass=False, n_input_tokens=200, n_output_tokens=75)

    summary = aggregate_jobs_dir(
        jobs, agent_label="agent-a-with-heretek", model="m", commit_sha="abc"
    )

    # Write to a file and load back via the prod code path.
    out_path = tmp_path / "summary.json"
    out_path.write_text(json.dumps(summary))
    loaded = load_summary(out_path)

    assert loaded.agent == "agent-a-with-heretek"
    assert loaded.passed == 1
    assert loaded.failed == 1
    assert loaded.n_tasks == 2
    assert loaded.tokens_total == 100 + 50 + 200 + 75
    assert len(loaded.per_task) == 2
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aggregate_results.py -v`
Expected: 12 tests green (11 original + 1 round-trip).

If failures: most likely the local `_write_trial` import didn't take; verify the import line is at the top of the test file, not inside a function.

- [ ] **Step 5: Commit**

```bash
git add tests/_factories.py tests/test_aggregate_results.py
git commit -m "test: extract write_trial factory + round-trip through Summary

Shared trial-dir factory in tests/_factories.py per the existing
convention. Round-trip test pins the aggregator output shape against
the prod load_summary code path — catches schema drift between the
aggregator and the Summary dataclass.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Run pre-commit: `pre-commit run --all-files`.

---

### Task 3: Wire aggregator into `scripts/terminal_bench_ab.sh`

**Files:**
- Modify: `scripts/terminal_bench_ab.sh` (add two aggregator invocations after the harbor runs)

**Interfaces:**
- Calls `python scripts/aggregate_results.py` with the same env vars the script already uses.

- [ ] **Step 1: Read the current `scripts/terminal_bench_ab.sh`**

Run: `cat scripts/terminal_bench_ab.sh`
Confirm the structure: AGENT_A_JOBS / AGENT_B_JOBS are set, harbor runs twice, then echo "both agents complete".

- [ ] **Step 2: Add aggregator invocations before the final echo**

Replace the existing trailing block (everything after the second `harbor run` invocation, replacing the `echo "[terminal_bench_ab] both agents complete"` line) with:

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

echo "[terminal_bench_ab] both agents complete"
```

Update the script's header comment block too — add a line noting the aggregator step:

```bash
# Per-agent results land in:
#   ${RESULTS_DIR}/agent-a/jobs/<job-name>/trials/<trial-id>/...
#   ${RESULTS_DIR}/agent-b/jobs/<job-name>/trials/<trial-id>/...
# After each agent's harbor run, aggregate_results.py emits:
#   ${RESULTS_DIR}/agent-a/summary.json
#   ${RESULTS_DIR}/agent-b/summary.json
# (consumed by scripts/comparison_report.py).
```

- [ ] **Step 3: Verify the existing `test_terminal_bench_ab_sh.py` tests still pass**

Run: `pytest tests/test_terminal_bench_ab_sh.py -v`
Expected: all 9 tests green.

If failures: most likely the fake harbor binary in the test fixture
doesn't write a `result.json`, so the aggregator will see zero trials
and emit a zero summary. The new aggregate invocations should still
exit 0. If a test fails because it asserts results dir shape, regenerate
the test expectations or add a `summary.json` write to the fake harbor.

> **Note:** The existing fake harbor in `tests/test_terminal_bench_ab_sh.py:25-27` does NOT write any `result.json`. It only logs argv and exits 0. After this task, the real shell script will invoke the aggregator which will see zero trials and emit a zero summary — but the existing tests don't assert on `summary.json` presence, so they should still pass.

- [ ] **Step 4: Manually verify the wire-up end-to-end**

```bash
mkdir -p /tmp/smoke-aggregate/plugins
mkdir -p /tmp/smoke-aggregate/results/agent-a/jobs/job-1/tb-001
mkdir -p /tmp/smoke-aggregate/results/agent-a/jobs/job-1/tb-002
mkdir -p /tmp/smoke-aggregate/results/agent-b/jobs/job-1/tb-001
mkdir -p /tmp/smoke-aggregate/results/agent-b/jobs/job-1/tb-002

cat > /tmp/smoke-aggregate/results/agent-a/jobs/job-1/tb-001/result.json <<'EOF'
{
  "task_name": "tb-001",
  "verifier_result": {"rewards": {"reward": 1.0}},
  "agent_result": {"n_input_tokens": 1000, "n_output_tokens": 500},
  "started_at": "2026-08-12T00:00:00Z",
  "finished_at": "2026-08-12T00:01:00Z"
}
EOF
cat > /tmp/smoke-aggregate/results/agent-a/jobs/job-1/tb-002/result.json <<'EOF'
{
  "task_name": "tb-002",
  "verifier_result": {"rewards": {"reward": 0.0}},
  "agent_result": {"n_input_tokens": 2000, "n_output_tokens": 800},
  "started_at": "2026-08-12T00:01:00Z",
  "finished_at": "2026-08-12T00:03:00Z"
}
EOF
# (Agent B same shape but with both pass...)

python scripts/aggregate_results.py \
  --jobs-dir /tmp/smoke-aggregate/results/agent-a/jobs \
  --agent-label agent-a-with-heretek \
  --model test-model \
  --commit-sha smoke \
  --output /tmp/smoke-aggregate/results/agent-a/summary.json

cat /tmp/smoke-aggregate/results/agent-a/summary.json
```

Expected: a valid summary.json with `n_tasks: 2, passed: 1, failed: 1, pass_rate: 0.5, tokens_total: 4300, wall_clock_sec_total: 180, wall_clock_sec_p50: 120, heretek_harness: true, per_task: [{tb-001: pass}, {tb-002: fail}]`.

- [ ] **Step 5: Commit**

```bash
git add scripts/terminal_bench_ab.sh
git commit -m "feat(scripts): aggregate_results invocations after each harbor run

terminal_bench_ab.sh now emits <results-dir>/agent-{a,b}/summary.json
matching the Summary dataclass. comparison_report.py can now consume
real harbor output without falling over on FileNotFoundError.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Run pre-commit: `pre-commit run --all-files`.

---

### Task 4: Correct `scripts/HARBOR_NOTES.md` schema + remove Follow-up section

**Files:**
- Modify: `scripts/HARBOR_NOTES.md`

**Interfaces:**
- Replace lines 45-65 (the "Output directory structure" section) with the verified harbor 0.21.0 schema.
- Replace lines 123-137 (the "Follow-up: `summary.json` aggregation" section) with a one-line note that aggregation is now handled by `aggregate_results.py`.

- [ ] **Step 1: Read the current `scripts/HARBOR_NOTES.md`**

Run: `cat scripts/HARBOR_NOTES.md`
Confirm the line numbers and content of the two sections being replaced.

- [ ] **Step 2: Replace the "Output directory structure" section (lines 45-65)**

Find the block that starts with `## Output directory structure` and ends just before `## Task filtering`. Replace it with:

```markdown
## Output directory structure (harbor 0.21.0, verified 2026-08-12)

Harbor writes per-job output to `<jobs-dir>/<job-name>/`. Each trial
directory contains:

```
<jobs-dir>/<job-name>/<trial-name>/
├── agent/         # Subdirectory; harbor's claude-code adapter writes here.
├── verifier/      # Subdirectory; contains reward.txt + reward.json.
├── artifacts/     # Collected artifacts from the environment.
├── config.json    # Resolved trial config.
├── lock.json      # Resolved trial inputs.
├── result.json    # TrialResult (pydantic model, JSON-encoded).
└── trial.log      # Logs from the trial.
```

The per-trial `result.json` is a `TrialResult` pydantic model. Fields
relevant to aggregation:

- `task_name` — task ID (e.g. `tb-001-fix-permissions`).
- `verifier_result.rewards` (`dict[str, float|int]`) — pass iff any value == 1.0.
- `agent_result.n_input_tokens` / `n_output_tokens` / `n_cache_tokens` / `cost_usd`.
- `started_at` / `finished_at` (ISO 8601) — wall-clock = `finished_at - started_at`.
- `agent_info.model_info.name` — model name.

**No** `trials/` subdir, **no** `trajectory.json`, **no** `agent.log`,
**no** `env.log`, **no** `verifier.log` files — those were recorded
from an older harbor version and are stale for 0.21.0.

Harbor ALSO writes a job-level `<jobs-dir>/<job-name>/result.json`
(`JobResult` with aggregated `JobStats` and the same `trial_results`
list). The aggregator does not consume this — it walks per-trial
files directly (robust to partial runs).
```

- [ ] **Step 3: Replace the "Follow-up: `summary.json` aggregation" section (lines 123-137)**

Find the block that starts with `## Follow-up: \`summary.json\` aggregation` and ends at the end of the file. Replace it with:

```markdown
## Per-agent `summary.json`

Per-agent `summary.json` is aggregated from per-trial `result.json`
files by `scripts/aggregate_results.py`, invoked after each `harbor run`
in `terminal_bench_ab.sh`. See
`docs/superpowers/specs/2026-08-12-aggregate-results-design.md` for
the schema and edge-case handling.
```

- [ ] **Step 4: Verify the file is well-formed**

Run: `cat scripts/HARBOR_NOTES.md`
Expected: no `trials/` subdir references, no `trajectory.json` references,
no `agent.log` references (other than the historical context if any),
the Follow-up section is replaced with the one-line pointer.

Run: `pre-commit run --all-files`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add scripts/HARBOR_NOTES.md
git commit -m "docs(scripts): correct harbor 0.21.0 schema + remove stale Follow-up

The 'Output directory structure' section was written from an older
harbor version; corrected for 0.21.0 (subdirs for agent/verifier, no
trajectory.json, no agent.log file). The 'Follow-up summary.json
aggregation' section is replaced with a one-line pointer to the
shipped aggregator.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Run pre-commit: `pre-commit run --all-files`.

---

### Task 5: Final verification — `scripts/ci.sh` clean

**Files:**
- Modify: none (pure verification)

**Interfaces:**
- Verifies: every test from Tasks 1–4 passes; the full local CI script is clean.

- [ ] **Step 1: Run the new tests**

```bash
pytest tests/test_aggregate_results.py -v
```

Expected: 12 tests green.

- [ ] **Step 2: Run the existing terminal-bench-ab tests**

```bash
pytest tests/test_terminal_bench_ab_sh.py tests/test_comparison_report.py tests/test_comparison_diff.py tests/test_no_secret_leak_in_issue.py tests/test_issue_body_schema.py tests/test_concurrency_group_yaml.py -v
```

Expected: all tests green.

- [ ] **Step 3: Run `scripts/ci.sh`**

```bash
bash scripts/ci.sh
```

Expected: `ci: OK` at the end. All steps pass.

If failures: re-run each suite individually to isolate; the most likely
regression is a circular import introduced by moving `write_trial` into
`tests/_factories.py` (Task 2). If `aggregate_results` can't be imported
from inside `_factories.py`, defer the import inside `write_trial`
(precedent: `tests/_factories.py` already does inline imports for
`comparison_report`).

- [ ] **Step 4: Final commit (no code changes; only if any incidental fixes were needed)**

If `scripts/ci.sh` was already clean in Step 3, skip this commit. If
you needed to fix a test or import, commit those fixes:

```bash
git add -A
git commit -m "fix: ci.sh clean across aggregate_results + existing tests

[describe what was fixed]

Co-Authored-By: Claude <noreply@anthropic.com>"
```

(This commit is conditional — skip if unnecessary.)

---

## Self-Review (against the spec)

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| §1 Summary | Task 1 (aggregator script) + Task 3 (wire-in) |
| §2 Harbor 0.21.0 trial schema | Task 1 (per-trial reading) + Task 4 (HARBOR_NOTES.md correction) |
| §3 Architecture (file layout, why per-trial, no harbor import) | Task 1 (script structure) |
| §4 Aggregation logic (verdict, tokens, wall_clock, aggregate) | Task 1 (`aggregate_jobs_dir`) |
| §5 Edge cases (empty dir, missing fields, multiple jobs, etc.) | Task 1 (11 tests cover each edge case) |
| §6 Wiring into `terminal_bench_ab.sh` | Task 3 |
| §7 Testing (6+ hermetic tests, factory helper) | Task 1 (11 tests) + Task 2 (factory + round-trip) |
| §8 HARBOR_NOTES.md corrections | Task 4 |
| §9 Out of scope | n/a (not implemented) |
| §10 Estimated scope | Tasks 1-4 match ~340 lines total |
| §11 References | n/a (informational) |

**Placeholder scan:** No "TBD", "TODO", "implement later", "fill in
details", "similar to Task N", or generic "add tests for the above"
language. The Task 2 placeholder note about vestigial imports is
explicit copy-paste guidance, not a placeholder.

**Type consistency:** `aggregate_jobs_dir(jobs_dir, *, agent_label, model,
commit_sha) -> dict` defined in Task 1 and consumed only in Task 2
(round-trip through `load_summary`). `_write_trial` (Task 1, local)
becomes `write_trial` (Task 2, shared via `tests/_factories.py`) — same
signature, just renamed and moved.

**One inconsistency caught during self-review and fixed inline:**
Task 2's helper had a vestigial `from aggregate_results import
aggregate_jobs_dir` plus a self-import `from ._factories import
write_trial` left over from an earlier draft. Replaced with the
corrected helper (no spurious imports).

**Spec requirement gaps:** None. All seven acceptance criteria from the
issue are covered:

1. ✅ `scripts/aggregate_results.py` exists — Task 1.
2. ✅ `tests/test_aggregate_results.py` with 5+ tests — Task 1 (11 tests) + Task 2 (1 more).
3. ✅ `terminal_bench_ab.sh` invokes aggregator — Task 3.
4. ✅ `scripts/ci.sh` still passes — Task 5.
5. ✅ Smoke test by manually synthesizing trial dirs — Task 3 Step 4.
6. ✅ `HARBOR_NOTES.md` Follow-up replaced — Task 4.

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-08-12-aggregate-results.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
