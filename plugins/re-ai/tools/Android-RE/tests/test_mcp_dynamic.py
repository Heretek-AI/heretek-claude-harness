"""Contract tests for the dynamic MCP server.

Verifies the server builds and registers the expected tool surface
without invoking any device-bound tools.
"""

from __future__ import annotations

import asyncio

import pytest


def test_dynamic_server_builds():
    pytest.importorskip("mcp", reason="mcp not installed")
    pytest.importorskip("frida", reason="frida not installed")
    from android_re_mcp_dynamic.server import build_server

    server = build_server()
    assert server is not None
    assert server.name == "android-re-dynamic"


def test_dynamic_server_exposes_30_plus_tools():
    pytest.importorskip("mcp", reason="mcp not installed")
    pytest.importorskip("frida", reason="frida not installed")
    from android_re_mcp_dynamic.server import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    assert len(tools) >= 30, f"Expected >= 30 dynamic tools, got {len(tools)}"
    # Spot-check a few
    names = {t.name for t in tools}
    for must_have in (
        "list_devices",
        "frida_spawn",
        "frida_attach",
        "frida_load_script",
        "frida_rpc_call",
        "install_apk",
        "take_screenshot",
        "start_logcat",
        "setup_mitm",
        "build_session_report",
    ):
        assert must_have in names, f"missing: {must_have}"


def test_native_server_unchanged():
    """Sanity check: native server has the expected tool set.

    The count grew from 19 → 22 when ``open_project`` / ``close_project`` /
    ``list_projects`` were added so the native server is self-contained
    (Phase 4 follow-up: project-store separation). Update the count here
    when adding or removing native tools.
    """
    pytest.importorskip("mcp", reason="mcp not installed")
    pytest.importorskip("lief", reason="lief not installed")
    from android_re_mcp_native.server import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    # The 3 project-lifecycle tools added for the native server.
    for must_have in ("open_project", "close_project", "list_projects"):
        assert must_have in names, f"missing: {must_have}"
    assert len(tools) == 22


def test_static_server_unchanged():
    """Sanity check: static server still has the decompile toolset after Phase 3.

    The full tool-name subset check lives in
    ``test_mcp_static.py::test_static_server_exposes_expected_tool_names``.
    This test only confirms the dynamic-side hasn't accidentally
    regressed the decompile tools.
    """
    pytest.importorskip("mcp", reason="mcp not installed")
    pytest.importorskip("androguard", reason="androguard not installed")
    from android_re_mcp_static.server import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {t.name for t in tools}
    expected = {
        "decompile_class",
        "decompile_method",
        "decompile_apk",
        "read_source",
        "get_smali",
    }
    missing = expected - tool_names
    assert not missing, f"Decompile tools missing: {missing}"
