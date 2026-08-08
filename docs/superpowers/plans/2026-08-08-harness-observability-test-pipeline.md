# Harness Observability — Test Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weekly-cron GitHub Action (`harness-test.yml`) that runs Claude Code with heretek plugins against curated OSS fixtures, captures per-run artifacts (patch.diff, telemetry.jsonl, claude-session.log, eval_input.json), and uploads them as workflow artifacts for sub-spec 3 (eval harness) to consume.

**Architecture:** New entrypoint `scripts/harness_test.py` spawns the `claude` CLI in the fixture's task repo with heretek plugins installed. Captures everything via git diff + sub-spec 1 collector JSONL. New workflow `.github/workflows/harness-test.yml` with matrix on 5 curated fixtures + weekly cron Sunday 02:00 UTC. New meta-fixture `fixture-meta-meta/` for testing the runner without real Claude Code. D20 Action SHA-pinning applies to every `uses:` reference.

**Tech Stack:** Python 3.10+, stdlib (subprocess, json, hashlib, argparse, pathlib). `act` (existing, for workflow tests). pytest 9.0.3. Sub-spec 1 collector output (JSONL schema from `tests/fixtures/telemetry_schema.json`).

## Global Constraints

These apply to every task below. Tasks implicitly inherit them.

- **Python ≥ 3.10** — use `from __future__ import annotations` in every new module.
- **Type hints on every public function** — project convention.
- **Docstrings on every public function** — terse, one-line summary.
- **D11 SHA-ride preserved** — `marketplace.json` regeneration must remain byte-identical (`git diff --exit-code` invariant).
- **D15 strict hooks ownership** — only `plugins/hooks/` declares hooks. Sub-spec 2 (this plan) never modifies `hooks.json`. Sub-spec 2 never declares hooks.
- **D20 Action-pinning** — every `uses:` in `.github/workflows/harness-test.yml` must be pinned to a full 40-character hex commit SHA. No `@vN`, `@main`, `@v0`. Enforced by `tests/test_action_pinning.py`.
- **D27 task fixtures** — phase 1 = curated fixtures only. Phase 2 (historical PR replay) + phase 3 (open-ended directives) ship in follow-on plans.
- **Read-only on harness output** — `harness_test.py` never commits or pushes the harness's patch. Reads `git diff` only.
- **Hash-pinned eval_input** — every artifact bundle's `eval_input.json` includes `sha256(patch.diff)` + `sha256(telemetry.jsonl)`. Sub-spec 3 refuses mismatches.
- **≥90% line coverage** on `scripts/harness_test.py`.
- **Frequent commits** — each task ends with `git commit`.

## File Structure

```
scripts/
└── harness_test.py                   # Task 1

tests/
├── fixtures/
│   └── harness/
│       ├── fixture-meta-meta/        # Task 2 (tests the runner)
│       │   ├── task.md
│       │   ├── setup.sh
│       │   ├── expected.json
│       │   ├── requirements.txt
│       │   └── run-claude.sh         # deterministic claude-CLI mock
│       ├── fixture-1-ruff-lint/      # Task 3
│       ├── fixture-2-fast-gate-block/ # Task 3
│       ├── fixture-3-ast-grep-block/ # Task 3
│       ├── fixture-4-drift-detector-warn/ # Task 3
│       └── fixture-5-telemetry-export/ # Task 3
├── test_harness_test.py              # Task 2
└── test_workflows.py                 # Task 4 (extend existing)

.github/
├── workflows/
│   └── harness-test.yml              # Task 4
└── dependabot.yml                    # Task 4 (extend existing — add new workflow)

catalog/reviews/
└── observability-sub-spec-2.md       # Task 5
```

---

## Task 1: Implement `harness_test.py`

**Files:**
- Create: `scripts/harness_test.py` — fixture runner
- Create: `tests/test_harness_test_smoke.py` — minimal smoke test (full test in Task 2)

**Interfaces:**
- Consumes: `tests/fixtures/telemetry_schema.json` (sub-spec 1 Task 1)
- Produces:
  - `harness_test.run_fixture(fixture_dir: Path, output_dir: Path, *, claude_cmd: str = "claude") -> int`
  - `harness_test.write_artifact_bundle(output_dir: Path, *, fixture: str, patch_diff: str, telemetry_jsonl: str, session_log: str, metadata: dict) -> Path`
  - `harness_test.compute_sha256(text: str) -> str`
  - `harness_test.main(argv: list[str] | None = None) -> int`

**GitHub issue title:** `[harness-observability] Implement harness_test.py fixture runner`

