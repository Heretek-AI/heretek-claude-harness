"""Entry point for ``python -m android_re_mcp_static``.

Wires the FastMCP server to stdio and runs it. Use the ``mcp`` script
console or the Claude Code MCP config to register::

    claude mcp add android-re-static -- \\
        uv run --package android-re-mcp-static python -m android_re_mcp_static
"""

from __future__ import annotations

import sys


def main() -> int:
    """Build the server, attach stdio transport, and run forever."""
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
    except ImportError as e:  # pragma: no cover
        print(f"mcp package not installed: {e}", file=sys.stderr)
        return 1

    from android_re_mcp_static.server import build_server

    mcp: FastMCP = build_server()
    # FastMCP in mcp>=1.27 exposes ``run(transport=...)`` which defaults
    # to stdio. Calling ``run()`` with no args is the canonical stdio entry.
    mcp.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
