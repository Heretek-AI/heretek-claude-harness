---
name: ruff-check
description: Run `ruff check` on the current Python project and surface lint findings. Use after modifying Python source.
---

Run `ruff check --output-format=concise --no-cache` from the project root. Surface the first 50 lines of output. If findings are present, list each with file:line:col and the rule code. Do not auto-fix; that's a separate `ruff format` workflow.

For a fast pass on changed files only, pass paths explicitly: `ruff check --output-format=concise path/to/file.py`.
