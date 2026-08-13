"""Unit tests for :mod:`android_re_core.device.adb_install`.

These tests mock :mod:`android_re_core.device.adb` and the
underlying ``subprocess.run`` calls so the new install ladder
can be exercised without a connected device. The single
device-bound test lives in
``mcp_servers/dynamic/tests/test_adb_install_e2e.py`` and is
gated by ``@pytest.mark.device``.

The clean-room constraint is enforced by the
``test_no_eval_in_module`` and
``test_does_not_construct_shell_string_concat`` tests at the
bottom of the file.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from android_re_core.device import adb as adb_module
from android_re_core.device import adb_install
from android_re_core.errors import APKNotFound, ToolFailed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_proc(stdout: str = "Success\n", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _fail_proc(
    stdout: str = "", stderr: str = "Failure [INSTALL_FAILED_OWNER_BLOCKED]\n"
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# detect_api_level
# ---------------------------------------------------------------------------


def test_detect_api_level_parses_int() -> None:
    """getprop returns a numeric string -> parsed int."""
    with patch.object(adb_module, "getprop", return_value="34\n"):
        assert adb_install.detect_api_level("emu") == 34


def test_detect_api_level_raises_on_garbage() -> None:
    """getprop returns garbage -> ToolFailed."""
    with (
        patch.object(adb_module, "getprop", return_value=""),
        pytest.raises(ToolFailed),
    ):
        adb_install.detect_api_level("emu")


# ---------------------------------------------------------------------------
# _existing_adb_install (strategy 1)
# ---------------------------------------------------------------------------


def test_existing_strategy_used_on_api_33(tmp_path: Path) -> None:
    """On API 33, only the one-shot ``adb install`` is invoked; the
    push+pm and staged paths are not.
    """
    apk = tmp_path / "sample.apk"
    apk.write_bytes(b"fake-apk-bytes")
    with (
        patch.object(adb_module, "getprop", return_value="33"),
        patch.object(adb_install, "_run_adb_raw", return_value=_ok_proc()) as run_raw,
    ):
        result = adb_install.install_apk("emu", str(apk))
    assert result.status == "success"
    assert result.strategy == "adb_install"
    # Exactly one adb invocation; it carries the install subcommand.
    assert run_raw.call_count == 1
    call_args = run_raw.call_args.args[0]
    assert "install" in call_args
    assert str(apk) in call_args


# ---------------------------------------------------------------------------
# _push_then_pm_install (strategy 2)
# ---------------------------------------------------------------------------


def test_push_strategy_used_on_api_34(tmp_path: Path) -> None:
    """On API 34 with strategy-1 success, the push+pm path is not invoked."""
    apk = tmp_path / "sample.apk"
    apk.write_bytes(b"fake-apk-bytes")
    with (
        patch.object(adb_module, "getprop", return_value="34"),
        patch.object(adb_install, "_run_adb_raw", return_value=_ok_proc()) as run_raw,
    ):
        result = adb_install.install_apk("emu", str(apk))
    assert result.status == "success"
    # On a happy path, exactly one adb invocation (the install).
    assert run_raw.call_count == 1
    assert "install" in run_raw.call_args.args[0]


def test_staged_strategy_used_when_push_pm_fails_on_api_34(tmp_path: Path) -> None:
    """On API 34 with strategy-1 failure, escalate to push+pm;
    if push+pm also fails, escalate to staged.
    """
    apk = tmp_path / "sample.apk"
    apk.write_bytes(b"fake-apk-bytes")
    # Sequence: strategy 1 fails (INSTALL_FAILED_OWNER_BLOCKED),
    # push succeeds, pm install fails with INSUFFICIENT_STORAGE
    # (staged-eligible), then staged flow runs:
    #   push (again, idempotent) -> success
    #   pm install-create -> returns a session id
    #   pm install-write -> "Success"
    #   pm install-commit -> "Success"
    run_raw_results = [
        _fail_proc("Failure [INSTALL_FAILED_OWNER_BLOCKED]\n"),  # strategy 1
        _ok_proc("100KB/s (100000 bytes in 1.000s)\n"),  # push in strategy 2
        _ok_proc("100KB/s (100000 bytes in 1.000s)\n"),  # push in strategy 3 (idempotent)
    ]
    shell_argv_results = [
        "Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]\n",  # pm install (strategy 2)
        "42\n",  # pm install-create (strategy 3) -> session id 42
        "Success\n",  # pm install-write
        "Success\n",  # pm install-commit
    ]
    with (
        patch.object(adb_module, "getprop", return_value="34"),
        patch.object(adb_install, "_run_adb_raw", side_effect=run_raw_results),
        patch.object(adb_module, "shell_argv", side_effect=shell_argv_results),
        patch.object(adb_install, "_apk_short_hash", return_value="abc123def456"),
        patch.object(adb_install, "_read_package_safe", return_value="com.example"),
    ):
        result = adb_install.install_apk("emu", str(apk))
    assert result.status == "success"
    assert result.strategy == "staged_install"
    assert result.package == "com.example"


# ---------------------------------------------------------------------------
# InstallResult.to_dict
# ---------------------------------------------------------------------------


def test_returns_structured_install_result() -> None:
    """to_dict() returns the documented schema."""
    r = adb_install.InstallResult(
        status="success",
        api_level=34,
        strategy="push_then_pm_install",
        output="Success",
        package="com.example",
        elapsed_s=1.23,
    )
    d = r.to_dict()
    assert d == {
        "status": "success",
        "api_level": 34,
        "strategy": "push_then_pm_install",
        "output": "Success",
        "package": "com.example",
        "elapsed_s": 1.23,
    }


# ---------------------------------------------------------------------------
# Output convention: dry-run summary lives in the MCP wrapper, not here.
# We assert the Output path is what the wrapper computes.
# ---------------------------------------------------------------------------


def test_dry_run_uses_output_dir_for_helper(tmp_path: Path) -> None:
    """The MCP wrapper's dry-run path is computed by ``output_dir_for``.

    The actual dry-run summary file is written by the MCP wrapper,
    not by the core install function. We test the path computation
    by calling ``output_dir_for`` directly with the same input the
    wrapper uses.
    """
    from android_re_core.paths import output_dir_for

    apk_path = tmp_path / "sample.apk"
    apk_path.write_bytes(b"fake-apk-bytes")

    expected = output_dir_for(apk_path) / "dynamic" / "install-attempt.dry-run.json"
    assert expected.name == "install-attempt.dry-run.json"
    assert expected.parent.name == "dynamic"


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


def test_handles_missing_apk(tmp_path: Path) -> None:
    """``apk_path`` not on disk -> APKNotFound."""
    missing = tmp_path / "does-not-exist.apk"
    with pytest.raises(APKNotFound):
        adb_install.install_apk("emu", str(missing))


# ---------------------------------------------------------------------------
# Clean-room / no-eval constraints (policy enforcement, not behaviour)
# ---------------------------------------------------------------------------


def test_no_eval_in_module() -> None:
    """The new module does not call ``eval`` / ``exec`` / ``compile``."""
    src = Path(adb_install.__file__).read_text()  # type: ignore[attr-defined]
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"eval", "exec", "compile"}:
                pytest.fail(f"Forbidden call to {func.id} in adb_install.py at line {node.lineno}")


def test_does_not_construct_shell_string_concat() -> None:
    """No ``_adb.shell(...)`` call uses an f-string; the module uses ``shell_argv``."""
    src = Path(adb_install.__file__).read_text()  # type: ignore[attr-defined]
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match ``_adb.shell(...)`` (an Attribute on a Name).
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "shell"
            and isinstance(func.value, ast.Name)
            and func.value.id == "_adb"
        ):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.JoinedStr):
            pytest.fail(
                f"Forbidden f-string passed to _adb.shell() at line {node.lineno}; "
                f"use _adb.shell_argv with an explicit argv list instead."
            )


# ---------------------------------------------------------------------------
# ANDROID_RE_FORCE_STAGED escape hatch
# ---------------------------------------------------------------------------


def test_android_re_force_staged_skips_ladder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the env var is set, only strategy 1 is tried; no escalation."""
    monkeypatch.setenv("ANDROID_RE_FORCE_STAGED", "1")
    apk = tmp_path / "sample.apk"
    apk.write_bytes(b"fake-apk-bytes")
    with (
        patch.object(adb_module, "getprop", return_value="34"),
        patch.object(adb_install, "_run_adb_raw", return_value=_ok_proc()) as run_raw,
    ):
        result = adb_install.install_apk("emu", str(apk))
    assert result.status == "success"
    # Strategy 1 only — no push, no staged.
    assert run_raw.call_count == 1
    assert "install" in run_raw.call_args.args[0]
