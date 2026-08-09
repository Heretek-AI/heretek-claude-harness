"""Catalog updater. Uses ruamel.yaml to preserve comments + key order
when bumping an item's SHA / vetting.date in catalog.yaml.

CLI:
    python scripts/catalog_updater.py --plugin rust --item rust-analyzer \\
            --sha <40-char> --vetting-date 2026-08-05
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from ruamel.yaml import YAML


class ItemNotFound(Exception):
    pass


def _make_yaml() -> YAML:
    """Ruamel YAML configured to preserve the existing catalog formatting."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _find_item(data: dict, plugin_name: str, item_id: str) -> dict | None:
    """Locate the item dict under plugins[].name == plugin_name."""
    for plugin in data.get("plugins", []):
        if plugin.get("name") != plugin_name:
            continue
        for item in plugin.get("items") or []:
            if item.get("id") == item_id:
                return item
    return None


def _apply_item_updates(
    item: dict, new_sha: str, vetting_date: str, cve_scan: str | None
) -> None:
    """In-place update of sha + vetting.date (+ optional cve_scan)."""
    item["sha"] = new_sha
    vetting = item.setdefault("vetting", {})
    # Parse to datetime.date so ruamel.yaml round-trips as an unquoted YAML
    # date scalar (matches the existing formatting in catalog.yaml).
    vetting["date"] = date.fromisoformat(vetting_date)
    if cve_scan is not None:
        vetting["cve_scan"] = date.fromisoformat(cve_scan)


def bump_item_sha(
    catalog_path: Path,
    plugin_name: str,
    item_id: str,
    new_sha: str,
    vetting_date: str,
    cve_scan: str | None = None,
) -> None:
    """Atomically update one item's sha + vetting.date (and cve_scan)."""
    if len(new_sha) != 40:
        raise ValueError(f"new_sha must be 40 chars, got {len(new_sha)}")

    yaml = _make_yaml()
    data = yaml.load(catalog_path.read_text())
    item = _find_item(data, plugin_name, item_id)
    if item is None:
        raise ItemNotFound(f"{plugin_name}/{item_id}")
    _apply_item_updates(item, new_sha, vetting_date, cve_scan)

    tmp = catalog_path.with_suffix(catalog_path.suffix + ".tmp")
    with tmp.open("w") as f:
        yaml.dump(data, f)
    tmp.replace(catalog_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("catalog/catalog.yaml"))
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--sha", required=True, help="40-char commit SHA")
    parser.add_argument("--vetting-date", required=True)
    parser.add_argument("--cve-scan")
    args = parser.parse_args(argv)

    try:
        bump_item_sha(
            args.catalog,
            args.plugin,
            args.item,
            args.sha,
            args.vetting_date,
            args.cve_scan,
        )
    except ItemNotFound as e:
        print(f"item not found: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
