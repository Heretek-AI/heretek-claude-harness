# Harbor + Terminal-Bench A/B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a GitHub Action (`.github/workflows/terminal-bench-ab.yml`) that triggers on `push` to `main` and `workflow_dispatch`, runs two Claude Code agents via Harbor against Terminal-Bench 2 (one with the heretek harness via `--plugin-dir`, one without), and opens a per-run comparison GitHub issue.

**Architecture:** Two `harbor run` invocations in a single workflow job (Agent A: `claude-code` with `--ak config={plugin_dir}`; Agent B: `claude-code` baseline). Harbor writes per-agent results; a Python script `scripts/comparison_report.py` reads both `summary.json` files, computes a diff, renders a Markdown comparison, and the workflow opens a per-run GitHub issue via `gh`. Same model, same `ANTHROPIC_BASE_URL`/`AUTH_TOKEN`, same task set — only the harness differs.

**Tech Stack:** Bash (`scripts/terminal_bench_ab.sh`), Python 3.10+ (`scripts/comparison_report.py`), Harbor CLI (installed via `uv tool install harbor`), Terminal-Bench 2 dataset, `gh` CLI for issue creation, GitHub Actions YAML. Tests: `pytest` + `ruff` + `shellcheck` + `actionlint`.

## Global Constraints

These apply to every task in this plan. Copy values verbatim from the spec:

- **Spec:** `docs/superpowers/specs/2026-08-11-harbor-terminal-bench-ab-design.md` — every requirement below traces to a section there.
- **Trigger:** `on.push.branches: [main]` and `on.workflow_dispatch`. **No** scheduled `cron` trigger (intentional — pushed earlier draft mentioned `weekly`, removed in self-review).
- **Per-job env (from repo secrets):** `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `ANTHROPIC_AUTH_TOKEN`. Plus `HERETEK_PLUGIN_DIR: ${{ github.workspace }}/plugins`.
- **Permissions block:** `contents: read`, `issues: write`, `actions: write` (`actions: read` is wrong — `actions/upload-artifact@v4` requires write).
- **Concurrency:** `concurrency.group: terminal-bench-ab`, `concurrency.cancel-in-progress: true`.
- **Tier system:** `quick` (8 tasks, default), `full` (all), `custom` (user-supplied). For v1 the script runs the full dataset; tier filtering ships when harbor's task-filter syntax is confirmed.
- **Quick subset:** `scripts/tb_subset_quick.txt` — 8 Terminal-Bench 2 task IDs, hand-picked. Picked during Task 1.
- **Issue label:** `terminal-bench-ab`, `automated`. Title: `Terminal-Bench A/B: <7-char-sha> — <YYYY-MM-DD>`.
- **Coverage targets:** `scripts/comparison_report.py` ≥85%, `scripts/terminal_bench_ab.sh` ≥75%.
- **Secret scan:** `comparison_report.py` aborts render if `comparison.md` contains token-shaped strings (`sk-*`, `sk-cp-*`, `ghp_*`).
- **Artifact retention:** 30 days.
- **No placeholders / TBD / TODO** in any committed file. Every step below contains the actual code.
- **Co-Authored-By** trailer required on every commit: `Co-Authored-By: Claude <noreply@anthropic.com>`.
- **Pre-commit mandatory** on every commit (per project `CLAUDE.md`).
- **`scripts/ci.sh` mandatory before PR** (per project `CLAUDE.md`).
- **Harbor install:** `uv tool install harbor`.
- **Dataset version string:** `terminal-bench@2.0` (per harbor README).
- **Harbor long-form flags (per harbor README):** `--dataset`, `--agent`, `--model`, `--n-concurrent`, `--env`. Short forms (`-d`, `-a`, `-m`) also work. Other flags (`-o`, `--ak`, `--task`) are NOT documented in the README — implementer must run `harbor run --help` after install to discover them and document findings in `scripts/HARBOR_NOTES.md` before writing the script that uses them.

## File Structure

**New files:**

| File | Responsibility |
|---|---|
| `scripts/terminal_bench_ab.sh` | Runs both `harbor run` invocations; produces `results/agent-a/` + `results/agent-b/` |
| `scripts/HARBOR_NOTES.md` | Documented harbor CLI behavior discovered during Task 1 (output dir, task filter, `--ak` syntax) |
| `scripts/tb_subset_quick.txt` | 8 Terminal-Bench 2 task IDs (one per line) |
| `scripts/comparison_report.py` | Reads both `summary.json`; produces `diff.json` + `comparison.md`; aborts on secret leak |
| `tests/test_terminal_bench_ab_sh.py` | Hermetic test: mocks harbor binary, asserts invocation shape |
| `tests/test_comparison_report.py` | Golden-file + summary.json reader tests |
| `tests/test_comparison_diff.py` | Edge-case diff tests (all-fail, identical, missing) |
| `tests/test_issue_body_schema.py` | Markdown structure validation |
| `tests/test_no_secret_leak_in_issue.py` | Scans rendered Markdown for token-shaped strings |
| `tests/test_concurrency_group_yaml.py` | Verifies workflow YAML has concurrency + permissions blocks |
| `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/{agent-a,agent-b}/summary.json` + `expected-comparison.md` | Golden fixture: 5/8 pass for A |
| `tests/fixtures/terminal_bench_ab/case-all-fail/{agent-a,agent-b}/summary.json` | Edge: both score 0 |
| `tests/fixtures/terminal_bench_ab/case-identical-results/{agent-a,agent-b}/summary.json` | Edge: Δ is 0 |
| `tests/fixtures/terminal_bench_ab/case-agent-b-missing/{agent-a}/summary.json` | Edge: B did not complete |
| `tests/fixtures/terminal_bench_ab/case-task-id-with-secret/{agent-a,agent-b}/summary.json` | Negative test for secret scan |
| `.github/workflows/terminal-bench-ab.yml` | The GH Action |
| `docs/superpowers/plans/2026-08-11-harbor-terminal-bench-ab.md` | This plan |

**Modified files:**

| File | Change |
|---|---|
| `scripts/ci.sh` | Add `pytest tests/test_terminal_bench_*.py` + `actionlint .github/workflows/terminal-bench-ab.yml` to the CI flow |

---

### Task 1: Discover harbor CLI + bootstrap `tb_subset_quick.txt` + TDD `scripts/terminal_bench_ab.sh`

**Files:**
- Create: `scripts/HARBOR_NOTES.md`
- Create: `scripts/tb_subset_quick.txt`
- Create: `scripts/terminal_bench_ab.sh`
- Create: `tests/test_terminal_bench_ab_sh.py`

**Interfaces:**
- Consumes: `harbor` binary on `PATH`; env vars `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `ANTHROPIC_AUTH_TOKEN`, `HERETEK_PLUGIN_DIR`, `HERETEK_N_CONCURRENT` (default 8).
- Produces: `results/agent-a/{summary.json,per-task.jsonl,harbor-log.txt}` and `results/agent-b/...` (exact shape to be confirmed in Step 1 and recorded in `HARBOR_NOTES.md`).

- [ ] **Step 1: Install harbor and discover its CLI**

Run:
```bash
uv tool install harbor
harbor run --help 2>&1 | tee /tmp/harbor-help.txt
harbor datasets list 2>&1 | tee /tmp/harbor-datasets.txt
```

Inspect `/tmp/harbor-help.txt` and `/tmp/harbor-datasets.txt`. Identify:
1. The flag that controls output directory (likely `-o` or `--output-dir`).
2. The flag that filters tasks in a dataset (likely `--task` repeated, or `--ak config={task_filter:[...]}`).
3. Whether `--ak` accepts nested JSON config that gets translated to the agent's native format.
4. The exact directory shape harbor writes per-task results in.

- [ ] **Step 2: Document findings in `scripts/HARBOR_NOTES.md`**

Create `scripts/HARBOR_NOTES.md` with this content (replace the placeholders with values you discovered in Step 1):

```markdown
# Harbor CLI notes

Discovered via `harbor run --help` and `harbor datasets list` on YYYY-MM-DD.

## Output directory flag

Flag: `<DISCOVERED_FLAG>`

Format: Harbor writes per-trial logs to `<output_dir>/<trial_id>/`. Each trial
directory contains `trial.log`, `verifier_output.txt`, and per-task JSON.

## Task filtering

Flag: `<DISCOVERED_FLAG>`

Syntax: `<DISCOVERED_SYNTAX>` (e.g., `--task tb-001 --task tb-002`).

For v1 we pass the 8 quick-subset IDs from `scripts/tb_subset_quick.txt` as
repeated `--task` arguments.

## `--ak` agent kwargs

`--ak key=value` accepts inline JSON via `key={"json":"value"}`. The JSON is
converted to the agent's native format. For Claude Code we use:

```
--ak 'config={"plugin_dir":"<absolute path>"}'
```

## Dataset version

`terminal-bench@2.0` is the current version per `harbor datasets list`.
```

