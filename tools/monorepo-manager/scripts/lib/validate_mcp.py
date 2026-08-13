"""Validator for the .mcp.json contract.

Rules enforced beyond the JSON Schema:
- The `name` key (the mcpServers dict key) matches `^[a-z][a-z0-9-]{2,32}$`.
- An env value that looks like a token (length >= 20, alphanumeric/underscore)
  is rejected as a plaintext secret.
"""

from __future__ import annotations

import json
import pathlib
import re

import jsonschema

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{2,32}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]{20,}$")


def _looks_like_token(value: str) -> bool:
    return bool(_TOKEN_RE.match(value))


def validate_mcp(path: str) -> list[str]:
    p = pathlib.Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    schema = json.loads(
        (pathlib.Path(__file__).parents[2] / "schemas" / "mcp-json.schema.json").read_text()
    )
    violations: list[str] = []

    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(raw), key=lambda e: e.path):
        violations.append(f"{'/'.join(map(str, err.path)) or '<root>'}: {err.message}")

    servers = raw.get("mcpServers", {})
    for name, server in servers.items():
        if not _NAME_RE.match(name):
            violations.append(f"name '{name}': must match {_NAME_RE.pattern}")
        env = server.get("env") or {}
        for k, v in env.items():
            if isinstance(v, str) and _looks_like_token(v):
                violations.append(f"env '{k}': plaintext secret not allowed in .mcp.json")

    return violations