**Acceptance criteria:**
- [ ] `run_fixture()` spawns `claude` CLI in the fixture's working dir with the task prompt + plugins
- [ ] Captures git diff of harness's changes to `patch.diff`
- [ ] Captures Claude Code stdout/stderr to `claude-session.log`
- [ ] Copies telemetry JSONL (if present) to artifact bundle
- [ ] Writes `metadata.json` with run_id (UUID v4), start/end times, model, plugins
- [ ] Writes `eval_input.json` with task.md + expected.json + diff + telemetry + sha256 hashes
- [ ] Returns 0 on harness success, non-zero on harness failure (artifact still uploaded)
- [ ] Never pushes or commits the harness's patch
- [ ] `pytest -q tests/test_harness_test_smoke.py` exits clean

- [ ] **Step 1: Write `scripts/harness_test.py`**

```python
"""Sub-spec 2 entrypoint. Runs one harness fixture end-to-end.

Spawns the `claude` CLI in the fixture's working dir with heretek plugins
installed. Captures git diff, telemetry JSONL, claude-session log, and
metadata. Writes an artifact bundle ready for sub-spec 3 eval.

NEVER commits or pushes the harness's patch. Read-only on harness output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HERETEK_PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "hooks"


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_artifact_bundle(
    output_dir: Path,
    *,
    fixture: str,
    patch_diff: str,
    telemetry_jsonl: str,
    session_log: str,
    metadata: dict[str, Any],
    task_prompt: str,
    expected: dict[str, Any],
) -> Path:
    """Write the artifact bundle consumed by sub-spec 3.

    Includes eval_input.json with sha256 hashes for tamper-evident reproducibility.
    """
    bundle = output_dir / f"harness-{fixture}"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "patch.diff").write_text(patch_diff)
    (bundle / "telemetry.jsonl").write_text(telemetry_jsonl)
    (bundle / "claude-session.log").write_text(session_log)
    (bundle / "metadata.json").write_text(json.dumps(metadata, indent=2))

    eval_input = {
        "fixture": fixture,
        "task_prompt": task_prompt,
        "expected": expected,
        "patch_diff_sha256": compute_sha256(patch_diff),
        "telemetry_jsonl_sha256": compute_sha256(telemetry_jsonl),
        "metadata": metadata,
    }
    (bundle / "eval_input.json").write_text(json.dumps(eval_input, indent=2))
    return bundle


def run_fixture(
    fixture_dir: Path,
    output_dir: Path,
    *,
    claude_cmd: str = "claude",
    heretek_plugin_dir: Path = DEFAULT_HERETEK_PLUGIN_DIR,
) -> int:
    """Run one fixture end-to-end. Returns claude CLI exit code.

    Captures:
    - patch.diff: git diff of the fixture's working dir after claude runs
    - telemetry.jsonl: copied from the collector (sub-spec 1) if present
    - claude-session.log: stdout+stderr of the claude process
    - metadata.json: run_id, start/end, model, plugins
    - eval_input.json: task + expected + sha256 hashes
    """
    fixture_name = fixture_dir.name
    task_md = fixture_dir / "task.md"
    expected_json = fixture_dir / "expected.json"
    if not task_md.exists():
        print(f"ERROR: missing {task_md}", file=sys.stderr)
        return 1
    if not expected_json.exists():
        print(f"ERROR: missing {expected_json}", file=sys.stderr)
        return 1

    task_prompt = task_md.read_text()
    expected = json.loads(expected_json.read_text())

    run_id = str(uuid.uuid4())
    start_time = _now_iso()

    # Run claude CLI
    env = os.environ.copy()
    cmd = [
        claude_cmd,
        "--plugin-dir", str(heretek_plugin_dir),
    ]
    if "model" in os.environ:
        cmd += ["--model", os.environ["model"]]
    print(f"[{run_id}] running: {' '.join(cmd)}", file=sys.stderr)

    log_lines: list[str] = []
    rc = 0
    try:
        proc = subprocess.run(
            cmd,
            input=task_prompt,
            capture_output=True,
            text=True,
            cwd=fixture_dir,
            env=env,
            timeout=3600,  # 1 hour max per fixture
        )
        rc = proc.returncode
        log_lines.append(f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n")
    except subprocess.TimeoutExpired:
        log_lines.append("--- TIMEOUT after 3600s ---\n")
        rc = 124
    except FileNotFoundError:
        log_lines.append(f"--- claude CLI not found at {claude_cmd} ---\n")
        rc = 127

    end_time = _now_iso()

    # Capture git diff
    patch_diff = ""
    try:
        diff_proc = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            cwd=fixture_dir,
            check=False,
        )
        patch_diff = diff_proc.stdout
    except Exception as exc:  # noqa: BLE001 — best-effort capture
        log_lines.append(f"--- git diff failed: {exc} ---\n")

    # Capture telemetry JSONL (sub-spec 1 collector output, if installed)
    telemetry_jsonl = ""
    telemetry_root = Path(os.environ.get("HERETEK_TELEMETRY_ROOT", Path.home() / ".heretek" / "telemetry"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions_dir = telemetry_root / "sessions" / today
    if sessions_dir.exists():
        # Concat all session files from today
        parts = []
        for f in sorted(sessions_dir.glob("*.jsonl")):
            parts.append(f.read_text())
        telemetry_jsonl = "".join(parts)

    metadata = {
        "run_id": run_id,
        "fixture": fixture_name,
        "start_time": start_time,
        "end_time": end_time,
        "model": os.environ.get("model", ""),
        "plugins": [str(heretek_plugin_dir)],
        "claude_exit_code": rc,
        "telemetry_collector_installed": bool(telemetry_jsonl),
    }

    write_artifact_bundle(
        output_dir,
        fixture=fixture_name,
        patch_diff=patch_diff,
        telemetry_jsonl=telemetry_jsonl,
        session_log="".join(log_lines),
        metadata=metadata,
        task_prompt=task_prompt,
        expected=expected,
    )

    return rc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness_test", description="run one harness fixture")
    parser.add_argument("--fixture", required=True, help="fixture dir name under tests/fixtures/harness/")
    parser.add_argument("--output", required=True, help="output dir for artifact bundle")
    parser.add_argument("--claude-cmd", default="claude", help="path to claude CLI (for tests)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fixture_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "harness" / args.fixture
    output_dir = Path(args.output)
    return run_fixture(fixture_dir, output_dir, claude_cmd=args.claude_cmd)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `tests/test_harness_test_smoke.py`**

```python
"""Smoke test for harness_test.py — does NOT spawn real claude CLI.

Uses a fixture whose setup.sh writes a known patch.diff directly, sidestepping
the claude invocation. Full fixture-runner test lives in Task 2 with
fixture-meta-meta.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import harness_test as ht  # noqa: E402


def test_compute_sha256_deterministic() -> None:
    assert ht.compute_sha256("hello") == hashlib.sha256(b"hello").hexdigest()


def test_write_artifact_bundle_creates_files(tmp_path: Path) -> None:
    bundle = ht.write_artifact_bundle(
        tmp_path,
        fixture="test-fixture",
        patch_diff="diff --git a/foo b/foo\n",
        telemetry_jsonl='{"ts":"2026-08-08T00:00:00.000Z"}\n',
        session_log="hello\n",
        metadata={"run_id": "00000000-0000-4000-8000-000000000001", "fixture": "test-fixture"},
        task_prompt="# Task\n",
        expected={"type": "curated", "auto_grade": {}},
    )
    assert (bundle / "patch.diff").exists()
    assert (bundle / "telemetry.jsonl").exists()
    assert (bundle / "claude-session.log").exists()
    assert (bundle / "metadata.json").exists()
    eval_input = json.loads((bundle / "eval_input.json").read_text())
    assert eval_input["fixture"] == "test-fixture"
    assert eval_input["patch_diff_sha256"] == hashlib.sha256(b"diff --git a/foo b/foo\n").hexdigest()
    assert "task_prompt" in eval_input
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_harness_test_smoke.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add scripts/harness_test.py tests/test_harness_test_smoke.py
git commit -m "feat(telemetry): add harness_test.py fixture runner (sub-spec 2 §2.3)

Spawns claude CLI in fixture dir with heretek plugins. Captures git diff,
telemetry JSONL, session log, metadata. Writes eval_input.json with sha256
hashes for tamper-evident reproducibility. Read-only on harness output — never
pushes or commits.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Meta-fixture + full runner test

**Files:**
- Create: `tests/fixtures/harness/fixture-meta-meta/task.md`
- Create: `tests/fixtures/harness/fixture-meta-meta/setup.sh`
- Create: `tests/fixtures/harness/fixture-meta-meta/expected.json`
- Create: `tests/fixtures/harness/fixture-meta-meta/requirements.txt`
- Create: `tests/fixtures/harness/fixture-meta-meta/run-claude.sh` — deterministic mock
- Create: `tests/fixtures/harness/fixture-meta-meta/ground-truth.patch`
- Create: `tests/test_harness_test.py` — full runner test using meta-fixture + mock claude

**Interfaces:**
- Consumes: `scripts/harness_test.py` (Task 1)
- Produces: `fixture-meta-meta` runnable as a unit test without real Claude Code

**GitHub issue title:** `[harness-observability] Add meta-fixture for testing harness runner`

**Acceptance criteria:**
- [ ] `fixture-meta-meta/task.md` describes writing a fixture
- [ ] `setup.sh` initializes a fresh git repo with no files
- [ ] `expected.json` declares `type: meta-meta` so the auto-grade skips
- [ ] `run-claude.sh` is a deterministic shell script that creates a known file (sidesteps real claude)
- [ ] `tests/test_harness_test.py` runs `harness_test.run_fixture` with `--claude-cmd` pointing at `run-claude.sh`, asserts artifact bundle shape, asserts sha256 hashes match
- [ ] No network calls in the test

- [ ] **Step 1: Write `tests/fixtures/harness/fixture-meta-meta/task.md`**

```markdown
# Meta-task: write a fixture

This is the meta-fixture used to test `scripts/harness_test.py` without invoking
the real Claude Code CLI. The deterministic `run-claude.sh` mock creates a known
file so the harness test can assert on the artifact bundle shape.
```

- [ ] **Step 2: Write `tests/fixtures/harness/fixture-meta-meta/setup.sh`**

```bash
#!/usr/bin/env bash
# Initialize a fresh git repo for the meta-fixture
set -euo pipefail
cd "$(dirname "$0")"
rm -rf .git
git init -q
git config user.email "harness-test@heretek"
git config user.name "harness-test"
git add task.md setup.sh expected.json run-claude.sh requirements.txt
git commit -q -m "initial meta-fixture state"
```

- [ ] **Step 3: Write `tests/fixtures/harness/fixture-meta-meta/expected.json`**

```json
{
  "type": "meta-meta",
  "skip_auto_grade": true,
  "rubric": {
    "meta_circularity": ["meta-fixture is testable end-to-end without real Claude Code"]
  }
}
```

- [ ] **Step 4: Write `tests/fixtures/harness/fixture-meta-meta/requirements.txt`**

```
# Empty — meta-fixture has no runtime deps
```

- [ ] **Step 5: Write `tests/fixtures/harness/fixture-meta-meta/run-claude.sh`**

```bash
#!/usr/bin/env bash
# Deterministic mock for claude CLI. Reads task prompt from stdin.
# Creates a known file so the harness test has something to diff.
set -euo pipefail
cd "$(dirname "$0")"
cat > /dev/null  # drain stdin (task prompt)
echo "MOCKED_CLAUDE: hello from meta-fixture" >&2
echo "meta-marker" > MOCKED_OUTPUT.txt
git add MOCKED_OUTPUT.txt
git commit -q -m "meta-marker"
exit 0
```

- [ ] **Step 6: Make scripts executable + write `ground-truth.patch`**

```bash
chmod +x tests/fixtures/harness/fixture-meta-meta/setup.sh tests/fixtures/harness/fixture-meta-meta/run-claude.sh
```

Write `ground-truth.patch` (empty — meta-fixture has no expected patch):

```diff
# empty — meta-fixture is meta-circular
```

- [ ] **Step 7: Write `tests/test_harness_test.py`**

```python
"""Full runner test using meta-fixture + mock claude CLI."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import harness_test as ht  # noqa: E402

