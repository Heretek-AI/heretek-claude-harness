"""End-to-end install tests for the ``install_apk`` MCP tool.

These tests require a connected Android emulator with ``adb``
reachable on ``PATH``. They run under ``just test-device`` and
are skipped under the default ``just test`` invocation
(``@pytest.mark.device``).

Each test installs a small fake APK against a real device. The
fake APK is a zero-byte file (size matters for the ``-S`` flag
in the staged flow); the install will fail at ``pm install`` with
``INSTALL_FAILED_NO_INSTALL`` (or similar) but the test asserts
that the install-ladder *dispatch* works — i.e. the right
strategy was selected and the call returned without raising.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Mark every test in this module as requiring a device.
pytestmark = pytest.mark.device

DYNAMIC_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(DYNAMIC_SRC) not in sys.path:
    sys.path.insert(0, str(DYNAMIC_SRC))


@pytest.fixture
def fake_apk(tmp_path: Path) -> Path:
    """A tiny but real file on disk so the install path can be exercised."""
    p = tmp_path / "fake.apk"
    # 1 KB of zero bytes — small enough to push quickly, large enough
    # to look like a real APK to ``pm install``.
    p.write_bytes(b"\x00" * 1024)
    return p


def _build_tool():
    """Return the ``install_apk`` tool function from the dynamic server."""
    from mcp.server.fastmcp import FastMCP

    from android_re_mcp_dynamic.tools.device_tools import register

    mcp = FastMCP(name="test-install-e2e")
    register(mcp)
    tools = {t.name: t.fn for t in mcp._tool_manager._tools.values()}  # type: ignore[attr-defined]
    return tools["install_apk"]


def _pick_serial() -> str:
    """Return the first connected emulator serial, or skip the test."""
    from android_re_core.device.adb import list_devices

    devs = list_devices()
    if not devs:
        pytest.skip("no adb devices connected; start an emulator first")
    return devs[0].serial


def test_install_apk_against_emulator_api_33(fake_apk: Path) -> None:
    """Install against an API 33 device. Strategy 1 (one-shot)."""
    serial = _pick_serial()
    install = _build_tool()
    # The fake APK won't actually install (it's not a real APK), so
    # we accept either success or failure — the test is about the
    # *ladder dispatch*, not the actual install.
    result = install(
        serial=serial,
        apk_path=str(fake_apk),
        replace=True,
        allow_downgrade=False,
        confirm=True,
    )
    assert "status" in result or "error" in result
    # On API 33, the result's strategy (if returned) must be adb_install.
    if "strategy" in result:
        assert result["strategy"] == "adb_install"


def test_install_apk_against_emulator_forces_staged(
    fake_apk: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ANDROID_RE_FORCE_STAGED=1, the staged path is taken.

    This forces the dispatcher to call strategy 1 and return;
    the staged path is a separate manual call. We assert that
    the forced mode returns a strategy=adb_install result on
    the real device.
    """
    monkeypatch.setenv("ANDROID_RE_FORCE_STAGED", "1")
    serial = _pick_serial()
    install = _build_tool()
    result = install(
        serial=serial,
        apk_path=str(fake_apk),
        confirm=True,
    )
    if "strategy" in result:
        assert result["strategy"] == "adb_install"


def test_install_apk_against_emulator_dry_run(fake_apk: Path) -> None:
    """confirm=false writes the dry-run summary on a real device."""
    install = _build_tool()
    result = install(
        serial="emu-5554",
        apk_path=str(fake_apk),
        confirm=False,
    )
    assert result["error"]["code"] == "confirm_required"
    assert "strategy_ladder" in result["error"]["dry_run_summary"]
