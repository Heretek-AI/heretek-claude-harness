#!/usr/bin/env bash
# Bootstrap a local dev environment for heretek-claude-harness.
#
# Creates .venv/ with the pinned deps from pyproject.toml plus httpx
# (required by the langsmith pytest plugin entry point).
#
# Usage:
#   ./scripts/dev-setup.sh                 # uses python3 + .venv/
#   PYTHON=python3.12 ./scripts/dev-setup.sh
#   VENV=.venv-3.14 ./scripts/dev-setup.sh
#
# After setup: source .venv/bin/activate && pytest -q

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"

# Pre-flight: Python available + version
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "error: $PYTHON not found on PATH" >&2
  exit 1
fi
PY_VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "error: Python 3.10+ required (found $PY_VERSION)" >&2
  exit 1
fi

# Create venv if missing
if [ ! -d "$VENV" ]; then
  echo "==> creating venv at $VENV (Python $PY_VERSION)"
  "$PYTHON" -m venv "$VENV"
else
  echo "==> reusing venv at $VENV"
fi

# Install pinned deps from pyproject.toml + ruamel.yaml (refresh_pins.py uses it)
# + httpx (langsmith pytest plugin's transitive dep — was missing on a fresh install)
echo "==> installing pinned deps"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet \
  "PyYAML==6.0.3" \
  "jsonschema==4.26.0" \
  "requests==2.34.2" \
  "pytest==9.1.1" \
  "ruamel.yaml" \
  "httpx"

# Verify: collection must succeed (no ModuleNotFoundError on scripts/ imports)
echo "==> verifying (pytest --collect-only)"
if ! "$VENV/bin/pytest" --collect-only -q >/dev/null 2>&1; then
  echo "error: pytest --collect-only failed; check missing deps above" >&2
  exit 1
fi

echo "==> done. activate with: source $VENV/bin/activate"