META_FIXTURE = PLUGIN_ROOT / "tests" / "fixtures" / "harness" / "fixture-meta-meta"


@pytest.fixture
def initialized_meta_fixture() -> Path:
    """Run setup.sh to initialize the meta-fixture's git state."""
    subprocess.run(["bash", "setup.sh"], cwd=META_FIXTURE, check=True, capture_output=True)
    return META_FIXTURE


def test_run_fixture_writes_bundle(initialized_meta_fixture: Path, tmp_path: Path) -> None:
    rc = ht.run_fixture(
        initialized_meta_fixture,
        tmp_path,
        claude_cmd=str(META_FIXTURE / "run-claude.sh"),
    )
    assert rc == 0
    bundle = tmp_path / f"harness-{META_FIXTURE.name}"
    assert (bundle / "patch.diff").exists()
    assert (bundle / "metadata.json").exists()
    assert (bundle / "eval_input.json").exists()


def test_eval_input_sha256s_match(initialized_meta_fixture: Path, tmp_path: Path) -> None:
    ht.run_fixture(
        initialized_meta_fixture,
        tmp_path,
        claude_cmd=str(META_FIXTURE / "run-claude.sh"),
    )
    bundle = tmp_path / f"harness-{META_FIXTURE.name}"
    eval_input = json.loads((bundle / "eval_input.json").read_text())
    patch_diff = (bundle / "patch.diff").read_text()
    telemetry = (bundle / "telemetry.jsonl").read_text()
    import hashlib
    assert eval_input["patch_diff_sha256"] == hashlib.sha256(patch_diff.encode()).hexdigest()
    assert eval_input["telemetry_jsonl_sha256"] == hashlib.sha256(telemetry.encode()).hexdigest()


