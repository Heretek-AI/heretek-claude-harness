#!/usr/bin/env bash
# Smoke test for the Layer-1 fast-gate dispatcher.
# Creates a file with a known lint error and asserts the dispatcher exits non-zero.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR="$(mktemp -d)"
trap "rm -rf $TMPDIR" EXIT

BAD_FILE="$TMPDIR/bad.py"
cat > "$BAD_FILE" <<'EOF'
import os
def f( ):pass
EOF

PAYLOAD=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"%s","old_string":"","new_string":"import os\\ndef f( ):pass\\n"}}' "$BAD_FILE")

# Run the dispatcher via module path.
set +e
python -m plugins.hooks.scripts.fast_gate <<<"$PAYLOAD" >/dev/null 2>&1
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
    # If ruff isn't installed, the dispatcher fails open with exit 0.
    # That's acceptable but skip reporting.
    if ! command -v ruff >/dev/null 2>&1; then
        echo "fast_gate_smoke: SKIPPED (ruff not installed)"
        exit 0
    fi
    echo "fast_gate_smoke: FAIL (expected non-zero exit on lint error)"
    exit 1
fi

if [ "$EXIT_CODE" -eq 2 ]; then
    echo "fast_gate_smoke: OK (dispatcher blocked bad file with exit 2)"
    exit 0
fi

echo "fast_gate_smoke: FAIL (unexpected exit code: $EXIT_CODE)"
exit 1
