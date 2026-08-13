"""Entry point for ``python -m android_re_mcp_dynamic``."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from android_re_mcp_dynamic.server import build_server
    except ImportError as e:
        print(f"android_re_mcp_dynamic: import failed: {e}", file=sys.stderr)
        return 1
    mcp = build_server()
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
