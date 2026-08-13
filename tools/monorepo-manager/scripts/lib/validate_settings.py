"""Validator for .claude/settings.json.

Beyond the JSON Schema, the contract requires that `permissions.deny`
includes destructive patterns: `rm -rf`, `git push --force`, and
`git reset --hard` against protected branches.
"""

from __future__ import annotations

import json
import pathlib

import jsonschema

_REQUIRED_DENY_PATTERNS = ["rm -rf", "git push --force", "git reset --hard"]


def validate_settings(path: str) -> list[str]:
    p = pathlib.Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    schema = json.loads(
        (pathlib.Path(__file__).parents[2] / "schemas" / "settings-json.schema.json").read_text()
    )
    violations: list[str] = []

    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(raw), key=lambda e: e.path):
        violations.append(f"{'/'.join(map(str, err.path)) or '<root>'}: {err.message}")

    allow = (raw.get("permissions") or {}).get("allow") or []
    if not allow:
        violations.append("permissions.allow must be a non-empty explicit allowlist")

    deny = (raw.get("permissions") or {}).get("deny") or []
    deny_text = "\n".join(deny)
    for pat in _REQUIRED_DENY_PATTERNS:
        if pat not in deny_text:
            violations.append(f"permissions.deny must contain destructive pattern '{pat}'")

    return violations