- [ ] **Step 3: Create `scripts/tb_subset_quick.txt`**

Browse https://tbench.ai/leaderboard and the harbor Terminal-Bench 2 dataset
catalog. Pick 8 task IDs that satisfy the spec criteria: short wall-clock
(<2 min/task at Sonnet-equivalent), representative diversity (terminal ops,
file editing, build system, networking, etc.), deterministic oracle.

Write one task ID per line to `scripts/tb_subset_quick.txt`. Example:

```
tb-001-fix-file-permissions
tb-002-edit-json-config
tb-003-build-c-project
tb-004-network-fetch
tb-005-grep-large-log
tb-006-chmod-recursive
tb-007-rotate-file
tb-008-install-pkg
```

(Replace these placeholders with real Terminal-Bench 2 task IDs from the
dataset catalog. The names above are illustrative; the real IDs follow the
pattern `<dataset-prefix>-<short-slug>`.)

- [ ] **Step 4: Write failing test in `tests/test_terminal_bench_ab_sh.py`**

Create `tests/test_terminal_bench_ab_sh.py`:

```python
"""Hermetic test for scripts/terminal_bench_ab.sh.

Mocks the `harbor` binary via PATH manipulation. Asserts the script invokes
harbor twice (once per agent), with the right agent config (heretek for A,
baseline for B), and the right model.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def fake_harbor_dir(tmp_path: Path) -> Path:
    """Create a fake `harbor` binary that records invocations and exits 0."""
    d = tmp_path / "bin"
    d.mkdir()
    harbor = d / "harbor"
    harbor.write_text(
        "#!/usr/bin/env bash\n"
        'echo "$@" >> "$HARBOR_CALL_LOG"\n'
        "mkdir -p \"$HARBOR_OUTPUT_DIR/trial-1\"\n"
        "echo '{\"trial_id\":\"trial-1\",\"task_id\":\"tb-001\",\"verdict\":\"pass\"}' "
        ">> \"$HARBOR_OUTPUT_DIR/trial-1/result.json\"\n"
        "exit 0\n"
    )
    harbor.chmod(0o755)
    return d


def _run_script(
    fake_harbor_dir: Path,
    tmp_path: Path,
    *,
    extra_env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run terminal_bench_ab.sh with the fake harbor on PATH."""
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "terminal_bench_ab.sh"
    call_log = tmp_path / "harbor-calls.log"
    env = {
        **os.environ,
        "PATH": f"{fake_harbor_dir}:{os.environ['PATH']}",
        "HARBOR_CALL_LOG": str(call_log),
        "RESULTS_DIR": str(tmp_path / "results"),
        "HERETEK_PLUGIN_DIR": str(tmp_path / "plugins"),
        "HERETEK_N_CONCURRENT": "1",
        **extra_env,
    }
    return subprocess.run(
        ["bash", str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_invokes_harbor_twice(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """The script must invoke harbor twice — once for agent A, once for agent B."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    call_log = tmp_path / "harbor-calls.log"
    calls = call_log.read_text().splitlines()
    assert len(calls) == 2, f"expected 2 harbor calls, got {len(calls)}: {calls}"


def test_agent_a_uses_heretek_plugin_dir(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """Agent A's harbor invocation must include the heretek plugin_dir."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    call_log = (tmp_path / "harbor-calls.log").read_text()
    assert "--ak" in call_log, "agent A must pass --ak"
    assert "plugin_dir" in call_log, "agent A --ak must include plugin_dir"
    assert "agent-a" in call_log, "agent A output dir must be agent-a"


def test_agent_b_has_no_plugin_dir(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """Agent B's harbor invocation must NOT include a plugin_dir."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    calls = (tmp_path / "harbor-calls.log").read_text().splitlines()
    # Second call is agent B; it must not include plugin_dir.
    assert "plugin_dir" not in calls[1], (
        f"agent B must not pass plugin_dir; got: {calls[1]}"
    )
    assert "agent-b" in calls[1], "agent B output dir must be agent-b"


def test_uses_model_from_env(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """The script must pass the model from ANTHROPIC_MODEL env var."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "claude-test-1"},
    )
    assert proc.returncode == 0, proc.stderr
    call_log = (tmp_path / "harbor-calls.log").read_text()
    assert "claude-test-1" in call_log


def test_wipes_existing_results_dir(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """Pre-existing results/ must be wiped before harbor runs."""
    stale = tmp_path / "results" / "stale-file.txt"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale")
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    assert not stale.exists(), "stale results must be wiped"
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest tests/test_terminal_bench_ab_sh.py -v`
Expected: FAIL — `scripts/terminal_bench_ab.sh` not found.

- [ ] **Step 6: Implement `scripts/terminal_bench_ab.sh`**

Create `scripts/terminal_bench_ab.sh`:

```bash
#!/usr/bin/env bash
# scripts/terminal_bench_ab.sh — run Harbor Terminal-Bench 2 with two agents:
# Agent A: claude-code + heretek harness (via --plugin-dir).
# Agent B: claude-code baseline (no harness).
#
# Env vars (consumed):
#   ANTHROPIC_MODEL          — required. e.g., "claude-sonnet-5-20260301"
#   ANTHROPIC_BASE_URL       — optional. Passed through to harbor if set.
#   HERETEK_PLUGIN_DIR       — required. Absolute path to plugins/ checkout.
#   HERETEK_N_CONCURRENT     — optional. Default 8.
#   HERETEK_DATASET          — optional. Default "terminal-bench@2.0".
#   RESULTS_DIR              — optional. Default ./results.
#   HERETEK_QUICK_SUBSET     — optional. Path to subset file. Default scripts/tb_subset_quick.txt.
#
# Per-agent results land in:
#   ${RESULTS_DIR}/agent-a/<harbor trial dirs>
#   ${RESULTS_DIR}/agent-b/<harbor trial dirs>
#
# Exit code: 0 if both agents succeed; non-zero if either fails.

set -euo pipefail

ANTHROPIC_MODEL="${ANTHROPIC_MODEL:?ANTHROPIC_MODEL must be set}"
HERETEK_PLUGIN_DIR="${HERETEK_PLUGIN_DIR:?HERETEK_PLUGIN_DIR must be set}"
HERETEK_N_CONCURRENT="${HERETEK_N_CONCURRENT:-8}"
HERETEK_DATASET="${HERETEK_DATASET:-terminal-bench@2.0}"
RESULTS_DIR="${RESULTS_DIR:-./results}"
HERETEK_QUICK_SUBSET="${HERETEK_QUICK_SUBSET:-$(dirname "$0")/tb_subset_quick.txt}"

# Build --task filter from subset file (one ID per line; blank lines ignored).
TASK_ARGS=()
if [ -f "$HERETEK_QUICK_SUBSET" ]; then
  while IFS= read -r task_id; do
    [ -n "$task_id" ] && TASK_ARGS+=(--task "$task_id")
  done < "$HERETEK_QUICK_SUBSET"
fi

# Wipe results dir and recreate per-agent subdirs.
rm -rf "$RESULTS_DIR"
mkdir -p "$RESULTS_DIR/agent-a" "$RESULTS_DIR/agent-b"

# Resolve harbor output subdirs. Harbor writes per-trial logs into the
# output dir we pass. See scripts/HARBOR_NOTES.md for details.
AGENT_A_OUT="${RESULTS_DIR}/agent-a/run"
AGENT_B_OUT="${RESULTS_DIR}/agent-b/run"

echo "[terminal_bench_ab] agent A (with heretek) -> ${AGENT_A_OUT}"
harbor run \
  --dataset "$HERETEK_DATASET" \
  --agent claude-code \
  --model "anthropic/${ANTHROPIC_MODEL}" \
  --n-concurrent "$HERETEK_N_CONCURRENT" \
  --ak "config={\"plugin_dir\":\"${HERETEK_PLUGIN_DIR}\"}" \
  "${TASK_ARGS[@]}" \
  --output-dir "$AGENT_A_OUT"

echo "[terminal_bench_ab] agent B (baseline) -> ${AGENT_B_OUT}"
harbor run \
  --dataset "$HERETEK_DATASET" \
  --agent claude-code \
  --model "anthropic/${ANTHROPIC_MODEL}" \
  --n-concurrent "$HERETEK_N_CONCURRENT" \
  "${TASK_ARGS[@]}" \
  --output-dir "$AGENT_B_OUT"

echo "[terminal_bench_ab] both agents complete"
```

Make the script executable: `chmod +x scripts/terminal_bench_ab.sh`

