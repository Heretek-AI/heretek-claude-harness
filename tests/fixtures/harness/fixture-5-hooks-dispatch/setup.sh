#!/usr/bin/env bash
set -euo pipefail
mkdir -p plugins/hooks/scripts
cat > plugins/hooks/scripts/dispatch.py <<'EOF'
"""Minimal dispatcher for the fixture — handles only SessionStart."""
from __future__ import annotations

import sys


def main() -> int:
    for line in sys.stdin:
        event = line.strip()
        if event == "SessionStart":
            print(f"event: {event}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
EOF
git init -q -b main
git add .
git -c user.email=t@t -c user.name=t commit -q -m init