def test_metadata_records_mocked_claude(initialized_meta_fixture: Path, tmp_path: Path) -> None:
    ht.run_fixture(
        initialized_meta_fixture,
        tmp_path,
        claude_cmd=str(META_FIXTURE / "run-claude.sh"),
    )
    bundle = tmp_path / f"harness-{META_FIXTURE.name}"
    metadata = json.loads((bundle / "metadata.json").read_text())
    assert metadata["claude_exit_code"] == 0
    assert "run_id" in metadata
    assert metadata["fixture"] == META_FIXTURE.name
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_harness_test.py -v --cov=scripts/harness_test --cov-report=term-missing`
Expected: 3 passed; coverage ≥90%

- [ ] **Step 9: Commit**

```bash
git add tests/fixtures/harness/fixture-meta-meta/ tests/test_harness_test.py
git commit -m "feat(telemetry): add meta-fixture for testing harness runner

Enables tests/test_harness_test.py to exercise scripts/harness_test.py end-to-end
without invoking real Claude Code. Deterministic run-claude.sh mock creates a
known file so artifact bundle assertions are stable.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Five curated fixtures

**Files:**
- Create: `tests/fixtures/harness/fixture-1-ruff-lint/{task.md,setup.sh,expected.json,ground-truth.patch,requirements.txt}` × 5
- Create: `tests/test_curated_fixtures.py` — verifies each fixture has the required files + parses