> **Note:** The flag `--output-dir` is illustrative; the implementer must
> replace it with the actual harbor flag discovered in Step 1 (e.g., `-o`).
> Update the script accordingly.

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_terminal_bench_ab_sh.py -v`
Expected: PASS — 5 tests green.

If failures: re-check that the fake `harbor` binary is being found on PATH,
that `HARBOR_CALL_LOG` is being written, and that the script's harbor
invocations include the documented flags.

- [ ] **Step 8: Commit**

```bash
git add scripts/HARBOR_NOTES.md scripts/tb_subset_quick.txt scripts/terminal_bench_ab.sh tests/test_terminal_bench_ab_sh.py
git commit -m "feat(scripts): terminal_bench_ab.sh runs two harbor agents

Discovered harbor CLI flags via 'harbor run --help'; documented in
scripts/HARBOR_NOTES.md. Picks 8 Terminal-Bench 2 task IDs into
scripts/tb_subset_quick.txt. Test suite mocks the harbor binary and
asserts two invocations (A with --plugin-dir, B without).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Run pre-commit per project `CLAUDE.md`: `pre-commit run --all-files`.

---

### Task 2: TDD `scripts/comparison_report.py` — argument parsing + `summary.json` reader

**Files:**
- Create: `scripts/comparison_report.py`
- Create: `tests/test_comparison_report.py`

**Interfaces:**
- Consumes: `--results-dir`, `--commit-sha`, `--trigger`, `--actor`, `--tier`, `--model`, `--base-url`, `--output` (CLI flags).
- Produces: A `summary.json` dataclass loaded from `<results-dir>/agent-a/summary.json` (and `agent-b/summary.json`). Function signature:

```python
def load_summary(path: Path) -> Summary: ...
```

Where `Summary` is a `@dataclass` with fields matching the spec's `summary.json` schema (lines 180-197 of the spec).

- [ ] **Step 1: Write failing test**

Create `tests/test_comparison_report.py`:

```python
"""Tests for scripts/comparison_report.py — argument parsing and summary.json loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.comparison_report import load_summary, build_arg_parser


def test_build_arg_parser_has_required_flags() -> None:
    parser = build_arg_parser()
    args = parser.parse_args([
        "--results-dir", "./results",
        "--commit-sha", "abc1234",
        "--trigger", "push",
        "--actor", "alice",
        "--tier", "quick",
        "--model", "claude-test",
        "--base-url", "https://example.com",
        "--output", "/tmp/c.md",
    ])
    assert args.results_dir == Path("./results")
    assert args.commit_sha == "abc1234"
    assert args.trigger == "push"
    assert args.actor == "alice"
    assert args.tier == "quick"
    assert args.model == "claude-test"
    assert args.base_url == "https://example.com"
    assert args.output == Path("/tmp/c.md")


def test_load_summary_minimal(tmp_path: Path) -> None:
    payload = {
        "agent": "agent-a-with-heretek",
        "model": "claude-test",
        "commit_sha": "abc1234",
        "heretek_harness": True,
        "n_tasks": 8,
        "passed": 5,
        "failed": 3,
        "pass_rate": 0.625,
        "wall_clock_sec_total": 845,
        "wall_clock_sec_p50": 92,
        "tokens_total": 412345,
        "per_task": [
            {"task_id": "tb-001", "verdict": "pass", "wall_clock_sec": 45, "tokens": 12345},
            {"task_id": "tb-002", "verdict": "fail", "wall_clock_sec": 60, "tokens": 8000},
        ],
    }
    p = tmp_path / "summary.json"
    p.write_text(json.dumps(payload))
    s = load_summary(p)
    assert s.agent == "agent-a-with-heretek"
    assert s.passed == 5
    assert s.failed == 3
    assert s.pass_rate == pytest.approx(0.625)
    assert len(s.per_task) == 2
    assert s.per_task[0].task_id == "tb-001"
    assert s.per_task[0].verdict == "pass"


def test_load_summary_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_summary(tmp_path / "does-not-exist.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_comparison_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.comparison_report'`.

- [ ] **Step 3: Implement minimal `scripts/comparison_report.py`**

Create `scripts/comparison_report.py`:

```python
"""Render a comparison Markdown report from two agent result bundles.

Reads ${results_dir}/agent-a/summary.json and ${results_dir}/agent-b/summary.json,
computes a diff, renders a Markdown comparison, and writes it to --output.

Usage:
    python scripts/comparison_report.py \\
        --results-dir ./results \\
        --commit-sha $GITHUB_SHA \\
        --trigger push \\
        --actor $GITHUB_ACTOR \\
        --tier quick \\
        --model "$ANTHROPIC_MODEL" \\
        --base-url "$ANTHROPIC_BASE_URL" \\
        --output /tmp/comparison.md
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PerTaskResult:
    task_id: str
    verdict: str  # "pass" | "fail"
    wall_clock_sec: int
    tokens: int


@dataclass
class Summary:
    agent: str
    model: str
    commit_sha: str
    heretek_harness: bool
    n_tasks: int
    passed: int
    failed: int
    pass_rate: float
    wall_clock_sec_total: int
    wall_clock_sec_p50: int
    tokens_total: int
    per_task: list[PerTaskResult]


def load_summary(path: Path) -> Summary:
    """Load a summary.json file. Raises FileNotFoundError if missing."""
    if not path.exists():
        raise FileNotFoundError(f"summary not found: {path}")
    payload = json.loads(path.read_text())
    return Summary(
        agent=payload["agent"],
        model=payload["model"],
        commit_sha=payload["commit_sha"],
        heretek_harness=payload["heretek_harness"],
        n_tasks=payload["n_tasks"],
        passed=payload["passed"],
        failed=payload["failed"],
        pass_rate=payload["pass_rate"],
        wall_clock_sec_total=payload["wall_clock_sec_total"],
        wall_clock_sec_p50=payload["wall_clock_sec_p50"],
        tokens_total=payload["tokens_total"],
        per_task=[PerTaskResult(**t) for t in payload["per_task"]],
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="comparison_report")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--trigger", choices=["push", "workflow_dispatch"], required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--tier", choices=["quick", "full", "custom"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


if __name__ == "__main__":
    sys.exit(0)  # v1: just verify imports
```

> **Note:** `from scripts.comparison_report import ...` requires `scripts/` to be a package. Create `scripts/__init__.py` if it doesn't exist (it already does per the repo's existing layout).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_comparison_report.py -v`
Expected: PASS — 3 tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/comparison_report.py tests/test_comparison_report.py scripts/__init__.py 2>/dev/null || true
git commit -m "feat(scripts): comparison_report.py arg parser + summary loader

Dataclass-driven Summary model. Loads summary.json from either agent's
output dir. CLI surface for downstream rendering.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: TDD `comparison_report.py` — diff computation

**Files:**
- Create: `tests/test_comparison_diff.py`
- Modify: `scripts/comparison_report.py`

**Interfaces:**
- Produces: `compute_diff(a: Summary, b: Summary) -> dict` returning the JSON shape from spec lines 200-213.

- [ ] **Step 1: Write failing test**

Create `tests/test_comparison_diff.py`:

```python
"""Tests for the diff computation in scripts/comparison_report.py."""

from __future__ import annotations

from scripts.comparison_report import Summary, PerTaskResult, compute_diff


def _summary(passed_ids: list[str], failed_ids: list[str]) -> Summary:
    per_task = [
        PerTaskResult(task_id=tid, verdict="pass", wall_clock_sec=60, tokens=10000)
        for tid in passed_ids
    ] + [
        PerTaskResult(task_id=tid, verdict="fail", wall_clock_sec=30, tokens=5000)
        for tid in failed_ids
    ]
    n = len(per_task)
    return Summary(
        agent="test",
        model="m",
        commit_sha="abc",
        heretek_harness=True,
        n_tasks=n,
        passed=len(passed_ids),
        failed=len(failed_ids),
        pass_rate=len(passed_ids) / n if n else 0.0,
        wall_clock_sec_total=900,
        wall_clock_sec_p50=60,
        tokens_total=100000,
        per_task=per_task,
    )


def test_diff_identical() -> None:
    a = _summary(["tb-1", "tb-2"], ["tb-3"])
    b = _summary(["tb-1", "tb-2"], ["tb-3"])
    d = compute_diff(a, b)
    assert d["delta_passed"] == 0
    assert d["tasks_agent_a_passed_b_failed"] == []
    assert d["tasks_agent_b_passed_a_failed"] == []
    assert d["tasks_both_passed"] == ["tb-1", "tb-2"]
    assert d["tasks_both_failed"] == ["tb-3"]


def test_diff_a_wins_on_two_tasks() -> None:
    a = _summary(["tb-1", "tb-2", "tb-3"], ["tb-4"])
    b = _summary(["tb-1"], ["tb-2", "tb-3", "tb-4"])
    d = compute_diff(a, b)
    assert d["delta_passed"] == 2
    assert sorted(d["tasks_agent_a_passed_b_failed"]) == ["tb-2", "tb-3"]
    assert d["tasks_agent_b_passed_a_failed"] == []
    assert d["tasks_both_passed"] == ["tb-1"]


