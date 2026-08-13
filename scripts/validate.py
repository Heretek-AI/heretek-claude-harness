"""Validate the marketplace and every plugin manifest against JSON Schemas.

Performs strict JSON Schema validation (Draft 2020-12) against `marketplace.json`,
`plugin.json`, `hooks.json`, `.mcp.json`, and `.lsp.json` across all plugins.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMAS_DIR = REPO_ROOT / "tests" / "schemas"

SCHEMAS = {
    "marketplace": "marketplace.schema.json",
    "plugin": "plugin.schema.json",
    "hooks": "hooks.schema.json",
    "mcp": "mcp.schema.json",
    "lsp": "lsp.schema.json",
}


def _load_schema(name: str, schemas_dir: Path) -> dict[str, Any]:
    """Load JSON schema file by key name from schemas_dir.

    Args:
        name: Schema key name (e.g. 'plugin', 'marketplace').
        schemas_dir: Directory containing JSON Schema files.

    Returns:
        Loaded JSON schema dict.

    Raises:
        FileNotFoundError: If schema file is missing.
        ValueError: If schema file root is not a dictionary.
    """
    path = schemas_dir / SCHEMAS[name]
    if not path.is_file():
        raise FileNotFoundError(f"schema not found: {path}")
    loaded: Any = json.loads(path.read_text())
    if not isinstance(loaded, dict):
        raise ValueError(f"schema root in {path} must be a dict")
    return cast(dict[str, Any], loaded)


def _validate_one(schema: dict[str, Any], instance: Any, label: str) -> list[str]:
    """Validate single JSON instance against schema.

    Args:
        schema: Loaded JSON schema dict.
        instance: Parsed JSON data to validate.
        label: Human-readable file label for error reporting.

    Returns:
        List of formatted validation error strings (empty list = clean).
    """
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{label}: {e.message}" for e in validator.iter_errors(instance)]  # type: ignore[no-any-expr]


def _validate_plugin_manifests(repo_root: Path, schemas: dict[str, dict[str, Any]]) -> list[str]:
    """Walk plugins/<name>/.claude-plugin/ and validate plugin.json + sibling manifests.

    Args:
        repo_root: Path to repository root directory.
        schemas: Map of schema name -> loaded schema dict.

    Returns:
        List of validation error strings across all plugin packages.
    """
    errors: list[str] = []
    plugins_root = repo_root / "plugins"
    if not plugins_root.is_dir():
        return errors
    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        manifest_dir = plugin_dir / ".claude-plugin"
        if not manifest_dir.is_dir():
            continue
        for kind, schema in (
            ("plugin.json", schemas["plugin"]),
            ("hooks.json", schemas["hooks"]),
            (".mcp.json", schemas["mcp"]),
            (".lsp.json", schemas["lsp"]),
        ):
            path = manifest_dir / kind
            if not path.is_file():
                continue
            label = f"plugins/{plugin_dir.name}/.claude-plugin/{kind}"
            try:
                instance: object = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                errors.append(f"{label}: invalid JSON ({exc.msg})")
                continue
            errors.extend(_validate_one(schema, instance, label))
    return errors


def validate_all(repo_root: Path, schemas_dir: Path | None = None) -> list[str]:
    """Return a list of schema-failure messages; empty list = clean validation pass.

    Args:
        repo_root: Path to repository root directory.
        schemas_dir: Optional custom schema directory path.

    Returns:
        List of error strings. Empty list indicates 100% schema compliance.
    """
    schemas_dir = schemas_dir or DEFAULT_SCHEMAS_DIR
    try:
        schemas = {name: _load_schema(name, schemas_dir) for name in SCHEMAS}
    except FileNotFoundError as exc:
        return [str(exc)]

    errors: list[str] = []

    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.is_file():
        errors.append(f"missing marketplace manifest: {marketplace_path}")
    else:
        try:
            instance: object = json.loads(marketplace_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f".claude-plugin/marketplace.json: invalid JSON ({exc.msg})")
        else:
            errors.extend(
                _validate_one(schemas["marketplace"], instance, ".claude-plugin/marketplace.json")
            )

    errors.extend(_validate_plugin_manifests(repo_root, schemas))
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    """CLI execution entrypoint for schema validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--schemas-dir", type=Path, default=DEFAULT_SCHEMAS_DIR)
    args = parser.parse_args(argv)

    errors = validate_all(args.repo_root, schemas_dir=args.schemas_dir)
    if not errors:
        print("validate: OK (all manifests conform to JSON Schemas)")
        return 0
    print(f"validate: {len(errors)} error(s)", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
