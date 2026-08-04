---
description: Install Layer 3 git pre-commit + pre-push hooks (pre-commit framework).
---

Installs the heretek pre-commit framework hooks into the current git repository. Requires Python 3.8+ and `pip install pre-commit`.

The installer:
1. Verifies the cwd is inside a git repository.
2. Verifies `python3` and `pre-commit` are on PATH.
3. Runs `pre-commit install --install-hooks --overwrite` with the heretek config.
4. Sets up both `pre-commit` and `pre-push` hook types.

Idempotent: re-running with hooks already installed overwrites cleanly.

Usage: `/hooks:install-git-hooks`.
