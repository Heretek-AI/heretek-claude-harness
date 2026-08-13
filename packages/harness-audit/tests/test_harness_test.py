"""Full fixture-runner test using fixture-meta-meta.

Mocks subprocess.run to invoke a deterministic stub that does NOT spawn
real claude CLI. Tests the harness_test.py runner end-to-end.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from harness_test import run_fixture  # noqa: E402


def test_run_fixture_meta_meta_produces_artifact_bundle(tmp_path: Path) -> None:
    fixture = PLUGIN_ROOT / "tests" / "fixtures" / "harness" / "fixture-meta-meta"
    output = tmp_path / "artifacts"

    with patch("harness_test.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        exit_code = run_fixture(fixture, output)

    assert exit_code == 0
    bundle = output / "harness-fixture-meta-meta"
    assert bundle.exists()
    assert (bundle / "patch.diff").exists()
    assert (bundle / "metadata.json").exists()
    assert (bundle / "eval_input.json").exists()


def test_artifact_bundle_metadata_has_required_keys(tmp_path: Path) -> None:
    fixture = PLUGIN_ROOT / "tests" / "fixtures" / "harness" / "fixture-meta-meta"
    output = tmp_path / "artifacts"

    with patch("harness_test.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        run_fixture(fixture, output)

    metadata = json.loads((output / "harness-fixture-meta-meta" / "metadata.json").read_text())
    for key in ["fixture", "start_time", "end_time", "model", "plugins"]:
        assert key in metadata, f"missing key: {key}"
