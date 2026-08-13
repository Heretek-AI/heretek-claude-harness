"""Tests for the :mod:`android_re_core.paths` module."""

from __future__ import annotations

from pathlib import Path

import pytest

from android_re_core import paths
from android_re_core.errors import APKNotFound, ToolNotFound


def test_repo_root_exists():
    """The REPO_ROOT constant must point to a real directory."""
    assert paths.REPO_ROOT.exists()
    assert paths.REPO_ROOT.is_dir()
    assert (paths.REPO_ROOT / "pyproject.toml").exists()


def test_vendor_dir_is_under_repo_root():
    assert paths.VENDOR_DIR.parent == paths.REPO_ROOT
    # The vendor dir may not exist on a fresh checkout; that's OK.
    # We just check the path is well-formed.
    assert paths.VENDOR_DIR.name == "vendor"


def test_find_tool_raises_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """find_tool raises ToolNotFound when the tool is not on PATH or in vendor/."""
    # Point VENDOR_DIR at an empty tmp dir to make sure no fallback.
    monkeypatch.setattr(paths, "VENDOR_DIR", tmp_path / "empty-vendor")
    with pytest.raises(ToolNotFound) as exc:
        paths.find_tool("definitely-not-a-real-tool-xyz123")
    assert exc.value.code == "tool_not_found"


def test_find_tool_respects_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """An env var takes precedence over PATH and vendor/."""
    fake = tmp_path / "my-fake-tool"
    fake.write_text("#!/bin/sh\necho fake\n")
    fake.chmod(0o755)
    monkeypatch.setenv("ADB", str(fake))  # ADB is the env var find_adb uses
    assert paths.find_adb() == fake


def test_tool_version_default(monkeypatch: pytest.MonkeyPatch):
    """TOOL_VERSION defaults to the library version."""
    monkeypatch.delenv("ANDROID_RE_VENDOR_VERSION", raising=False)
    assert paths.TOOL_VERSION == "0.1.0"


# ---------------------------------------------------------------------------
# Output/ directory convention
# ---------------------------------------------------------------------------


def test_output_dir_default_under_repo_root(monkeypatch: pytest.MonkeyPatch):
    """OUTPUT_DIR defaults to ``<REPO_ROOT>/Output`` when the env var is unset."""
    monkeypatch.delenv("ANDROID_RE_OUTPUT_DIR", raising=False)
    # The default depends on whether the env var was set at import time
    # of android_re_core.paths. We can't reliably re-import here, so
    # just assert the path is well-formed and absolute.
    assert paths.OUTPUT_DIR.is_absolute()
    assert paths.OUTPUT_DIR.name == "Output"


def test_triage_dir_is_alias_for_output_dir():
    """The legacy TRIAGE_DIR constant is now an alias for OUTPUT_DIR."""
    assert paths.TRIAGE_DIR == paths.OUTPUT_DIR


def test_output_dir_for_naming(tmp_path: Path):
    """output_dir_for returns ``<stem>-<8hex>`` under OUTPUT_DIR."""
    apk = tmp_path / "my-app.apk"
    apk.write_bytes(b"hello world")  # sha256: b94d27b9... → b94d27b9
    d = paths.output_dir_for(apk)
    assert d.parent == paths.OUTPUT_DIR
    assert d.name == "my-app-b94d27b9"
    # Function is pure: does not create the directory.
    assert not d.exists()


def test_output_dir_for_accepts_string(tmp_path: Path):
    """output_dir_for accepts both str and PathLike inputs."""
    apk = tmp_path / "foo.apk"
    apk.write_bytes(b"x")
    d_str = paths.output_dir_for(str(apk))
    d_path = paths.output_dir_for(apk)
    assert d_str == d_path


def test_output_dir_for_missing_raises(tmp_path: Path):
    """output_dir_for raises APKNotFound if the APK does not exist."""
    with pytest.raises(APKNotFound):
        paths.output_dir_for(tmp_path / "does-not-exist.apk")


def test_output_dir_for_is_stable_for_same_input(tmp_path: Path):
    """The same APK path (same basename + same content) yields the same dir."""
    apk = tmp_path / "a.apk"
    apk.write_bytes(b"same")
    d1 = paths.output_dir_for(apk)
    d2 = paths.output_dir_for(apk)
    assert d1 == d2


def test_output_dir_for_distinguishes_different_basenames(tmp_path: Path):
    """Two APKs with identical content but different basenames get different dirs."""
    a = tmp_path / "a.apk"
    b = tmp_path / "b.apk"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    assert paths.output_dir_for(a) != paths.output_dir_for(b)


def test_output_dir_for_distinguishes_different_content(tmp_path: Path):
    """Two APKs with different content get different directory names."""
    a = tmp_path / "a.apk"
    b = tmp_path / "b.apk"
    a.write_bytes(b"alpha")
    b.write_bytes(b"beta")
    assert paths.output_dir_for(a) != paths.output_dir_for(b)