def test_diff_b_wins_on_one_task() -> None:
    a = _summary(["tb-1"], ["tb-2", "tb-3"])
    b = _summary(["tb-1", "tb-2"], ["tb-3"])
    d = compute_diff(a, b)
    assert d["delta_passed"] == -1
    assert d["tasks_agent_a_passed_b_failed"] == []
    assert d["tasks_agent_b_passed_a_failed"] == ["tb-2"]


def test_diff_wall_clock_and_tokens() -> None:
    a = _summary(["tb-1"], [])
    b = _summary(["tb-1"], [])
    a.wall_clock_sec_total = 100
    b.wall_clock_sec_total = 150
    a.tokens_total = 1000
    b.tokens_total = 2000
    d = compute_diff(a, b)
    assert d["wall_clock_delta_sec"] == -50
    assert d["tokens_delta"] == -1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_comparison_diff.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_diff'`.

- [ ] **Step 3: Add `compute_diff` to `scripts/comparison_report.py`**

Append to `scripts/comparison_report.py`:

```python
def compute_diff(a: Summary, b: Summary) -> dict:
    """Compute the comparison diff between two agent summaries.

    Returns a dict matching the spec's diff.json schema (spec §4).
    Positive deltas mean agent A (heretek) did better.
    """
    a_pass = {t.task_id for t in a.per_task if t.verdict == "pass"}
    b_pass = {t.task_id for t in b.per_task if t.verdict == "pass"}
    return {
        "commit_sha": a.commit_sha,
        "delta_pass_rate": a.pass_rate - b.pass_rate,
        "delta_passed": a.passed - b.passed,
        "tasks_agent_a_passed_b_failed": sorted(a_pass - b_pass),
        "tasks_agent_b_passed_a_failed": sorted(b_pass - a_pass),
        "tasks_both_passed": sorted(a_pass & b_pass),
        "tasks_both_failed": sorted(
            {t.task_id for t in a.per_task}
            - a_pass
            - (b_pass - a_pass)
        ),
        "wall_clock_delta_sec": a.wall_clock_sec_total - b.wall_clock_sec_total,
        "tokens_delta": a.tokens_total - b.tokens_total,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_comparison_diff.py -v`
Expected: PASS — 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/comparison_report.py tests/test_comparison_diff.py
git commit -m "feat(scripts): compute_diff for agent comparison

Set algebra over per-task pass/fail sets. Positive deltas favor agent A
(with heretek). Wall-clock + tokens deltas computed from totals.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: TDD `comparison_report.py` — Markdown rendering

**Files:**
- Modify: `scripts/comparison_report.py`
- Modify: `tests/test_comparison_report.py`

**Interfaces:**
- Produces: `render_markdown(a: Summary, b: Summary, diff: dict, meta: dict) -> str` — returns the Markdown body matching the spec's issue template (spec §5 lines 251-285).
- `meta` is a dict with keys: `commit_sha_short`, `trigger`, `actor`, `tier`, `model`, `base_url`.

- [ ] **Step 1: Add failing tests to `tests/test_comparison_report.py`**

Append to `tests/test_comparison_report.py`:

```python
from scripts.comparison_report import render_markdown, compute_diff  # noqa: E402


def _meta() -> dict:
    return {
        "commit_sha_short": "abc1234",
        "trigger": "push",
        "actor": "alice",
        "tier": "quick",
        "model": "claude-test",
        "base_url": "https://example.com",
    }


def test_render_markdown_has_required_headings() -> None:
    a = _summary(["tb-1", "tb-2", "tb-3", "tb-4", "tb-5"], ["tb-6", "tb-7", "tb-8"])
    b = _summary(["tb-1", "tb-2", "tb-3", "tb-4"], ["tb-5", "tb-6", "tb-7", "tb-8"])
    diff = compute_diff(a, b)
    md = render_markdown(a, b, diff, _meta())
    for heading in [
        "# Terminal-Bench A/B — `abc1234`",
        "**Trigger:** `push`",
        "**Actor:** alice",
        "## Headline",
        "## Per-task",
        "## Tasks where heretek helped",
        "## Tasks where heretek hurt",
    ]:
        assert heading in md, f"missing heading: {heading}"


def test_render_markdown_delta_row_present() -> None:
    a = _summary(["tb-1", "tb-2"], ["tb-3"])
    b = _summary(["tb-1"], ["tb-2", "tb-3"])
    diff = compute_diff(a, b)
    md = render_markdown(a, b, diff, _meta())
    assert "| **Δ** |" in md


def test_render_markdown_lists_helped_tasks() -> None:
    a = _summary(["tb-1", "tb-2"], ["tb-3"])
    b = _summary(["tb-1"], ["tb-2", "tb-3"])
    diff = compute_diff(a, b)
    md = render_markdown(a, b, diff, _meta())
    assert "`tb-2`" in md
    assert "heretek helped" in md.lower()


def test_render_markdown_no_help_section_when_empty() -> None:
    a = _summary(["tb-1"], ["tb-2"])
    b = _summary(["tb-1"], ["tb-2"])
    diff = compute_diff(a, b)
    md = render_markdown(a, b, diff, _meta())
    # When nothing was helped, the bullet should be "(none)".
    assert "(none)" in md
```

> **Note:** `_summary` is defined in `tests/test_comparison_diff.py`. To avoid duplicating it, extract it into a small `tests/_factories.py` helper module. Or copy-paste it here — the writing-plans skill says "repeat the code" rather than "similar to Task N."

Copy-paste the `_summary` helper from `tests/test_comparison_diff.py` into this test file too (rename to avoid collision, e.g. `_make_summary`).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_comparison_report.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_markdown'`.

- [ ] **Step 3: Implement `render_markdown`**

Append to `scripts/comparison_report.py`:

```python
def render_markdown(
    a: Summary,
    b: Summary,
    diff: dict,
    meta: dict,
) -> str:
    """Render the comparison Markdown body for the GitHub issue."""
    lines: list[str] = []
    lines.append(f"# Terminal-Bench A/B — `{meta['commit_sha_short']}`")
    lines.append("")
    lines.append(f"**Trigger:** `{meta['trigger']}`")
    lines.append(f"**Actor:** {meta['actor']}")
    n = a.n_tasks
    lines.append(
        f"**Tier:** `{meta['tier']}` ({n} task{'s' if n != 1 else ''})"
    )
    lines.append(f"**Model:** `{meta['model']}` (via `{meta['base_url']}`)")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("| Agent | Pass rate | Passed | Failed | Wall-clock | Tokens |")
    lines.append("|---|---|---|---|---|---|")
    pct = lambda x: f"{x * 100:.1f}%"  # noqa: E731
    lines.append(
        f"| **A — with heretek** | {pct(a.pass_rate)} | {a.passed}/{a.n_tasks} "
        f"| {a.failed}/{a.n_tasks} | {a.wall_clock_sec_total}s | {a.tokens_total:,} |"
    )
    lines.append(
        f"| **B — baseline** | {pct(b.pass_rate)} | {b.passed}/{b.n_tasks} "
        f"| {b.failed}/{b.n_tasks} | {b.wall_clock_sec_total}s | {b.tokens_total:,} |"
    )
    sign_pct = f"+{pct(diff['delta_pass_rate'])}" if diff["delta_pass_rate"] >= 0 else pct(diff["delta_pass_rate"])
    sign_passed = f"+{diff['delta_passed']}" if diff["delta_passed"] >= 0 else str(diff["delta_passed"])
    sign_wall = f"+{diff['wall_clock_delta_sec']}s" if diff["wall_clock_delta_sec"] >= 0 else f"{diff['wall_clock_delta_sec']}s"
    sign_tokens = f"+{diff['tokens_delta']:,}" if diff["tokens_delta"] >= 0 else f"{diff['tokens_delta']:,}"
    lines.append(
        f"| **Δ** | **{sign_pct}** | **{sign_passed}** | — | **{sign_wall}** | **{sign_tokens}** |"
    )
    lines.append("")
    lines.append("## Per-task")
    lines.append("")
    lines.append("| Task | A | B | Notes |")
    lines.append("|---|---|---|---|")
    a_by_id = {t.task_id: t for t in a.per_task}
    b_by_id = {t.task_id: t for t in b.per_task}
    all_ids = sorted(set(a_by_id) | set(b_by_id))
    for tid in all_ids:
        a_str = (
            f"✓ ({a_by_id[tid].wall_clock_sec}s)"
            if a_by_id.get(tid) and a_by_id[tid].verdict == "pass"
            else f"✗ ({a_by_id[tid].wall_clock_sec}s)"
            if a_by_id.get(tid)
            else "—"
        )
        b_str = (
            f"✓ ({b_by_id[tid].wall_clock_sec}s)"
            if b_by_id.get(tid) and b_by_id[tid].verdict == "pass"
            else f"✗ ({b_by_id[tid].wall_clock_sec}s)"
            if b_by_id.get(tid)
            else "—"
        )
        a_pass = a_by_id.get(tid) and a_by_id[tid].verdict == "pass"
        b_pass = b_by_id.get(tid) and b_by_id[tid].verdict == "pass"
        if a_pass and b_pass:
            note = "both"
        elif a_pass and not b_pass:
            note = "A wins"
        elif b_pass and not a_pass:
            note = "B wins"
        else:
            note = "both fail"
        lines.append(f"| {tid} | {a_str} | {b_str} | {note} |")
    lines.append("")
    helped = diff["tasks_agent_a_passed_b_failed"]
    hurt = diff["tasks_agent_b_passed_a_failed"]
    lines.append("## Tasks where heretek helped")
    lines.append("")
    if helped:
        for tid in helped:
            lines.append(f"- `{tid}` (A pass, B fail)")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Tasks where heretek hurt")
    lines.append("")
    if hurt:
        for tid in hurt:
            lines.append(f"- `{tid}` (A fail, B pass)")
    else:
        lines.append("(none)")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_comparison_report.py tests/test_comparison_diff.py -v`
