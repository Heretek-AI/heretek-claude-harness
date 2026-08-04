"""Generate .claude-plugin/marketplace.json from catalog/catalog.yaml.

catalog.yaml is the source of truth (spec §5). The generator maps catalog
plugin entries to the marketplace.json plugin entry shape:

- relative source `{type: relative, path: rust}` → bare string `"rust"`
  (resolved against metadata.pluginRoot by Claude Code)
- git-subdir / github / url / npm source objects → pass through unchanged
- catalog-only fields (components, items) → stripped from the output
- first-party plugin entries have no `version` field (D11 SHA-ride)

Run as CLI:
    python scripts/generate_marketplace.py [--catalog PATH] [--output PATH]

Exit code: 0 on success, 1 on any error. The CLI catches the full set
of expected runtime errors (ValueError, KeyError, TypeError, OSError,
FileNotFoundError, yaml.YAMLError) so the user sees a clear stderr
message instead of a Python traceback. Idempotent: re-running on the
same catalog produces byte-identical output (verified by Task 11).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "catalog" / "catalog.yaml"
DEFAULT_OUTPUT = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# catalog.yaml-only fields that must NOT appear in marketplace.json.
_INTERNAL_FIELDS = {"components", "items"}


def _normalize_source(source: dict | str) -> dict | str:
    """Translate the catalog's source shape into the marketplace.json shape."""
    if isinstance(source, str):
        return source
    src_type = source.get("type")
    if src_type == "relative":
        return source["path"]
    # 3rd-party object: translate to the Claude Code marketplace shape
    # (which uses `source:` discriminator, not `type:`).
    out = {"source": src_type}
    for key in ("repo", "url", "path", "ref", "sha", "package", "headers"):
        if key in source:
            out[key] = source[key]
    return out


def _plugin_entry(catalog_plugin: dict) -> dict:
    """Project a catalog plugin entry into the marketplace.json entry shape."""
    # Strip catalog-only fields first. _INTERNAL_FIELDS is the canonical
    # list of fields that must NEVER appear in marketplace.json.
    filtered = {k: v for k, v in catalog_plugin.items() if k not in _INTERNAL_FIELDS}
    out: dict = {
        "name": filtered["name"],
        "source": _normalize_source(filtered["source"]),
    }
    for optional in ("category", "tags", "description", "author"):
        if optional in filtered:
            out[optional] = filtered[optional]
    # Note: 'version' is intentionally NEVER added — first-party plugins
    # use SHA-ride (D11). 3rd-party entries get their version (if any)
    # from the catalog entry directly.
    if "version" in filtered:
        out["version"] = filtered["version"]
    return out


def generate(catalog_path: Path, output_path: Path) -> dict:
    """Read catalog.yaml, write marketplace.json; return the generated dict."""
    catalog = yaml.safe_load(catalog_path.read_text())
    if not isinstance(catalog, dict) or "marketplace" not in catalog:
        raise ValueError(
            f"{catalog_path}: top-level 'marketplace' key missing or not a mapping"
        )
    if not isinstance(catalog.get("plugins"), list):
        raise ValueError(f"{catalog_path}: 'plugins' must be a list")

    marketplace_section = catalog["marketplace"]
    plugins = [_plugin_entry(p) for p in catalog["plugins"]]

    generated = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **marketplace_section,
        "plugins": plugins,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")
    return generated


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        generate(args.catalog, args.output)
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        FileNotFoundError,
        yaml.YAMLError,
    ) as exc:
        print(f"generate: error: {exc}", file=sys.stderr)
        return 1
    print(f"generate: wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
