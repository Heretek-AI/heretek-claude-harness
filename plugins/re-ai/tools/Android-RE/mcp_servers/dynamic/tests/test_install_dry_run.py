"""Dry-run summary tests for the ``install_apk`` MCP tool.

The ``install_apk`` tool on the dynamic MCP server requires
``confirm=true`` to actually run the install. With ``confirm=false``
it returns a ``confirm_required`` error and writes a structured
dry-run summary to the ``Output/<apk>-<short-sha>/dynamic/``
directory.

These tests cover the dry-run path: the dry-run summary is
written to the expected path, contains the strategy ladder, and
returns the ``confirm_required`` error shape. The actual install
path is exercised by the device-bound ``test_adb_install_e2e.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the in-workspace dynamic server importable as a package.
DYNAMIC_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(DYNAMIC_SRC) not in sys.path:
    sys.path.insert(0, str(DYNAMIC_SRC))


@pytest.fixture
def apk_path(tmp_path: Path) -> Path:
    """A real (fake) APK on disk so the tool's precondition passes."""
    p = tmp_path / "sample.apk"
    p.write_bytes(b"fake-apk-bytes-for-dry-run")
    return p


def test_dry_run_writes_to_output_convention(apk_path: Path) -> None:
    """confirm=false writes the dry-run summary at the documented path.

    The expected path is
    ``Output/<apk-basename>-<short-sha>/dynamic/install-attempt.dry-run.json``
    by default; the test monkey-patches the project root so the
    summary lands in a known tmp_path.
    """
    # We import the tool registration function and call it with
    # an in-memory FastMCP client. If the test environment cannot
    # import the dynamic server (e.g., the workspace is not
    # installed), skip with a clear message.
    try:
        from mcp.server.fastmcp import FastMCP

        from android_re_mcp_dynamic.tools.device_tools import register
    except ImportError as e:
        pytest.skip(f"dynamic server not importable: {e}")

    mcp = FastMCP(name="test-install-dry-run")
    register(mcp)

    # We bypass the actual MCP client (avoids the long-running event
    # loop) and call the underlying tool function directly. To do
    # that, we pull the tool from the FastMCP internal registry.
    tools = {t.name: t.fn for t in mcp._tool_manager._tools.values()}  # type: ignore[attr-defined]
    install = tools["install_apk"]

    # The dry-run summary path is rooted at the per-APK Output dir,
    # which by default sits at ``<repo-root>/Output/``. We override
    # ANDROID_RE_OUTPUT_DIR so the summary lands in tmp_path.

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setenv("ANDROID_RE_OUTPUT_DIR", str(apk_path.parent))
        result = install(
            serial="emu-5554",
            apk_path=str(apk_path),
            replace=True,
            allow_downgrade=False,
            confirm=False,
        )
    finally:
        monkey.undo()

    # The tool returns the confirm_required error envelope.
    assert "error" in result
    assert result["error"]["code"] == "confirm_required"
    summary = result["error"]["dry_run_summary"]
    assert summary["dry_run"] is True
    assert summary["serial"] == "emu-5554"
    assert summary["apk_path"] == str(apk_path)
    assert summary["replace"] is True
    assert summary["allow_downgrade"] is False
    # The strategy ladder must list all 3 strategies.
    assert len(summary["strategy_ladder"]) == 3
    assert "adb_install" in summary["strategy_ladder"][0]
    assert "push_then_pm_install" in summary["strategy_ladder"][1]
    assert "staged_install" in summary["strategy_ladder"][2]

    # The summary file is on disk.
    expected = Path(summary["would_write_summary_to"])
    assert expected.exists()
    on_disk = json.loads(expected.read_text())
    assert on_disk["dry_run"] is True
    assert on_disk["serial"] == "emu-5554"


def test_dry_run_respects_output_path_override(apk_path: Path, tmp_path: Path) -> None:
    """When the caller passes ``output_path``, the summary lands there."""
    try:
        from mcp.server.fastmcp import FastMCP

        from android_re_mcp_dynamic.tools.device_tools import register
    except ImportError as e:
        pytest.skip(f"dynamic server not importable: {e}")

    mcp = FastMCP(name="test-install-dry-run-override")
    register(mcp)
    tools = {t.name: t.fn for t in mcp._tool_manager._tools.values()}  # type: ignore[attr-defined]
    install = tools["install_apk"]

    custom = tmp_path / "my-custom-summary.json"
    result = install(
        serial="emu-5554",
        apk_path=str(apk_path),
        confirm=False,
        output_path=str(custom),
    )
    assert result["error"]["code"] == "confirm_required"
    assert custom.exists()
    assert result["error"]["dry_run_summary"]["would_write_summary_to"] == str(custom)
