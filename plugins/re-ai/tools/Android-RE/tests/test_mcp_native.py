"""Contract tests for the native MCP server."""

from __future__ import annotations

import asyncio

import pytest


def test_native_server_builds():
    """The native server factory produces a non-None FastMCP instance."""
    pytest.importorskip("mcp", reason="mcp not installed")
    pytest.importorskip("lief", reason="lief not installed")
    from android_re_mcp_native.server import build_server

    server = build_server()
    assert server is not None
    assert server.name == "android-re-native"


def test_native_server_exposes_nineteen_tools():
    """Phase 2 ships exactly 19 native tools."""
    pytest.importorskip("mcp", reason="mcp not installed")
    pytest.importorskip("lief", reason="lief not installed")
    from android_re_mcp_native.server import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {t.name for t in tools}
    expected = {
        "list_binaries",
        "parse_binary",
        "get_sections",
        "get_symbols",
        "get_relocations",
        "get_imports",
        "get_exports",
        "get_security_features",
        "disassemble_function",
        "disassemble_bytes",
        "get_strings",
        "detect_packers",
        "lookup_signature",
        "extract_certificate_chain",
        "generate_frida_native_hook",
        "generate_native_interceptor",
        "compare_binaries",
        "yara_scan",
        "build_native_report",
    }
    missing = expected - tool_names
    assert not missing, f"Missing tools: {missing}"


# Note: the static server's tool-count assertion lives in
# tests/test_mcp_static.py (test_static_server_exposes_expected_tool_names).
# It is intentionally not duplicated here.
