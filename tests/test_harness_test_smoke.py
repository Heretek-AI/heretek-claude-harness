"""Smoke test for harness_test.py — does NOT spawn real claude CLI.

Uses a fixture whose setup.sh writes a known patch.diff directly, sidestepping
the claude invocation. Full fixture-runner test lives in tests/test_harness_test.py
with fixture-meta-meta.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

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
        metadata={
            "run_id": "00000000-0000-4000-8000-000000000001",
            "fixture": "test-fixture",
        },
        task_prompt="# Task\n",
        expected={"type": "curated", "auto_grade": {}},
    )
    assert (bundle / "patch.diff").exists()
    assert (bundle / "telemetry.jsonl").exists()
    assert (bundle / "claude-session.log").exists()
    assert (bundle / "metadata.json").exists()
    eval_input = json.loads((bundle / "eval_input.json").read_text())
    assert eval_input["fixture"] == "test-fixture"
    assert (
        eval_input["patch_diff_sha256"]
        == hashlib.sha256(b"diff --git a/foo b/foo\n").hexdigest()
    )
    assert "task_prompt" in eval_input
    assert "expected" in eval_input
