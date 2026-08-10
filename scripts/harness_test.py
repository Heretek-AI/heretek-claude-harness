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
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HERETEK_PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "hooks"


def compute_sha256(text: str) -> str:
    """Compute SHA-256 hex digest of a UTF-8 string."""
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


def _collect_telemetry_jsonl() -> str:
    """Concat telemetry JSONL files from the collector (sub-spec 1) for today."""
    telemetry_root = Path(
        os.environ.get("HERETEK_TELEMETRY_ROOT", Path.home() / ".heretek" / "telemetry")
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions_dir = telemetry_root / "sessions" / today
    if not sessions_dir.exists():
        return ""
    parts = []
    for f in sorted(sessions_dir.glob("*.jsonl")):
        parts.append(f.read_text())
    return "".join(parts)


def _capture_git_diff(cwd: Path) -> str:
    """Capture git diff in `cwd`. Returns empty string on failure (best-effort)."""
    try:
        diff_proc = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        return diff_proc.stdout
    except Exception as exc:  # noqa: BLE001 — best-effort capture
        return f"--- git diff failed: {exc} ---\n"


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
        "--plugin-dir",
        str(heretek_plugin_dir),
    ]
    if os.environ.get("HERETEK_MODEL"):
        cmd += ["--model", os.environ["HERETEK_MODEL"]]
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
        log_lines.append(
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n"
        )
    except subprocess.TimeoutExpired:
        log_lines.append("--- TIMEOUT after 3600s ---\n")
        rc = 124
    except FileNotFoundError:
        log_lines.append(f"--- claude CLI not found at {claude_cmd} ---\n")
        rc = 127

    end_time = _now_iso()

    patch_diff = _capture_git_diff(fixture_dir)
    telemetry_jsonl = _collect_telemetry_jsonl()

    metadata = {
        "run_id": run_id,
        "fixture": fixture_name,
        "start_time": start_time,
        "end_time": end_time,
        "model": os.environ.get("HERETEK_MODEL", ""),
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
    parser = argparse.ArgumentParser(
        prog="harness_test", description="run one harness fixture"
    )
    parser.add_argument(
        "--fixture",
        required=True,
        help="fixture dir name under tests/fixtures/harness/",
    )
    parser.add_argument(
        "--output", required=True, help="output dir for artifact bundle"
    )
    parser.add_argument(
        "--claude-cmd", default="claude", help="path to claude CLI (for tests)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fixture_dir = (
        Path(__file__).parent.parent / "tests" / "fixtures" / "harness" / args.fixture
    )
    output_dir = Path(args.output)
    return run_fixture(fixture_dir, output_dir, claude_cmd=args.claude_cmd)


if __name__ == "__main__":
    sys.exit(main())
