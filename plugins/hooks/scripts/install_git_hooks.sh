#!/usr/bin/env bash
# Layer 3 installer for the heretek hooks plugin.
# Installs the pre-commit framework hooks (pre-commit + pre-push) into the
# current git repository. Idempotent: re-running is safe.
set -euo pipefail

# 1. Locate the repo root (searching upwards from script dir if REPO_ROOT unset).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${REPO_ROOT:-}" ]]; then
    SEARCH_DIR="$SCRIPT_DIR"
    while [[ "$SEARCH_DIR" != "/" ]]; do
        if [[ -d "$SEARCH_DIR/.git" || -f "$SEARCH_DIR/.git" ]]; then
            REPO_ROOT="$SEARCH_DIR"
            break
        fi
        SEARCH_DIR="$(dirname "$SEARCH_DIR")"
    done
    REPO_ROOT="${REPO_ROOT:-$(pwd)}"
fi

PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PRECOMMIT_CONFIG="${REPO_ROOT}/.pre-commit-config.yaml"
if [[ ! -f "$PRECOMMIT_CONFIG" ]]; then
    PRECOMMIT_CONFIG="$PLUGIN_ROOT/.pre-commit-config.yaml"
fi

# 2. Sanity: must be inside a git repository.
if ! git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    echo "install_git_hooks: $REPO_ROOT is not a git repository; aborting" >&2
    exit 1
fi

# 3. Sanity: pre-commit framework is Python-based; require Python.
if ! command -v python3 >/dev/null 2>&1; then
    echo "install_git_hooks: python3 not found on PATH; install Python ≥ 3.8 first" >&2
    exit 1
fi

# 4. Sanity: pre-commit framework must be installed.
if ! python3 -m pre_commit --version >/dev/null 2>&1; then
    echo "install_git_hooks: pre-commit not installed; install with: pip install pre-commit" >&2
    exit 1
fi

# 5. Idempotency check: short-circuit if hooks are already installed (#97).
HOOK_PATH="$(git -C "$REPO_ROOT" rev-parse --git-common-dir)/hooks/pre-commit"
if [[ -f "$HOOK_PATH" ]] && grep -q "pre-commit" "$HOOK_PATH" 2>/dev/null; then
    echo "install_git_hooks: pre-commit hooks already installed; skipping" >&2
    echo "install_git_hooks: OK (pre-commit + pre-push hooks already installed in $REPO_ROOT)"
    exit 0
fi

# 6. Run pre-commit install
if [[ -f "$PRECOMMIT_CONFIG" ]]; then
    python3 -m pre_commit install --install-hooks --overwrite --config "$PRECOMMIT_CONFIG"
else
    python3 -m pre_commit install --install-hooks --overwrite
fi

echo "install_git_hooks: OK (pre-commit + pre-push hooks installed in $REPO_ROOT)"
