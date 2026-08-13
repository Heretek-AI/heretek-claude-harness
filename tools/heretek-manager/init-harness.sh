#!/usr/bin/env bash
# Materialise the Heretek harness into a target directory.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

cd "$ROOT"
exec python -m scripts.lib.cli "$@"
