"""Entry point for ``python -m android_re_mcp_native``."""

from __future__ import annotations

import sys


def main() -> int:
    """Build the server, attach stdio transport, and run."""
    try:
        from android_re_mcp_native.server import build_server
    except ImportError as e:
        print(f"android_re_mcp_native: import failed: {e}", file=sys.stderr)
        return 1
    mcp = build_server()
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
