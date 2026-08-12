#!/usr/bin/env bash
# Heretek Pre-commit Installer Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TARGET_DIR="${1:-$(pwd)}"

if [ ! -d "$TARGET_DIR/.git" ]; then
    echo "error: $TARGET_DIR is not a git repository" >&2
    exit 1
fi

if ! command -v pre-commit &> /dev/null; then
    echo "error: pre-commit CLI is not installed. Install with 'pip install pre-commit' or 'brew install pre-commit'." >&2
    exit 1
fi

CONFIG_SRC="$PLUGIN_ROOT/.pre-commit-config.yaml"
CONFIG_DEST="$TARGET_DIR/.pre-commit-config.yaml"

if [ ! -f "$CONFIG_DEST" ]; then
    cp "$CONFIG_SRC" "$CONFIG_DEST"
    echo "Installed .pre-commit-config.yaml to $TARGET_DIR"
fi

cd "$TARGET_DIR"
pre-commit install --install-hooks
echo "Pre-commit hooks successfully installed in $TARGET_DIR"
