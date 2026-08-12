"""Generate .claude-plugin/marketplace.json from catalog/catalog.yaml."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "catalog" / "catalog.yaml"
DEFAULT_OUTPUT = REPO_ROOT / ".claude-plugin" / "marketplace.json"

_INTERNAL_FIELDS = {"components", "items"}


def _normalize_source(
    source: dict[str, Any] | str, plugin_root: str | None = None
) -> dict[str, Any] | str:
    if isinstance(source, str):
        return source
    src_type = cast(str, source.get("type"))
    if src_type == "relative":
        path = cast(str, source["path"])
        root = (plugin_root or "./plugins").lstrip("./").rstrip("/")
        return f"./{root}/{path}"
    out: dict[str, Any] = {"source": src_type}
    for key in ("repo", "url", "path", "ref", "sha", "package", "headers"):
        if key in source:
            out[key] = source[key]
    return out


def _plugin_entry(catalog_plugin: dict[str, Any], plugin_root: str | None = None) -> dict[str, Any]:
    filtered = {k: v for k, v in catalog_plugin.items() if k not in _INTERNAL_FIELDS}
    name_val = cast(str, filtered["name"])
    source_val = cast(dict[str, Any] | str, filtered["source"])
    out: dict[str, Any] = {
        "name": name_val,
        "source": _normalize_source(source_val, plugin_root=plugin_root),
    }
    for optional in ("category", "tags", "description", "author"):
        if optional in filtered:
            out[optional] = filtered[optional]
    if "version" in filtered:
        out["version"] = filtered["version"]
    return out


def _safe_load_catalog(catalog_path: Path) -> dict[str, Any]:
    loaded: Any = yaml.safe_load(catalog_path.resolve().read_text())
    if not isinstance(loaded, dict):
        raise ValueError(f"{catalog_path}: root content is not a dict")
    return cast(dict[str, Any], loaded)


def generate(catalog_path: Path, output_path: Path) -> dict[str, Any]:
    catalog = _safe_load_catalog(catalog_path)
    if "marketplace" not in catalog or not isinstance(catalog["marketplace"], dict):
        raise ValueError(f"{catalog_path}: top-level 'marketplace' key missing or not a mapping")
    plugins_raw = catalog.get("plugins")
    if not isinstance(plugins_raw, list):
        raise ValueError(f"{catalog_path}: 'plugins' must be a list")

    marketplace_section = cast(dict[str, Any], catalog["marketplace"])
    plugin_root = cast(dict[str, Any], marketplace_section.get("metadata", {})).get("pluginRoot")
    plugins: list[dict[str, Any]] = [
        _plugin_entry(cast(dict[str, Any], p), plugin_root=cast(str | None, plugin_root))
        for p in cast(list[Any], plugins_raw)
    ]

    generated: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **marketplace_section,
        "plugins": plugins,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = output_path.resolve()
    tmp = resolved.with_suffix(resolved.suffix + ".tmp")
    tmp.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")
    tmp.replace(resolved)
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
        yaml.YAMLError,
    ) as exc:
        print(f"generate: error: {exc}", file=sys.stderr)
        return 1
    print(f"generate: wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
