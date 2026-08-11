"""Hermetic test for scripts/terminal_bench_ab.sh.

Mocks the `harbor` binary via PATH manipulation. Asserts the script invokes
harbor twice (once per agent), with the right agent config (heretek for A,
baseline for B), and the right model.

Harbor is mocked via `HARBOR_CALL_LOG` env var; the fake harbor appends its
argv to that log file and exits 0.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def fake_harbor_dir(tmp_path: Path) -> Path:
    """Create a fake `harbor` binary that records invocations and exits 0."""
    d = tmp_path / "bin"
    d.mkdir()
    harbor = d / "harbor"
    harbor.write_text("#!/usr/bin/env bash\n" 'echo "$@" >> "$HARBOR_CALL_LOG"\n' "exit 0\n")
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
        "HERETEK_QUICK_SUBSET": str(repo_root / "scripts" / "tb_subset_quick.txt"),
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


def test_agent_b_has_no_plugin_dir(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """Agent B's harbor invocation must NOT include the --ak plugin_dir kwarg."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    calls = (tmp_path / "harbor-calls.log").read_text().splitlines()
    # Second call is agent B; it must not include --ak at all.
    assert "--ak" not in calls[1], f"agent B must not pass --ak; got: {calls[1]}"


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


def test_uses_claude_code_agent(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """Both agents must use the built-in claude-code adapter."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    call_log = (tmp_path / "harbor-calls.log").read_text()
    assert "claude-code" in call_log


def test_uses_terminal_bench_dataset(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """The script must pass terminal-bench@2.0 as the dataset."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    call_log = (tmp_path / "harbor-calls.log").read_text()
    assert "terminal-bench@2.0" in call_log


def test_passes_quick_subset_tasks(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """Each task ID from tb_subset_quick.txt must appear in the harbor invocations."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    call_log = (tmp_path / "harbor-calls.log").read_text()
    repo_root = Path(__file__).resolve().parent.parent
    subset = (repo_root / "scripts" / "tb_subset_quick.txt").read_text()
    for task_id in subset.splitlines():
        if not task_id.strip():
            continue
        assert task_id in call_log, f"task {task_id!r} not passed to harbor"


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


def test_separate_output_dirs_per_agent(fake_harbor_dir: Path, tmp_path: Path) -> None:
    """Agent A and Agent B must write to separate subdirs under RESULTS_DIR."""
    proc = _run_script(
        fake_harbor_dir,
        tmp_path,
        extra_env={"ANTHROPIC_MODEL": "test-model"},
    )
    assert proc.returncode == 0, proc.stderr
    calls = (tmp_path / "harbor-calls.log").read_text().splitlines()
    assert "--jobs-dir" in calls[0] or "-o" in calls[0]
    assert "--jobs-dir" in calls[1] or "-o" in calls[1]
    assert "agent-a" in calls[0]
    assert "agent-b" in calls[1]
    assert calls[0] != calls[1], "agent A and B must not share output dir"
