#!/usr/bin/env bash
# Layer 3 installer for the heretek hooks plugin.
# Installs the pre-commit framework hooks (pre-commit + pre-push) into the
# current git repository. Idempotent: re-running is safe.
set -euo pipefail

# 1. Locate the repo root (parent of plugins/hooks where this script lives).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "$PLUGIN_ROOT/../.." && pwd)}"
PRECOMMIT_CONFIG="$PLUGIN_ROOT/.pre-commit-config.yaml"

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
# Use `git rev-parse --git-common-dir` because `pre-commit install` writes
# hooks to the common git dir (shared with the main checkout when running
# in a worktree). Hardcoding `$REPO_ROOT/.git/hooks/pre-commit` misses the
# hook when `$REPO_ROOT` is a worktree (where `.git/` is a file).
HOOK_PATH="$(git -C "$REPO_ROOT" rev-parse --git-common-dir)/hooks/pre-commit"
if [[ -f "$HOOK_PATH" ]] && grep -q "pre-commit" "$HOOK_PATH" 2>/dev/null; then
    echo "install_git_hooks: pre-commit hooks already installed; skipping" >&2
    echo "install_git_hooks: OK (pre-commit + pre-push hooks already installed in $REPO_ROOT)"
    exit 0
fi

# 6. Run pre-commit install (sets up both pre-commit and pre-push because of
#    default_install_hook_types in .pre-commit-config.yaml).
python3 -m pre_commit install --install-hooks --overwrite --config "$PRECOMMIT_CONFIG"

echo "install_git_hooks: OK (pre-commit + pre-push hooks installed in $REPO_ROOT)"