Expected: PASS — all green.

- [ ] **Step 5: Commit**

```bash
git add scripts/comparison_report.py tests/test_comparison_report.py
git commit -m "feat(scripts): render Markdown comparison report

Renders the full issue body: headline table, per-task table, helped/hurt
sections. Pure function — no I/O — making it trivial to test.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Golden fixture + golden test (`case-quick-8-pass-5`)

**Files:**
- Create: `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/agent-a/summary.json`
- Create: `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/agent-a/per-task.jsonl`
- Create: `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/agent-b/summary.json`
- Create: `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/agent-b/per-task.jsonl`
- Create: `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/expected-comparison.md`
- Modify: `tests/test_comparison_report.py`

**Interfaces:**
- Consumes: A `tmp_path` populated with the fixture directory.
- Produces: A regression test that runs `render_markdown(...)` on the fixture's two `summary.json` files and asserts the output matches `expected-comparison.md` byte-for-byte.

- [ ] **Step 1: Create the fixture files**

Create `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/agent-a/summary.json`:

```json
{
  "agent": "agent-a-with-heretek",
  "model": "claude-test",
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
    {"task_id": "tb-001-fix-permissions", "verdict": "pass", "wall_clock_sec": 45, "tokens": 12345},
    {"task_id": "tb-002-edit-json", "verdict": "pass", "wall_clock_sec": 60, "tokens": 15000},
    {"task_id": "tb-003-build-c", "verdict": "fail", "wall_clock_sec": 180, "tokens": 30000},
    {"task_id": "tb-005-network-fetch", "verdict": "pass", "wall_clock_sec": 120, "tokens": 22000},
    {"task_id": "tb-006-chmod", "verdict": "pass", "wall_clock_sec": 30, "tokens": 8000},
    {"task_id": "tb-007-rotate", "verdict": "fail", "wall_clock_sec": 90, "tokens": 18000},
    {"task_id": "tb-008-install", "verdict": "pass", "wall_clock_sec": 200, "tokens": 40000},
    {"task_id": "tb-004-build-system", "verdict": "fail", "wall_clock_sec": 120, "tokens": 25000}
  ]
}
```

Create `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/agent-b/summary.json`:

```json
{
  "agent": "agent-b-baseline",
  "model": "claude-test",
  "commit_sha": "abc1234",
  "heretek_harness": false,
  "n_tasks": 8,
  "passed": 4,
  "failed": 4,
  "pass_rate": 0.5,
  "wall_clock_sec_total": 887,
  "wall_clock_sec_p50": 95,
  "tokens_total": 425645,
  "per_task": [
    {"task_id": "tb-001-fix-permissions", "verdict": "pass", "wall_clock_sec": 52, "tokens": 13000},
    {"task_id": "tb-002-edit-json", "verdict": "pass", "wall_clock_sec": 65, "tokens": 16000},
    {"task_id": "tb-003-build-c", "verdict": "fail", "wall_clock_sec": 175, "tokens": 29000},
    {"task_id": "tb-005-network-fetch", "verdict": "fail", "wall_clock_sec": 60, "tokens": 18000},
    {"task_id": "tb-006-chmod", "verdict": "pass", "wall_clock_sec": 35, "tokens": 8500},
    {"task_id": "tb-007-rotate", "verdict": "fail", "wall_clock_sec": 95, "tokens": 19000},
    {"task_id": "tb-008-install", "verdict": "fail", "wall_clock_sec": 195, "tokens": 39000},
    {"task_id": "tb-004-build-system", "verdict": "fail", "wall_clock_sec": 175, "tokens": 28000}
  ]
}
```

For `per-task.jsonl` files: one JSON object per line, mirroring `per_task[]` from `summary.json`. (These are required by the spec but not exercised by `comparison_report.py` — they're for downstream tooling that consumes harbor output directly. Create them now for fixture completeness.)

Create `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/agent-a/per-task.jsonl` with eight lines, one per `per_task` entry, format `{"task_id": "...", "verdict": "...", "wall_clock_sec": N, "tokens": N}`.

Create `tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/agent-b/per-task.jsonl` similarly.

- [ ] **Step 2: Generate `expected-comparison.md` by running the script against the fixture**

The implementer runs this once to materialize the expected output:

```bash
mkdir -p /tmp/fixture-run
cp -r tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/* /tmp/fixture-run/

python scripts/comparison_report.py \
  --results-dir /tmp/fixture-run \
  --commit-sha abc1234 \
  --trigger push \
  --actor test-runner \
  --tier quick \
  --model claude-test \
  --base-url http://localhost \
  --output tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/expected-comparison.md

cat tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/expected-comparison.md
```

Inspect the output. Verify it includes the expected headline (`+12.5%`), per-task table, helped/hurt sections.

- [ ] **Step 3: Add the golden test to `tests/test_comparison_report.py`**

Append to `tests/test_comparison_report.py`:

```python
def test_golden_case_quick_8_pass_5() -> None:
    """Regression test: rendering the case-quick-8-pass-5 fixture matches expected."""
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "terminal_bench_ab"
        / "case-quick-8-pass-5"
    )
    a = load_summary(fixture_root / "agent-a" / "summary.json")
    b = load_summary(fixture_root / "agent-b" / "summary.json")
    diff = compute_diff(a, b)
    md = render_markdown(a, b, diff, {
        "commit_sha_short": "abc1234",
        "trigger": "push",
        "actor": "test-runner",
        "tier": "quick",
        "model": "claude-test",
        "base_url": "http://localhost",
    })
    expected = (fixture_root / "expected-comparison.md").read_text()
    assert md == expected, f"golden mismatch; got:\n{md}\nexpected:\n{expected}"
```

- [ ] **Step 4: Run the golden test**

Run: `pytest tests/test_comparison_report.py::test_golden_case_quick_8_pass_5 -v`
Expected: PASS.

If FAIL: compare the rendered Markdown against the expected file with `diff` and fix the render logic (do not edit the expected file unless the new render is clearly correct).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/terminal_bench_ab/case-quick-8-pass-5/ tests/test_comparison_report.py
git commit -m "test: golden fixture case-quick-8-pass-5 + regression test

Frozen comparison.md for a known-good A/B pair. Locks the rendering
contract against accidental format drift.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Edge case fixtures + tests

**Files:**
- Create: `tests/fixtures/terminal_bench_ab/case-all-fail/agent-a/summary.json`
- Create: `tests/fixtures/terminal_bench_ab/case-all-fail/agent-b/summary.json`
- Create: `tests/fixtures/terminal_bench_ab/case-identical-results/agent-a/summary.json`
- Create: `tests/fixtures/terminal_bench_ab/case-identical-results/agent-b/summary.json`
- Create: `tests/fixtures/terminal_bench_ab/case-agent-b-missing/agent-a/summary.json`
- Modify: `tests/test_comparison_diff.py`

- [ ] **Step 1: Create `case-all-fail` fixtures**

Create `tests/fixtures/terminal_bench_ab/case-all-fail/agent-a/summary.json`:

```json
{
  "agent": "agent-a-with-heretek",
  "model": "claude-test",
  "commit_sha": "deadbeef",
  "heretek_harness": true,
  "n_tasks": 4,
  "passed": 0,
  "failed": 4,
  "pass_rate": 0.0,
  "wall_clock_sec_total": 600,
  "wall_clock_sec_p50": 150,
  "tokens_total": 80000,
  "per_task": [
    {"task_id": "tb-A", "verdict": "fail", "wall_clock_sec": 150, "tokens": 20000},
    {"task_id": "tb-B", "verdict": "fail", "wall_clock_sec": 150, "tokens": 20000},
    {"task_id": "tb-C", "verdict": "fail", "wall_clock_sec": 150, "tokens": 20000},
    {"task_id": "tb-D", "verdict": "fail", "wall_clock_sec": 150, "tokens": 20000}
  ]
}
```

Create `tests/fixtures/terminal_bench_ab/case-all-fail/agent-b/summary.json` with the same structure (all fail).

- [ ] **Step 2: Create `case-identical-results` fixtures**

Create `tests/fixtures/terminal_bench_ab/case-identical-results/agent-a/summary.json`:

```json
{
  "agent": "agent-a-with-heretek",
  "model": "claude-test",
  "commit_sha": "1234567",
  "heretek_harness": true,
  "n_tasks": 3,
  "passed": 2,
  "failed": 1,
  "pass_rate": 0.6667,
  "wall_clock_sec_total": 300,
  "wall_clock_sec_p50": 100,
  "tokens_total": 60000,
  "per_task": [
    {"task_id": "tb-X", "verdict": "pass", "wall_clock_sec": 100, "tokens": 20000},
    {"task_id": "tb-Y", "verdict": "pass", "wall_clock_sec": 100, "tokens": 20000},
    {"task_id": "tb-Z", "verdict": "fail", "wall_clock_sec": 100, "tokens": 20000}
  ]
}
```

Create `tests/fixtures/terminal_bench_ab/case-identical-results/agent-b/summary.json` with identical content.

- [ ] **Step 3: Create `case-agent-b-missing` fixture (only agent-a present)**

Create `tests/fixtures/terminal_bench_ab/case-agent-b-missing/agent-a/summary.json`:

```json
{
  "agent": "agent-a-with-heretek",
  "model": "claude-test",
  "commit_sha": "feedface",
  "heretek_harness": true,
  "n_tasks": 4,
  "passed": 3,
  "failed": 1,
  "pass_rate": 0.75,
  "wall_clock_sec_total": 400,
  "wall_clock_sec_p50": 100,
  "tokens_total": 80000,
  "per_task": [
    {"task_id": "tb-P", "verdict": "pass", "wall_clock_sec": 100, "tokens": 20000},
    {"task_id": "tb-Q", "verdict": "pass", "wall_clock_sec": 100, "tokens": 20000},
    {"task_id": "tb-R", "verdict": "pass", "wall_clock_sec": 100, "tokens": 20000},
    {"task_id": "tb-S", "verdict": "fail", "wall_clock_sec": 100, "tokens": 20000}
  ]
}
```

Do NOT create `agent-b/summary.json` for this case.

- [ ] **Step 4: Add edge case tests to `tests/test_comparison_diff.py`**

Append to `tests/test_comparison_diff.py`:

```python
from scripts.comparison_report import load_summary  # noqa: E402


def _fixture_root(name: str) -> Path:
    return (
        Path(__file__).resolve().parent
        / "fixtures"
        / "terminal_bench_ab"
        / name
    )


def test_all_fail_renders_with_zero_delta() -> None:
    a = load_summary(_fixture_root("case-all-fail") / "agent-a" / "summary.json")
    b = load_summary(_fixture_root("case-all-fail") / "agent-b" / "summary.json")
    d = compute_diff(a, b)
    assert d["delta_pass_rate"] == 0.0
    assert d["delta_passed"] == 0
    assert d["tasks_both_passed"] == []
    assert sorted(d["tasks_both_failed"]) == ["tb-A", "tb-B", "tb-C", "tb-D"]


def test_identical_results_yield_zero_deltas() -> None:
    a = load_summary(
        _fixture_root("case-identical-results") / "agent-a" / "summary.json"
    )
    b = load_summary(
        _fixture_root("case-identical-results") / "agent-b" / "summary.json"
    )
    d = compute_diff(a, b)
    assert d["delta_pass_rate"] == 0.0
    assert d["delta_passed"] == 0
    assert d["tasks_agent_a_passed_b_failed"] == []
    assert d["tasks_agent_b_passed_a_failed"] == []
    assert d["wall_clock_delta_sec"] == 0
    assert d["tokens_delta"] == 0


def test_missing_agent_b_raises_file_not_found() -> None:
    """If agent-b/summary.json is missing, load_summary must raise."""
    with pytest.raises(FileNotFoundError):
        load_summary(
            _fixture_root("case-agent-b-missing") / "agent-b" / "summary.json"
        )
```

Add `import pytest` and `from pathlib import Path` imports at the top of `tests/test_comparison_diff.py` if not already present.

- [ ] **Step 5: Run edge case tests**

Run: `pytest tests/test_comparison_diff.py -v`
Expected: PASS — all 4 (the original 4 + 3 new = 7) tests green.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/terminal_bench_ab/case-all-fail/ tests/fixtures/terminal_bench_ab/case-identical-results/ tests/fixtures/terminal_bench_ab/case-agent-b-missing/ tests/test_comparison_diff.py
git commit -m "test: edge case fixtures (all-fail, identical, missing)

Lock down the diff semantics for the three edge cases the spec
explicitly calls out.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: TDD secret leak detection (`case-task-id-with-secret`)

**Files:**
- Create: `tests/fixtures/terminal_bench_ab/case-task-id-with-secret/agent-a/summary.json`
- Create: `tests/fixtures/terminal_bench_ab/case-task-id-with-secret/agent-b/summary.json`
- Create: `tests/test_no_secret_leak_in_issue.py`
- Modify: `scripts/comparison_report.py`

**Interfaces:**
- Produces: `scan_for_secrets(markdown: str) -> list[str]` — returns list of detected token-shaped strings (empty if clean).
- `render_markdown` (or a wrapper) aborts if the rendered Markdown contains tokens.

- [ ] **Step 1: Create the secret-leak fixture**

Create `tests/fixtures/terminal_bench_ab/case-task-id-with-secret/agent-a/summary.json` with a task_id field containing a token-shaped string. The fixture uses a deliberately low-entropy placeholder (`aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`) so the regex-based `scan_for_secrets` test fires but `gitleaks`' entropy heuristic does not flag the committed fixture:

```json
{
  "agent": "agent-a-with-heretek",
  "model": "claude-test",
  "commit_sha": "0000000",
  "heretek_harness": true,
  "n_tasks": 1,
  "passed": 1,
  "failed": 0,
  "pass_rate": 1.0,
  "wall_clock_sec_total": 60,
  "wall_clock_sec_p50": 60,
  "tokens_total": 10000,
  "per_task": [
    {"task_id": "tb-leak-sk-cp-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "verdict": "pass", "wall_clock_sec": 60, "tokens": 10000}
  ]
}
```

Create `tests/fixtures/terminal_bench_ab/case-task-id-with-secret/agent-b/summary.json` (mirror, same token-shaped task_id).

- [ ] **Step 2: Write failing test**

Create `tests/test_no_secret_leak_in_issue.py`:

```python
"""Verify that rendered comparison Markdown does not leak tokens.

This is the safety net: if a future change causes a token-shaped string
to appear in the issue body, this test fails before the issue is opened.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.comparison_report import (
    load_summary,
    compute_diff,
    render_markdown,
    scan_for_secrets,
)


def test_scan_for_secrets_detects_sk_cp() -> None:
    # Low-entropy placeholder (matches our regex, skips gitleaks entropy heuristic).
    md = "Anthropic API key: sk-cp-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    hits = scan_for_secrets(md)
    assert any("sk-cp-" in h for h in hits), f"expected sk-cp hit, got {hits}"


def test_scan_for_secrets_detects_ghp() -> None:
    # Low-entropy placeholder (matches our regex, skips gitleaks entropy heuristic).
    md = "GitHub PAT: ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    hits = scan_for_secrets(md)
    assert any("ghp_" in h for h in hits), f"expected ghp_ hit, got {hits}"


def test_scan_for_secrets_clean_text() -> None:
    md = "All tests passed. Pass rate: 62.5%."
    hits = scan_for_secrets(md)
    assert hits == []


def test_render_with_secret_aborts() -> None:
    """A fixture that contains a token in a task_id must abort the render."""
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "terminal_bench_ab"
        / "case-task-id-with-secret"
    )
    a = load_summary(fixture_root / "agent-a" / "summary.json")
    b = load_summary(fixture_root / "agent-b" / "summary.json")
    diff = compute_diff(a, b)
    md = render_markdown(a, b, diff, {
        "commit_sha_short": "0000000",
        "trigger": "push",
        "actor": "test",
        "tier": "quick",
        "model": "m",
        "base_url": "u",
    })
    with pytest.raises(RuntimeError, match="secret"):
        # Wrap render+scan in a function the implementer will add.
        from scripts.comparison_report import render_with_secret_check
        render_with_secret_check(md)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_no_secret_leak_in_issue.py -v`
Expected: FAIL — `ImportError: cannot import name 'scan_for_secrets'`.

- [ ] **Step 4: Implement `scan_for_secrets` + `render_with_secret_check` in `scripts/comparison_report.py`**

Append to `scripts/comparison_report.py`:

```python
import re

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),         # sk-... (Anthropic-style)
    re.compile(r"sk-cp-[A-Za-z0-9_-]{20,}"),     # sk-cp-... (MiniMax-style)
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),         # GitHub PAT
    re.compile(r"gho_[A-Za-z0-9]{20,}"),         # GitHub OAuth
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),  # Slack
)


def scan_for_secrets(markdown: str) -> list[str]:
    """Return list of token-shaped strings found in `markdown`."""
    hits: list[str] = []
    for pattern in _SECRET_PATTERNS:
        hits.extend(pattern.findall(markdown))
    return hits


def render_with_secret_check(markdown: str) -> str:
    """Raise RuntimeError if `markdown` contains token-shaped strings.

    Called by the main() flow after render_markdown. The wrapper passes
    Markdown through unchanged; the only behavior is the abort.
    """
    hits = scan_for_secrets(markdown)
    if hits:
        redacted = [h[:6] + "..." + h[-4:] for h in hits]
        raise RuntimeError(
            f"refusing to write issue body — {len(hits)} secret-shaped "
            f"string(s) detected: {redacted}"
        )
    return markdown
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_no_secret_leak_in_issue.py -v`
Expected: PASS — 4 tests green.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/terminal_bench_ab/case-task-id-with-secret/ tests/test_no_secret_leak_in_issue.py scripts/comparison_report.py
git commit -m "feat(scripts): secret leak scan + render guard

Detects sk-*, sk-cp-*, ghp_*, gho_*, xox*- tokens in rendered Markdown.
The render_with_secret_check wrapper aborts if any are found. Negative
fixture (case-task-id-with-secret) locks the behavior.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: TDD workflow YAML + concurrency/permissions validation

**Files:**
- Create: `.github/workflows/terminal-bench-ab.yml`
- Create: `tests/test_concurrency_group_yaml.py`
- Create: `tests/test_issue_body_schema.py`

**Interfaces:**
- Produces: A YAML loader test that asserts the workflow file has `concurrency.group`, `concurrency.cancel-in-progress`, and `permissions.{contents,issues,actions}` blocks.
- Produces: An issue body schema test that asserts the rendered Markdown contains all required headings.

- [ ] **Step 1: Write failing tests**

Create `tests/test_concurrency_group_yaml.py`:

```python
"""Verify the GH Action workflow has required concurrency + permissions blocks."""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "workflows"
    / "terminal-bench-ab.yml"
)


def test_workflow_file_exists() -> None:
    assert WORKFLOW_PATH.exists(), f"missing {WORKFLOW_PATH}"


def test_workflow_has_concurrency_group() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert "concurrency" in workflow[True] or "concurrency" in workflow.get(True, {}), (
        "workflow must have top-level concurrency block"
    )
    # YAML's `on` key parses as boolean True; handle both.
    concurrency = (
        workflow[True].get("concurrency")
        if "concurrency" in workflow[True]
        else workflow.get("concurrency")
    )
    assert concurrency["group"] == "terminal-bench-ab"
    assert concurrency["cancel-in-progress"] is True


def test_workflow_has_required_permissions() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text())
    on_key = True if True in workflow else "on"
    perms = workflow[on_key].get("permissions", {})
    assert perms.get("contents") == "read"
    assert perms.get("issues") == "write"
    assert perms.get("actions") == "write", (
        "actions: write required for actions/upload-artifact@v4"
    )


def test_workflow_triggers_on_push_to_main() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text())
    on_key = True if True in workflow else "on"
    triggers = workflow[on_key]
    push = triggers.get("push")
    assert push is not None
    assert "main" in push["branches"]


def test_workflow_supports_workflow_dispatch() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text())
    on_key = True if True in workflow else "on"
    triggers = workflow[on_key]
    assert "workflow_dispatch" in triggers
```

Add `pyyaml` to dev requirements if not already present: `uv pip install pyyaml --dev` or add to `pyproject.toml`'s `[project.optional-dependencies]`. Check existing pattern in `requirements-dev.txt`.

Create `tests/test_issue_body_schema.py`:

```python
"""Verify the rendered Markdown has all required issue body sections."""

from __future__ import annotations

from pathlib import Path

from scripts.comparison_report import (
    load_summary,
    compute_diff,
    render_markdown,
)


def _load(name: str):
    root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "terminal_bench_ab"
        / name
    )
    a = load_summary(root / "agent-a" / "summary.json")
    b = load_summary(root / "agent-b" / "summary.json")
    return a, b


def test_issue_body_has_all_required_sections() -> None:
    a, b = _load("case-quick-8-pass-5")
    md = render_markdown(a, b, compute_diff(a, b), {
        "commit_sha_short": "abc1234",
        "trigger": "push",
        "actor": "alice",
        "tier": "quick",
        "model": "claude-test",
        "base_url": "http://localhost",
    })
    required = [
        "# Terminal-Bench A/B",
        "**Trigger:**",
        "**Actor:**",
        "**Tier:**",
        "**Model:**",
        "## Headline",
        "## Per-task",
        "## Tasks where heretek helped",
        "## Tasks where heretek hurt",
    ]
    for section in required:
        assert section in md, f"missing section: {section}"


def test_issue_body_no_template_placeholders() -> None:
    a, b = _load("case-quick-8-pass-5")
    md = render_markdown(a, b, compute_diff(a, b), {
        "commit_sha_short": "abc1234",
        "trigger": "push",
        "actor": "alice",
        "tier": "quick",
        "model": "claude-test",
        "base_url": "http://localhost",
    })
    for placeholder in ["<!--TEMPLATE-->", "{{", "}}", "TODO", "FIXME"]:
        assert placeholder not in md, f"placeholder {placeholder!r} leaked into body"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_concurrency_group_yaml.py tests/test_issue_body_schema.py -v`
Expected: FAIL — workflow file not found.

- [ ] **Step 3: Create `.github/workflows/terminal-bench-ab.yml`**

```yaml
name: Terminal-Bench A/B

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      n_tasks:
        description: "Number of Terminal-Bench tasks (default 8, full = all)"
        default: "8"
      n_concurrent:
        description: "Per-agent concurrency"
        default: "8"

concurrency:
  group: terminal-bench-ab
  cancel-in-progress: true

permissions:
  contents: read
  issues: write
  actions: write

jobs:
  terminal-bench-ab:
    runs-on: ubuntu-latest
    timeout-minutes: 360
    env:
      HERETEK_PLUGIN_DIR: ${{ github.workspace }}/plugins
      HERETEK_N_CONCURRENT: ${{ github.event.inputs.n_concurrent || '8' }}
      RESULTS_DIR: ${{ github.workspace }}/results

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install uv
        run: pip install uv

      - name: Install Harbor
        run: uv tool install harbor

      - name: Docker info (fail-fast if missing)
        run: docker info

      - name: Run Terminal-Bench A/B
        env:
          ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
          ANTHROPIC_MODEL: ${{ secrets.ANTHROPIC_MODEL }}
          ANTHROPIC_AUTH_TOKEN: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
        run: bash scripts/terminal_bench_ab.sh

      - name: Render comparison
        env:
          ANTHROPIC_MODEL: ${{ secrets.ANTHROPIC_MODEL }}
          ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
        run: |
          python scripts/comparison_report.py \
            --results-dir "$RESULTS_DIR" \
            --commit-sha "$GITHUB_SHA" \
            --trigger push \
            --actor "$GITHUB_ACTOR" \
            --tier quick \
            --model "$ANTHROPIC_MODEL" \
            --base-url "$ANTHROPIC_BASE_URL" \
            --output /tmp/comparison.md

      - name: Upload results artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: terminal-bench-ab-results
          path: results/
          retention-days: 30

      - name: Open comparison issue
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          if [ ! -f /tmp/comparison.md ]; then
            echo "::error::comparison.md not generated; skipping issue creation"
            exit 0
          fi
          gh issue create \
            --repo "$GITHUB_REPOSITORY" \
            --label terminal-bench-ab \
            --label automated \
            --title "Terminal-Bench A/B: $(echo $GITHUB_SHA | cut -c1-7) — $(date -u +%Y-%m-%d)" \
            --body-file /tmp/comparison.md
        # Continue on error: a failed issue creation logs to step summary,
        # but the run is still useful for debugging.
        continue-on-error: true
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_concurrency_group_yaml.py tests/test_issue_body_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Lint the workflow with actionlint**

Install actionlint if not present: `brew install actionlint` (or equivalent).

Run: `actionlint .github/workflows/terminal-bench-ab.yml`
Expected: exit 0, no errors.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/terminal-bench-ab.yml tests/test_concurrency_group_yaml.py tests/test_issue_body_schema.py
git commit -m "feat(workflow): terminal-bench-ab.yml + schema tests

Push-to-main + workflow_dispatch trigger. concurrency group, required
permissions, harbor install, dual agent run, comparison render, issue
creation. Schema tests verify the rendered body has all required
sections.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Extend `scripts/ci.sh` to include the new tests + actionlint

**Files:**
- Modify: `scripts/ci.sh`

**Interfaces:**
- Consumes: existing `scripts/ci.sh` content.
- Produces: Extended CI that runs `pytest tests/test_terminal_bench_*.py` + `actionlint .github/workflows/terminal-bench-ab.yml` in addition to existing tests.

- [ ] **Step 1: Read current `scripts/ci.sh`**

Run: `cat scripts/ci.sh`
Note the existing structure (pytest → validate → generate → diff → smoke).

- [ ] **Step 2: Add new test invocations**

Edit `scripts/ci.sh`. After the existing `pytest -q` line, add:

```bash
# Terminal-Bench A/B tests (Task 9)
if [ -d tests/test_terminal_bench_*.py ]; then
  pytest -q tests/test_terminal_bench_*.py tests/test_no_secret_leak_in_issue.py tests/test_issue_body_schema.py tests/test_concurrency_group_yaml.py
fi
```

Wait — pytest discovery doesn't glob in `-q`. Use:

```bash
pytest -q tests/test_terminal_bench_ab_sh.py \
          tests/test_comparison_report.py \
          tests/test_comparison_diff.py \
          tests/test_no_secret_leak_in_issue.py \
          tests/test_issue_body_schema.py \
          tests/test_concurrency_group_yaml.py
```

Add this block after the existing `pytest -q` invocation.

After the existing `bash tests/smoke/fast_gate_smoke.sh` block, add:

```bash
# Lint the new GH Action workflow
if command -v actionlint >/dev/null 2>&1; then
  actionlint .github/workflows/terminal-bench-ab.yml
else
  echo "ci: actionlint not installed; skipping workflow lint (install: brew install actionlint)"
fi
```

- [ ] **Step 3: Run the updated `scripts/ci.sh`**

Run: `bash scripts/ci.sh`
Expected: All steps green; new tests pass; workflow lints.

- [ ] **Step 4: Commit**

```bash
git add scripts/ci.sh
git commit -m "ci: include Terminal-Bench A/B tests + actionlint

Extends scripts/ci.sh with the new test files and workflow lint.
actionlint is optional (skip with a notice if not installed).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: End-to-end smoke on dev machine (Phase 5)

**Files:**
- Modify: none (verification step)

**Interfaces:**
- Verifies: the entire pipeline runs locally with a mocked harbor (since real harbor requires Docker + API access).

- [ ] **Step 1: Run the script with the fake harbor from Task 1's test fixture**

Extract the fake harbor binary into a reusable location:

```bash
mkdir -p /tmp/fake-harbor
cat > /tmp/fake-harbor/harbor <<'EOF'
#!/usr/bin/env bash
echo "$@" >> "$HARBOR_CALL_LOG"
mkdir -p "$HARBOR_OUTPUT_DIR/trial-1"
echo '{"trial_id":"trial-1","task_id":"tb-001","verdict":"pass"}' \
  > "$HARBOR_OUTPUT_DIR/trial-1/result.json"
exit 0
EOF
chmod +x /tmp/fake-harbor/harbor
```

Run the script:

```bash
mkdir -p /tmp/smoke/plugins
mkdir -p /tmp/smoke/results
cp -r plugins/* /tmp/smoke/plugins/ 2>/dev/null || true

PATH="/tmp/fake-harbor:$PATH" \
HARBOR_CALL_LOG=/tmp/smoke/harbor-calls.log \
HERETEK_PLUGIN_DIR=/tmp/smoke/plugins \
HERETEK_N_CONCURRENT=1 \
ANTHROPIC_MODEL=test-model \
bash scripts/terminal_bench_ab.sh
```

Expected: exits 0; `/tmp/smoke/results/agent-a/run/trial-1/result.json` and `/tmp/smoke/results/agent-b/run/trial-1/result.json` exist; `/tmp/smoke/harbor-calls.log` has 2 lines.

- [ ] **Step 2: Run `comparison_report.py` against the smoke output**

(Note: the smoke output won't have a real `summary.json` — this step verifies the script's CLI surface and error handling. Create a stub `summary.json` first.)

```bash
cat > /tmp/smoke/results/agent-a/summary.json <<'EOF'
{
  "agent": "agent-a-with-heretek",
  "model": "test-model",
  "commit_sha": "smoke000",
  "heretek_harness": true,
  "n_tasks": 1,
  "passed": 1,
  "failed": 0,
  "pass_rate": 1.0,
  "wall_clock_sec_total": 60,
  "wall_clock_sec_p50": 60,
  "tokens_total": 10000,
  "per_task": [{"task_id": "tb-001", "verdict": "pass", "wall_clock_sec": 60, "tokens": 10000}]
}
EOF
cp /tmp/smoke/results/agent-a/summary.json /tmp/smoke/results/agent-b/summary.json
sed -i 's/agent-a-with-heretek/agent-b-baseline/g; s/true/false/g' /tmp/smoke/results/agent-b/summary.json

python scripts/comparison_report.py \
  --results-dir /tmp/smoke/results \
  --commit-sha smoke000 \
  --trigger push \
  --actor local-smoke \
  --tier quick \
  --model test-model \
  --base-url http://localhost \
  --output /tmp/smoke/comparison.md

cat /tmp/smoke/comparison.md
```

Expected: exits 0; `/tmp/smoke/comparison.md` is a valid Markdown body with all required sections; both agents show 1/1 pass rate; Δ row is `+0.0%`, `+0`.

- [ ] **Step 3: Document the smoke run in `scripts/HARBOR_NOTES.md`**

Append to `scripts/HARBOR_NOTES.md`:

```markdown
## Smoke run (Phase 5 verification)

Performed on YYYY-MM-DD with a mocked harbor binary. The fake harbor
writes a single `result.json` per agent and exits 0. End-to-end flow
verified:

- `scripts/terminal_bench_ab.sh` invokes harbor twice with the right flags.
- `scripts/comparison_report.py` reads both summary.json files, renders a
  Markdown body with all required sections.

A live run on `main` will follow once repo secrets are configured.
```

- [ ] **Step 4: Commit the notes update**

```bash
git add scripts/HARBOR_NOTES.md
git commit -m "docs(scripts): record Phase 5 smoke run findings

Verified end-to-end with a mocked harbor. Live main-branch run is
gated on repo secrets being configured by a maintainer.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review (against the spec)

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| §1 Summary (push to main + workflow_dispatch, two agents, GH issue) | Tasks 1, 8 (workflow), 5 (issue body) |
| §2 Background and pivot | n/a (narrative, no implementation) |
| §3 Architecture (file layout, env, trigger, per-agent invocation) | Tasks 1, 8 |
| §4 Task selection + scoring + output schema | Tasks 1 (subset file), 2 (summary reader), 3 (diff), 4 (render) |
| §5 Data flow + issue tracking | Tasks 1 (terminal_bench_ab.sh), 4 (render Markdown), 5 (issue body), 8 (workflow + gh issue create) |
| §6 Error handling | Tasks 1 (wipe results dir), 6 (missing agent-b), 7 (secret scan), 8 (concurrency cancel-in-progress) |
| §7 Testing | Tasks 1, 2, 3, 4, 5, 6, 7, 8, 9 (all tests) |
| §8 Phases | Tasks 1=Phase 1, 2+3+4+5+6+7=Phase 2-3, 8=Phase 4, 9=Phase 4 (ci.sh), 10=Phase 5 |
| §9 References | n/a |
| §10 Deferred | n/a (deferred work, not in this plan) |

**Placeholder scan:** No "TBD", "TODO", "implement later" in any task. The phrase "the implementer must" appears in HARBOR_NOTES.md guidance but is a discovery prompt, not a placeholder for missing logic.

**Type consistency:** `Summary` and `PerTaskResult` dataclasses defined in Task 2; consumed in Tasks 3, 4, 5, 6, 7. `compute_diff`, `render_markdown`, `scan_for_secrets`, `render_with_secret_check` defined where introduced, consumed in later tests. No drift.

**Coverage gaps in spec vs plan:**
- Spec mentions `scripts/ci.sh` extension with `actionlint` — covered in Task 9.
- Spec mentions artifact upload (30-day retention) — covered in Task 8 workflow YAML.
- Spec mentions fallback to `$GITHUB_STEP_SUMMARY` — partially covered (Task 8 has `continue-on-error: true` on the `gh issue create` step but doesn't write to step summary on failure). Acceptable for v1; document as follow-up if it becomes important.

**Note on `pytest` discovery:** `tests/test_terminal_bench_*.py` is a glob used in narrative but `pytest` itself doesn't glob this way. Tasks that add new test files use explicit paths.

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-08-11-harbor-terminal-bench-ab.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
