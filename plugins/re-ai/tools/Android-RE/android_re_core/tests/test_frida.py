"""Tests for the :mod:`android_re_core.frida` and :mod:`android_re_core.device.adb` modules.

All tests that require a live Frida device or adb connection are
marked ``@pytest.mark.device`` and are skipped by default in CI.
Mock-based unit tests run without any device.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from android_re_core.device.adb import (
    AdbDevice,
    dumpsys,
    getprop,
    list_devices,
    run_adb,
    shell,
)
from android_re_core.errors import ToolFailed, ToolNotFound, ToolTimeout
from android_re_core.frida.device import (
    PINNED_FRIDA_VERSION,
    _version_match,
)
from android_re_core.frida.device import (
    list_devices as frida_list_devices,
)
from android_re_core.frida.rpc import call_rpc
from android_re_core.frida.scripts import ScriptStore
from android_re_core.frida.session import SessionStore

# ---------------------------------------------------------------------------
# Version match
# ---------------------------------------------------------------------------


class TestVersionMatch:
    def test_exact_match(self):
        assert _version_match("17.10.1", "17.10.1") is True

    def test_suffix_stripped(self):
        assert _version_match("17.10.1-rc.1", "17.10.1") is True
        assert _version_match("17.10.1+suffix", "17.10.1") is True

    def test_mismatch(self):
        assert _version_match("16.1.0", "17.10.1") is False
        assert _version_match("17.11.0", "17.10.1") is False

    def test_pinned_version_is_string(self):
        assert isinstance(PINNED_FRIDA_VERSION, str)
        assert PINNED_FRIDA_VERSION == "17.10.1"


# ---------------------------------------------------------------------------
# ADB device wrapper
# ---------------------------------------------------------------------------


class TestAdbDevice:
    def test_to_dict(self):
        d = AdbDevice(serial="emulator-5554", state="device")
        assert d.to_dict() == {"serial": "emulator-5554", "state": "device"}

    def test_list_devices_parses_output(self):
        """list_devices parses the standard adb devices -l output."""
        fake_stdout = (
            "List of devices attached\n"
            "emulator-5554    device product:foo model:bar device:emulator\n"
            "ABC123   unauthorized\n"
        )
        with patch("android_re_core.device.adb.run_adb") as mock_run:
            mock_run.return_value.stdout = fake_stdout
            mock_run.return_value.returncode = 0
            devs = list_devices()
        assert len(devs) == 2
        assert devs[0].serial == "emulator-5554"
        assert devs[0].state == "device"
        assert devs[1].serial == "ABC123"
        assert devs[1].state == "unauthorized"

    def test_list_devices_empty(self):
        with patch("android_re_core.device.adb.run_adb") as mock_run:
            mock_run.return_value.stdout = "List of devices attached\n"
            mock_run.return_value.returncode = 0
            assert list_devices() == []

    def test_shell_returns_stdout(self):
        with patch("android_re_core.device.adb.run_adb") as mock_run:
            mock_run.return_value.stdout = "Android 14\n"
            mock_run.return_value.returncode = 0
            out = shell("getprop ro.build.version.release", serial="emu")
        # shell returns the raw stdout (caller strips if needed)
        assert out == "Android 14\n"

    def test_getprop_trims(self):
        with patch("android_re_core.device.adb.run_adb") as mock_run:
            mock_run.return_value.stdout = "Pixel 8\n"
            mock_run.return_value.returncode = 0
            out = getprop("ro.product.model", serial="emu")
        assert out == "Pixel 8"

    def test_dumpsys_passes_args(self):
        with patch("android_re_core.device.adb.run_adb") as mock_run:
            mock_run.return_value.stdout = "...dumpsys output..."
            mock_run.return_value.returncode = 0
            dumpsys("activity", args=["activities"], serial="emu")
        # dumpsys() calls shell() which calls run_adb(['shell', <joined>])
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "shell"
        # The shell command is a single string with the service + args
        full = cmd[1] if len(cmd) > 1 else ""
        assert "dumpsys" in full
        assert "activity" in full
        assert "activities" in full
        assert mock_run.call_args.kwargs.get("serial") == "emu"

    def test_run_adb_propagates_tool_not_found(self):
        """If adb is missing, run_adb raises ToolNotFound."""
        from android_re_core.device import adb as adb_mod

        def _raise(*a, **kw):
            raise ToolNotFound("adb", details={})

        with patch.object(adb_mod, "find_adb", _raise), pytest.raises(ToolNotFound):
            run_adb(["devices"])

    def test_run_adb_propagates_timeout(self):
        import subprocess

        from android_re_core.device import adb as adb_mod

        with patch.object(adb_mod, "subprocess") as mock_sp:
            mock_sp.TimeoutExpired = subprocess.TimeoutExpired
            mock_sp.run.side_effect = subprocess.TimeoutExpired("adb", 5)
            with patch.object(adb_mod, "find_adb", return_value="/usr/bin/adb"):
                with pytest.raises(ToolTimeout):
                    run_adb(["devices"], timeout_s=5)

    def test_run_adb_propagates_failure(self):
        from android_re_core.device import adb as adb_mod

        with patch.object(adb_mod, "subprocess") as mock_sp:
            fake_proc = adb_mod.subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="adb: device not found"
            )
            mock_sp.run.return_value = fake_proc
            with patch.object(adb_mod, "find_adb", return_value="/usr/bin/adb"):
                with pytest.raises(ToolFailed):
                    run_adb(["devices"])


# ---------------------------------------------------------------------------
# Frida session / scripts / rpc (mocked)
# ---------------------------------------------------------------------------


class TestSessionStoreBasics:
    """SessionStore operations that don't require a live device."""

    def test_session_store_starts_empty(self):
        store = SessionStore()
        assert len(store) == 0
        assert store.list() == []

    def test_session_info_to_dict(self):
        from android_re_core.frida.session import SessionInfo

        info = SessionInfo(
            session_id="abc-123",
            pid=42,
            device_id="emulator-5554",
            package="com.example",
            created_at=1.0,
        )
        d = info.to_dict()
        assert d["session_id"] == "abc-123"
        assert d["pid"] == 42
        assert d["package"] == "com.example"


class TestScriptStoreBasics:
    def test_script_store_starts_empty(self):
        store = ScriptStore()
        assert store.list_for_session("any") == []


class TestRpcMocked:
    def test_call_rpc_method_not_found(self):
        """call_rpc raises KeyError when the method is not exported."""

        # A mock script that has no rpc.exports
        class _FakeScript:
            class rpc_exports:
                pass

        with pytest.raises(KeyError):
            call_rpc(_FakeScript, "missing")


# ---------------------------------------------------------------------------
# Live-device tests (skipped without a device)
# ---------------------------------------------------------------------------


@pytest.mark.device
class TestLiveFrida:
    """Live-device tests. Skipped unless a Frida device is reachable."""

    def test_frida_list_devices(self):
        devs = frida_list_devices()
        # We only assert that the call returns; the device count varies.
        assert isinstance(devs, list)

    def test_session_store_spawn_smoke(self):
        """Smoke-test the spawn path against a running app."""
        pytest.skip("Requires a real device with a launchable app")
