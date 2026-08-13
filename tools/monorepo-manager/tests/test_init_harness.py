"""End-to-end tests for scripts/init-harness.sh generation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scripts.lib.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_init_harness_generates_harness_files(tmp_path):
    result = _run(
        [
            "--target",
            str(tmp_path),
            "--name",
            "llama-builds",
            "--stack",
            "python",
            "--project-id",
            "1",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "CLAUDE.md").is_file()
    assert (tmp_path / ".mcp.json").is_file()
    assert (tmp_path / ".claude" / "settings.json").is_file()


def test_init_harness_generates_all_workflows(tmp_path):
    _run(
        ["--target", str(tmp_path), "--name", "heretek-manager", "--stack", "node"],
        cwd=tmp_path,
    )
    for name in ("super-linter.yml", "pre-commit.yml", "sonarcloud.yml", "secret-scan.yml"):
        assert (tmp_path / ".github" / "workflows" / name).is_file()


def test_init_harness_bakes_contract_hash(tmp_path):
    _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    payload = json.loads((tmp_path / ".heretek-harness.json").read_text())
    assert "contract_hash" in payload
    assert len(payload["contract_hash"]) == 16


def test_init_harness_refuses_on_drift(tmp_path):
    # First run establishes the hash.
    _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    # Second run without --force must succeed because the spec hasn't changed.
    result = _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    # Now corrupt the hash to simulate drift.
    payload = json.loads((tmp_path / ".heretek-harness.json").read_text())
    payload["contract_hash"] = "0" * 16
    (tmp_path / ".heretek-harness.json").write_text(json.dumps(payload))
    result = _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "drift" in result.stderr


def test_init_harness_force_overrides_drift(tmp_path):
    _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    payload = json.loads((tmp_path / ".heretek-harness.json").read_text())
    payload["contract_hash"] = "0" * 16
    (tmp_path / ".heretek-harness.json").write_text(json.dumps(payload))
    result = _run(
        [
            "--target",
            str(tmp_path),
            "--name",
            "llama-builds",
            "--stack",
            "python",
            "--force",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0


def test_init_harness_verify_clean(tmp_path):
    _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    result = _run(["--target", str(tmp_path), "--verify"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr


def test_init_harness_against_sandbox_python(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    # Pretend the sandbox has a previous README and a package.json for context.
    (sandbox / "README.md").write_text("pre-existing")
    result = _run(
        ["--target", str(sandbox), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    sandbox_files = {p.name for p in sandbox.iterdir()}
    assert "README.md" in sandbox_files  # preserved
    assert "AGENTS.md" in sandbox_files  # generated
    assert ".mcp.json" in sandbox_files


def test_init_harness_against_sandbox_node(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "package.json").write_text("{}")
    result = _run(
        ["--target", str(sandbox), "--name", "heretek-manager", "--stack", "node"],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    text = (sandbox / "AGENTS.md").read_text()
    assert "Node 20" in text


def test_init_harness_does_not_copy_seeds_yaml_to_child(tmp_path):
    """Fix #1: per spec §10 children never receive seeds/<repo>.yaml."""
    result = _run(
        [
            "--target",
            str(tmp_path),
            "--name",
            "llama-builds",
            "--stack",
            "python",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    # Umbrella seeds/<repo>.yaml must NOT be mirrored into the child.
    assert not (tmp_path / "seeds" / "llama-builds.yaml").exists()
    assert not (tmp_path / "seeds" / "heretek-manager.yaml").exists()
    # The child-side labels copy IS allowed under .github/labels/.
    assert (tmp_path / ".github" / "labels" / "labels.yaml").is_file()
    # But the umbrella-side seeds/labels.yaml must NOT appear in the child either.
    assert not (tmp_path / "seeds" / "labels.yaml").exists()


def test_init_harness_makes_seed_issues_sh_executable(tmp_path):
    """Fix #7: child scripts must be executable (chmod 0o755)."""
    import stat

    result = _run(
        [
            "--target",
            str(tmp_path),
            "--name",
            "llama-builds",
            "--stack",
            "python",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    script = tmp_path / "scripts" / "seed-issues.sh"
    assert script.is_file()
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/seed-issues.sh must be executable"
    assert mode & stat.S_IXGRP
    assert mode & stat.S_IXOTH


def test_init_harness_seed_edit_changes_baked_hash(tmp_path):
    """Fix #6: per spec §10, editing any seeds/*.yaml invalidates downstream installs."""
    # First run establishes a hash.
    _run(
        [
            "--target",
            str(tmp_path),
            "--name",
            "llama-builds",
            "--stack",
            "python",
        ],
        cwd=tmp_path,
    )
    payload = json.loads((tmp_path / ".heretek-harness.json").read_text())
    original = payload["contract_hash"]
    # Edit one seed file: append a trailing newline to a comment line.
    seeds_dir = REPO_ROOT / "seeds"
    target_seed = seeds_dir / "llama-builds.yaml"
    backup = target_seed.read_text()
    target_seed.write_text(backup + "\n")
    try:
        # Without --force the second run must refuse because the seed hash changed.
        result = _run(
            [
                "--target",
                str(tmp_path),
                "--name",
                "llama-builds",
                "--stack",
                "python",
            ],
            cwd=tmp_path,
        )
        assert (
            result.returncode == 2
        ), f"expected drift (rc=2) after seed edit, got {result.returncode}: {result.stderr}"
        assert "drift" in result.stderr
        # With --force the run regenerates and the hash now differs from the
        # original (because the seed content is different).
        result = _run(
            [
                "--target",
                str(tmp_path),
                "--name",
                "llama-builds",
                "--stack",
                "python",
                "--force",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        new_payload = json.loads((tmp_path / ".heretek-harness.json").read_text())
        assert new_payload["contract_hash"] != original
    finally:
        target_seed.write_text(backup)
