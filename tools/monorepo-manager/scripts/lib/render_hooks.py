"""Renderer for `.claude/hooks/*` shell scripts."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

_HOOKS = [
    ".claude/hooks/PreToolUse/deny-destructive.sh",
    ".claude/hooks/PostToolUse/run-pre-commit.sh",
    ".claude/hooks/Stop/verify-lint.sh",
]


def render_hooks(stack: str) -> dict[str, str]:
    if stack not in {"python", "node"}:
        raise ValueError(f"unknown stack '{stack}'")
    files: dict[str, str] = {}
    for rel in _HOOKS:
        text = (Path(_TEMPLATE_DIR) / rel).read_text(encoding="utf-8")
        if stack == "node" and rel.endswith("Stop/verify-lint.sh"):
            text = text.replace("ruff check .", "npx --no-install eslint .")
            text = text.replace(
                "[[ -f pyproject.toml ]] && ruff check . || true",
                "[[ -f package.json ]] && npx --no-install eslint . || true",
            )
        files[rel] = text
    return files
