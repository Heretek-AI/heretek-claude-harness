#!/usr/bin/env bash
# D15 install path for the heretek hooks plugin.
# Renders freshness tokens (#46) so the installer can pipe them into the
# harness's startup prompt config. Idempotent: re-running is safe.
set -euo pipefail

# Locate the repo root (parent of plugins/hooks where this script lives).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$REPO_ROOT"

# Freshness tokens (#46) — auto-injected at session start so the agent
# has a snapshot of "what's current" and doesn't fall back on training-time
# memory. This block is meant to be appended to the harness's startup prompt.
echo ""
echo "## Freshness tokens (auto-injected at session start):"
python -m scripts.freshness_tokens || echo "(failed to render tokens — run manually: python -m scripts.freshness_tokens)"

echo ""
echo "install: OK (freshness tokens emitted above)"