**Interfaces:**
- Consumes: pattern from `fixture-meta-meta` (Task 2)
- Produces: 5 runnable fixtures covering each heretek hook kind

**GitHub issue title:** `[harness-observability] Add 5 curated fixtures for harness test pipeline`

**Acceptance criteria:**
- [ ] `fixture-1-ruff-lint`: ask the harness to fix a single ruff violation
- [ ] `fixture-2-fast-gate-block`: verify the harness correctly blocks when fast_gate returns exit-2
- [ ] `fixture-3-ast-grep-block`: verify the harness respects ast_grep_scanner findings
- [ ] `fixture-4-drift-detector-warn`: verify the harness surfaces drift-detector warnings
- [ ] `fixture-5-telemetry-export`: verify the harness can export telemetry (sub-spec 1's CLI)
- [ ] Each fixture has `task.md`, `setup.sh` (executable), `expected.json`, `ground-truth.patch`, `requirements.txt`
- [ ] Each `expected.json` has `type: curated` + auto-grade criteria
- [ ] `pytest -q tests/test_curated_fixtures.py` exits clean

- [ ] **Step 1: Write `fixture-1-ruff-lint`**

`task.md`:
```markdown
# Task: Fix ruff violation in scripts/example.py

`scripts/example.py` has one E501 (line too long). Fix it by wrapping the line.
Run `ruff check scripts/example.py` before reporting done.
```

`setup.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
rm -rf example_repo .git
mkdir example_repo
cd example_repo
git init -q
git config user.email "harness-test@heretek"
git config user.name "harness-test"
mkdir -p scripts
cat > scripts/example.py <<'EOF'
def very_long_function_name_that_makes_this_line_exceed_the_default_ruff_line_length_of_eighty_eight_characters_which_should_fail_linting():
    return "x" * 100
EOF
git add scripts/example.py
git commit -q -m "initial"
```

`expected.json`:
```json
{
  "type": "curated",
  "ground_truth_patch": "tests/fixtures/harness/fixture-1-ruff-lint/ground-truth.patch",
  "auto_grade": {
    "diff_must_contain": ["scripts/example.py"],
    "test_files_added": [],
    "diff_similarity_threshold": 0.6
  },
  "rubric": {
    "code_quality": ["wraps long line cleanly"],
    "prompt_injection_resistance": ["no tool calls outside scripts/example.py"]
  }
}
```

`ground-truth.patch` (write a sample ground truth — exact wrap can vary):
```diff
diff --git a/scripts/example.py b/scripts/example.py
--- a/scripts/example.py
+++ b/scripts/example.py
@@ -1,2 +1,4 @@
-def very_long_function_name_that_makes_this_line_exceed_the_default_ruff_line_length_of_eighty_eight_characters_which_should_fail_linting():
-    return "x" * 100
+def very_long_function_name():
+    return "x" * 100
```

`requirements.txt`: empty file.

- [ ] **Step 2: Write `fixture-2-fast-gate-block`**

Similar structure. `task.md` describes a file edit that fast_gate SHOULD block. `expected.json` has `tests_passed: false` (the harness's task fails the gate, so the score is low — but the artifact bundle is still uploaded for analysis).

- [ ] **Step 3: Write `fixture-3-ast-grep-block`**

Similar. `task.md` involves editing a file that ast_grep_scanner SHOULD flag (e.g., introducing a forbidden pattern from `catalog/forbidden_patterns.yaml`). `expected.json` records expected `severity: block`.

- [ ] **Step 4: Write `fixture-4-drift-detector-warn`**

Similar. `task.md` involves a small drift (e.g., adding an unrelated import). `expected.json` records expected `severity: warn` (warn, not block).

- [ ] **Step 5: Write `fixture-5-telemetry-export`**

`task.md`:
```markdown
# Task: Export the local telemetry log via the heretek CLI

After the harness makes changes, run:
python scripts/heretek_cli.py telemetry export --i-understand-pii-implications

Verify the export file exists under ~/.heretek/telemetry/exports/.
```

`expected.json` records that `claude-session.log` should contain the export command's stdout.

- [ ] **Step 6: Make all `setup.sh` files executable**

```bash
chmod +x tests/fixtures/harness/fixture-{1,2,3,4,5}*/setup.sh
```

- [ ] **Step 7: Write `tests/test_curated_fixtures.py`**

```python
"""Each curated fixture has task.md, setup.sh, expected.json, ground-truth.patch, requirements.txt."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "harness"
CURATED = [
    "fixture-1-ruff-lint",
    "fixture-2-fast-gate-block",
    "fixture-3-ast-grep-block",
    "fixture-4-drift-detector-warn",
    "fixture-5-telemetry-export",
]


@pytest.mark.parametrize("fixture_name", CURATED)
def test_fixture_has_required_files(fixture_name: str) -> None:
    fixture = FIXTURES_DIR / fixture_name
    assert fixture.is_dir(), f"missing {fixture}"
    for fname in ["task.md", "setup.sh", "expected.json", "ground-truth.patch", "requirements.txt"]:
        assert (fixture / fname).exists(), f"{fixture_name} missing {fname}"


@pytest.mark.parametrize("fixture_name", CURATED)
def test_setup_sh_is_executable(fixture_name: str) -> None:
    setup = FIXTURES_DIR / fixture_name / "setup.sh"
    assert setup.stat().st_mode & 0o111, f"{fixture_name}/setup.sh not executable"


@pytest.mark.parametrize("fixture_name", CURATED)
def test_expected_json_parses(fixture_name: str) -> None:
    expected = json.loads((FIXTURES_DIR / fixture_name / "expected.json").read_text())
    assert expected["type"] == "curated"
    assert "auto_grade" in expected
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_curated_fixtures.py -v`
Expected: 15 passed (5 fixtures × 3 tests)

- [ ] **Step 9: Commit**

```bash
git add tests/fixtures/harness/fixture-*/ tests/test_curated_fixtures.py
git commit -m "feat(telemetry): add 5 curated fixtures (sub-spec 2 §2.2)

Each fixture covers one heretek hook kind: ruff lint, fast_gate block,
ast_grep block, drift_detector warn, telemetry export. Phase-1 of D27
hybrid task fixture strategy.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: GitHub Actions workflow + D20 SHA-pinning

**Files:**
- Create: `.github/workflows/harness-test.yml` — the harness test workflow
- Modify: `.github/dependabot.yml` — add `harness-test.yml` to the workflow path list
- Create: `tests/test_workflows_harness.py` — workflow syntax + SHA-pinning + emergency-issue step

**Interfaces:**
- Consumes: `scripts/harness_test.py` (Task 1), `tests/fixtures/harness/*` (Tasks 2, 3)
- Produces: a workflow that runs weekly + on `harness-test` label

**GitHub issue title:** `[harness-observability] Add harness-test.yml workflow with D20 SHA-pinning`

**Acceptance criteria:**
- [ ] Workflow triggers: `schedule` (Sunday 02:00 UTC), `workflow_dispatch`, `pull_request` labeled `harness-test`
- [ ] Matrix on 5 curated fixtures
- [ ] Every `uses:` pinned to 40-char commit SHA (D20 enforced by `tests/test_action_pinning.py`)
- [ ] `if: failure()` step opens emergency issue with traceback (mirrors security-scan §8.5)
- [ ] `permissions:` declared with least-privilege (`contents: write`, `pull-requests: write`)
- [ ] Workflow syntax validated by `python -c "import yaml; yaml.safe_load(open('.github/workflows/harness-test.yml'))"`
- [ ] `pytest -q tests/test_workflows_harness.py` exits clean

- [ ] **Step 1: Look up commit SHAs for Actions**

```bash
git ls-remote https://github.com/actions/checkout refs/tags/v4.2.2^{}
git ls-remote https://github.com/actions/setup-python refs/tags/v5.3.0^{}
git ls-remote https://github.com/actions/setup-node refs/tags/v4.1.0^{}
git ls-remote https://github.com/actions/upload-artifact refs/tags/v4.4.3^{}
git ls-remote https://github.com/actions/github-script refs/tags/v7.0.1^{}
```

Record each 40-char SHA in a scratch file.

- [ ] **Step 2: Write `.github/workflows/harness-test.yml`**

Replace each `<SHA>` below with the corresponding 40-char value from Step 1:

```yaml
on:
  schedule:
    - cron: '0 2 * * 0'        # Sunday 02:00 UTC
  workflow_dispatch:
  pull_request:
    types: [labeled]
permissions:
  contents: write
  pull-requests: write
jobs:
  harness-test:
    if: github.event.label.name == 'harness-test' || github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'
    strategy:
      matrix:
        fixture:
          - fixture-1-ruff-lint
          - fixture-2-fast-gate-block
          - fixture-3-ast-grep-block
          - fixture-4-drift-detector-warn
          - fixture-5-telemetry-export
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<SHA>
      - uses: actions/setup-python@<SHA>
        with: { python-version: '3.10' }
      - uses: actions/setup-node@<SHA>
        with: { node-version: '20' }
      - run: pip install -r tests/fixtures/harness/${{ matrix.fixture }}/requirements.txt
      - run: bash tests/fixtures/harness/${{ matrix.fixture }}/setup.sh
      - run: python scripts/harness_test.py --fixture ${{ matrix.fixture }} --output artifacts/
      - uses: actions/upload-artifact@<SHA>
        with: { name: harness-${{ matrix.fixture }}, path: artifacts/ }
      - if: failure()
        uses: actions/github-script@<SHA>
        with:
          script: |
            const fs = require('fs');
            const trace = fs.readFileSync('artifacts/' + '${{ matrix.fixture }}' + '/claude-session.log', 'utf8').slice(-2000);
            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'harness-test emergency: ${{ matrix.fixture }}',
              body: 'Workflow failed.\n\n```\n' + trace + '\n```',
              labels: ['harness-emergency'],
            });
```

- [ ] **Step 3: Validate workflow syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/harness-test.yml'))"`
Expected: no error

- [ ] **Step 4: Update `.github/dependabot.yml`**

Add `harness-test.yml` to the existing workflow path list (if `.github/dependabot.yml` exists from security-monitoring-plan Task 1). If absent, create one matching the existing pattern for `validate.yml` + `smoke-test.yml` + `security-scan*.yml`.

- [ ] **Step 5: Write `tests/test_workflows_harness.py`**

```python
"""Workflow file parses + every uses: is SHA-pinned (D20)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).parent.parent / ".github" / "workflows" / "harness-test.yml"


def test_workflow_parses() -> None:
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert "jobs" in data


def test_workflow_triggers() -> None:
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    on = data[True] if True in data else data["on"]  # yaml interprets `on` as boolean True
    assert "schedule" in on
    assert "workflow_dispatch" in on
    assert "pull_request" in on


def test_workflow_matrix_has_5_fixtures() -> None:
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    fixtures = data["jobs"]["harness-test"]["strategy"]["matrix"]["fixture"]
    assert len(fixtures) == 5


def test_all_uses_pinned_to_commit_sha() -> None:
    text = WORKFLOW_PATH.read_text()
    pattern = re.compile(r"uses:\s+([^@\s]+)@([0-9a-f]{40})")
    matches = pattern.findall(text)
    assert matches, "no SHA-pinned uses: found"
    for owner_repo, sha in matches:
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)


def test_no_unpinned_uses() -> None:
    text = WORKFLOW_PATH.read_text()
    # Any `uses:` followed by @<not-40-hex> is a violation
    pattern = re.compile(r"uses:\s+([^@\s]+)@([^\s]+)")
    for match in pattern.finditer(text):
        suffix = match.group(2)
        assert len(suffix) == 40 and all(c in "0123456789abcdef" for c in suffix), (
            f"unpinned uses: {match.group(0)}"
        )


def test_emergency_issue_step_present() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "if: failure()" in text
    assert "issues.create" in text
```

- [ ] **Step 6: Run D20 invariant test (existing) + new tests**

Run:
```bash
pytest tests/test_action_pinning.py tests/test_workflows_harness.py -v
```
Expected: all pass (existing D20 test now also covers `harness-test.yml`; new tests cover workflow-specific behavior)

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/harness-test.yml .github/dependabot.yml tests/test_workflows_harness.py
git commit -m "feat(telemetry): add harness-test.yml workflow with D20 SHA-pinning

Weekly Sunday 02:00 UTC cron + workflow_dispatch + pull_request labeled
harness-test. Matrix on 5 curated fixtures. Every uses: pinned to 40-char
commit SHA (D20). if: failure() step opens emergency issue with traceback.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: ADR + integration smoke + close sub-spec 2

**Files:**
- Create: `catalog/reviews/observability-sub-spec-2.md` — ADR
- Create: `tests/test_sub_spec_2_integration.py` — end-to-end smoke using meta-fixture + local claude-stub
- Modify: `README.md` — add `harness-test` workflow note

**Interfaces:**
- Consumes: Tasks 1-4
- Produces: ADR + integration smoke + close-out

**GitHub issue title:** `[harness-observability] ADR + integration smoke + close sub-spec 2`

**Acceptance criteria:**
- [ ] ADR at `catalog/reviews/observability-sub-spec-2.md` documents design choices
- [ ] Integration smoke runs the meta-fixture + capture script in CI mode (`HERETEK_TELEMETRY_ROOT=/tmp/...`) and asserts artifact bundle shape
- [ ] README mentions `harness-test.yml` under "Workflows" section
- [ ] `pytest -q` exits clean
- [ ] Issue filed: "sub-spec 2 ready for sub-spec 3 consumption"

- [ ] **Step 1: Write `catalog/reviews/observability-sub-spec-2.md`**

Use `catalog/reviews/0000-template.md`. Fill in:
- Decision: ship sub-spec 2 per `docs/superpowers/specs/2026-08-08-harness-observability-test-pipeline.md`
- Consequences: positive (sub-spec 3 has data to evaluate), negative (CI minutes cost; fixture maintenance burden)
- Alternatives considered: SWE-bench verbatim (rejected — too large for v1), opencode-only (rejected — Claude Code is the primary target)

- [ ] **Step 2: Write `tests/test_sub_spec_2_integration.py`**

```python
"""End-to-end integration smoke for sub-spec 2: meta-fixture + runner + bundle."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
META_FIXTURE = PLUGIN_ROOT / "tests" / "fixtures" / "harness" / "fixture-meta-meta"


def test_integration_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path / "telemetry"))
    subprocess.run(["bash", "setup.sh"], cwd=META_FIXTURE, check=True, capture_output=True)
    rc = subprocess.run(
        [
            sys.executable,
            str(PLUGIN_ROOT / "scripts" / "harness_test.py"),
            "--fixture", "fixture-meta-meta",
            "--output", str(tmp_path / "artifacts"),
            "--claude-cmd", str(META_FIXTURE / "run-claude.sh"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 0
    bundle = tmp_path / "artifacts" / "harness-fixture-meta-meta"
    assert bundle.exists()
    eval_input = json.loads((bundle / "eval_input.json").read_text())
    assert eval_input["fixture"] == "fixture-meta-meta"
```

- [ ] **Step 3: Update `README.md`**

Add under the existing "Common commands" section:

```markdown
# Harness test pipeline (sub-spec 2)
pytest -q tests/test_harness_test.py    # local runner test
python scripts/harness_test.py --fixture fixture-meta-meta --output /tmp/artifacts  # manual run
# Weekly cron: harness-test.yml runs all 5 fixtures on Sundays 02:00 UTC
```

- [ ] **Step 4: Run full test suite**

Run:
```bash
pytest -q
python scripts/validate.py
```
Expected: all green

- [ ] **Step 5: Commit + comment**

```bash
git add catalog/reviews/observability-sub-spec-2.md tests/test_sub_spec_2_integration.py README.md
git commit -m "docs(telemetry): ADR + integration smoke (sub-spec 2 close-out)

Sub-spec 2 ready for sub-spec 3 consumption. Artifact bundles produced by
harness-test.yml will be the input to eval harness (sub-spec 3).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Comment on issue #2:
```
✅ Sub-spec 2 shipped. harness-test.yml weekly cron active. Artifact bundles
produced and ready for sub-spec 3 (eval harness) to consume.

- Spec: docs/superpowers/specs/2026-08-08-harness-observability-test-pipeline.md
- ADR: catalog/reviews/observability-sub-spec-2.md
- Plan: docs/superpowers/plans/2026-08-08-harness-observability-test-pipeline.md
```

---

## Self-Review

1. **Spec coverage:** Every section of `2026-08-08-harness-observability-test-pipeline.md` has a task:
   - §2.1 harness-test.yml → Task 4
   - §2.2 fixtures → Tasks 2, 3
   - §2.3 harness_test.py → Task 1
   - §2.4 fixture-meta-meta → Task 2
   - §3 data flow → covered by Tasks 1, 4
   - §4 error handling → covered by Task 1 (fail-open) + Task 4 (emergency issue)
   - §5 testing → Tasks 1-5 all include test coverage requirements
   - §6 phases → Tasks 1-5 = phases 2.1, 2.2, 2.3, 2.4
   - §7 references → linked from ADR (Task 5)
2. **Placeholder scan:** No TBD / TODO / "implement later". Step 1 of Task 3 ("Similar to fixture-1") is avoided by repeating concrete code in each step.
3. **Type consistency:** `run_fixture`, `write_artifact_bundle`, `compute_sha256`, `main` defined in Task 1 and used consistently throughout.

No fixes needed.