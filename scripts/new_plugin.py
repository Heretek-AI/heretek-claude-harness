"""Scaffold a new first-party plugin directory from a template.

Run as CLI:
    python scripts/new_plugin.py [--repo-root PATH] <name> [<description>]

Creates plugins/<name>/.claude-plugin/plugin.json + plugins/<name>/README.md
from scripts/templates/plugin/{plugin.json,README.md}. Fails if the plugin
directory already exists. Plugin name must match the catalog convention:
lowercase, digits, hyphens; first character alphanumeric.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _display_name(slug: str) -> str:
    """Convert 'rust-analyzer' → 'Rust Analyzer' for the displayName field."""
    return " ".join(part.capitalize() for part in slug.split("-"))


def scaffold(repo_root: Path, name: str, description: str = "") -> Path:
    """Create plugins/<name>/ from templates. Returns the created dir."""
    if not PLUGIN_NAME_RE.match(name):
        raise ValueError(f"invalid plugin name {name!r}: must match {PLUGIN_NAME_RE.pattern}")
    plugin_dir = repo_root / "plugins" / name
    if plugin_dir.exists():
        raise FileExistsError(f"plugin directory already exists: {plugin_dir}")

    template_dir = Path(__file__).resolve().parent / "templates" / "plugin"
    plugin_json_tmpl = (template_dir / "plugin.json").read_text()
    readme_tmpl = (template_dir / "README.md").read_text()

    display = _display_name(name)
    plugin_json = (
        plugin_json_tmpl.replace("<name>", name)
        .replace("<displayName>", display)
        .replace("<description>", description)
    )
    readme = (
        readme_tmpl.replace("<name>", name)
        .replace("<displayName>", display)
        .replace("<description>", description)
    )

    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(plugin_json)
    (plugin_dir / "README.md").write_text(readme)

    # Validate the generated plugin.json against the schema before declaring success.
    import validate as _validate  # local import to avoid circular at module load

    schemas_dir = _validate.DEFAULT_SCHEMAS_DIR
    schema = _validate._load_schema("plugin", schemas_dir)
    instance = json.loads(plugin_json)
    errors = [
        f"plugin.json: {e.message}"
        for e in __import__("jsonschema").Draft202012Validator(schema).iter_errors(instance)
    ]
    if errors:
        # Roll back to avoid leaving a broken plugin on disk.
        import shutil

        shutil.rmtree(plugin_dir)
        raise ValueError(f"generated plugin.json failed schema validation: {errors}")

    return plugin_dir


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("name", help="Plugin slug (lowercase, hyphens, digits).")
    parser.add_argument("description", nargs="?", default="")
    args = parser.parse_args(argv)
    try:
        plugin_dir = scaffold(args.repo_root, args.name, args.description)
    except (FileExistsError, ValueError) as exc:
        print(f"new-plugin: error: {exc}", file=sys.stderr)
        return 1
    print(f"new-plugin: scaffolded {plugin_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
