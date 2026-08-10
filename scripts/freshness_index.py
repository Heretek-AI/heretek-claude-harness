"""Nightly freshness index — pulls latest stable versions from public registries.

Implements #36 from the 2026-08-06 freshness-enforced-coding roadmap spec.
Writes one YAML file per library to catalog/freshness/<lib>.yaml.

Usage:
    python -m scripts.freshness_index --lib pyyaml
    python -m scripts.freshness_index --all
    python -m scripts.freshness_index --lib pyyaml --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"

# Initial scope — heretek's own runtime deps. Expand in follow-up.
DEFAULT_LIBS = [
    ("pyyaml", "pypi"),
    ("jsonschema", "pypi"),
    ("requests", "pypi"),
    ("ruamel.yaml", "pypi"),
    ("pytest", "pypi"),
    ("ruff", "pypi"),
]


def _latest_pypi(lib: str) -> dict:
    """Query PyPI for latest stable version + release date of `lib`."""
    import requests

    url = f"https://pypi.org/pypi/{lib}/json"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    info = resp.json()["info"]
    version = info["version"]
    # Latest release date: parse from releases dict
    releases = resp.json()["releases"]
    release_files = releases.get(version, [])
    upload_time = release_files[0]["upload_time"] if release_files else None
    return {
        "latest_version": version,
        "latest_release_date": upload_time,
        "eol_date": None,  # PyPI does not publish EOL dates
        "cve_count_critical": 0,  # OSV.dev integration is a follow-up; #49 covers cumulative CVE tracking
    }


def fetch_freshness(lib: str, registry: str = "pypi") -> dict:
    """Fetch freshness data for a single library."""
    if registry == "pypi":
        return _latest_pypi(lib)
    raise NotImplementedError(f"Registry {registry!r} not yet supported")


def write_cache(lib: str, data: dict, dry_run: bool = False) -> Path:
    """Write freshness data to catalog/freshness/<lib>.yaml."""
    safe_name = lib.replace(".", "-").lower()
    out = CACHE_DIR / f"{safe_name}.yaml"
    if not dry_run:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml.safe_dump(data, sort_keys=False))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh freshness index cache")
    parser.add_argument("--lib", help="Refresh a single library")
    parser.add_argument("--all", action="store_true", help="Refresh all default libraries")
    parser.add_argument("--dry-run", action="store_true", help="Do not write cache files")
    args = parser.parse_args(argv)

    if not args.lib and not args.all:
        parser.error("specify --lib <name> or --all")

    targets = []
    if args.lib:
        targets.append((args.lib, "pypi"))
    if args.all:
        targets.extend(DEFAULT_LIBS)

    failures = []
    for lib, registry in targets:
        try:
            data = fetch_freshness(lib, registry)
            write_cache(lib, data, dry_run=args.dry_run)
            print(f"OK   {lib}: {data['latest_version']}")
        except Exception as exc:
            failures.append((lib, str(exc)))
            print(f"FAIL {lib}: {exc}", file=sys.stderr)

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
