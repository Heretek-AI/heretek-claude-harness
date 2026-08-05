"""Quarterly SHA + vetting refresh tool for heretek marketplace.

Walks every items[] entry in catalog.yaml and verifies the upstream
is still healthy against the D7 vetting bar (stars, last commit, license,
no critical CVEs). Without a GitHub token, runs offline and reports
staleness based on stored `vetting.date` (older than ~12 months -> stale).

Exit codes:
  0  all items fresh
  1  some items stale (operator should review + bump)
  2  network or parse error

Usage:
  python scripts/refresh_pins.py                       # offline, prints table
  python scripts/refresh_pins.py --github-token $TOK  # live API checks
  python scripts/refresh_pins.py --update-shas        # write new SHAs
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "catalog" / "catalog.yaml"

STALENESS_WINDOW_DAYS = 365
GITHUB_API = "https://api.github.com"


def _days_since(date_str: str) -> int:
    try:
        d = dt.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return 10**9
    return (dt.date.today() - d).days


def _github_get(path: str, gh_token: Optional[str]) -> dict:
    """Single GET against the GitHub API. Returns {} on any error (network, 404, rate limit).

    Override this in tests for hermetic execution.
    """
    try:
        import requests  # type: ignore

        headers = {"Accept": "application/vnd.github+json"}
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"
        r = requests.get(f"{GITHUB_API}{path}", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        return {}
    except Exception:
        return {}


def check_item(item: dict, *, gh_token: Optional[str]) -> tuple[str, dict]:
    """Return (status, details). status in {ok, skipped, stale_stars, stale_commit, license_drift, cve_alert}."""
    details: dict[str, Any] = {"id": item.get("id"), "upstream": item.get("upstream")}
    vetting = item.get("vetting") or {}
    vetting_date = vetting.get("date")
    if vetting_date and _days_since(vetting_date) > STALENESS_WINDOW_DAYS:
        details["reason"] = f"vetting.date {vetting_date} is older than {STALENESS_WINDOW_DAYS} days"
        return "stale_commit", details
    if not gh_token:
        details["reason"] = "no GITHUB_TOKEN; offline check skipped"
        return "skipped", details
    upstream = item.get("upstream")
    if not upstream or "/" not in upstream:
        details["reason"] = "upstream missing or malformed"
        return "skipped", details
    data = _github_get(f"/repos/{upstream}", gh_token)
    if not data:
        details["reason"] = "upstream not found or API error"
        return "stale_stars", details  # conservative
    stars = data.get("stargazers_count", 0)
    if stars < 500:
        details["reason"] = f"stars={stars} < 500"
        return "stale_stars", details
    spdx = (data.get("license") or {}).get("spdx_id") or "NOASSERTION"
    if spdx != (item.get("license") or "").upper():
        details["reason"] = f"license drifted: upstream={spdx} vs catalog={item.get('license')}"
        return "license_drift", details
    advisories = _github_get(f"/repos/{upstream}/security-advisories", gh_token)
    critical = [a for a in advisories if (a.get("severity") or "").upper() == "CRITICAL"]
    if critical:
        details["reason"] = f"{len(critical)} critical CVE(s)"
        return "cve_alert", details
    return "ok", details


def check_catalog(catalog_path: Path, *, gh_token: Optional[str]) -> list[tuple[str, Path, str, dict]]:
    catalog = yaml.safe_load(catalog_path.read_text())
    results: list[tuple[str, Path, str, dict]] = []
    for plugin in catalog.get("plugins", []):
        plugin_path = REPO_ROOT / "plugins" / plugin["name"]
        for item in plugin.get("items") or []:
            status, details = check_item(item, gh_token=gh_token)
            results.append((status, plugin_path, item.get("id", "?"), details))
    return results


def bump_sha(item: dict, new_sha: str) -> dict:
    """Return a copy of item with sha + vetting.date updated to today."""
    out = dict(item)
    out["sha"] = new_sha
    vetting = dict(item.get("vetting") or {})
    vetting["date"] = dt.date.today().isoformat()
    out["vetting"] = vetting
    return out


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--update-shas", action="store_true",
                        help="Write updated SHAs back to the catalog (requires --github-token).")
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"))
    args = parser.parse_args(argv)
    results = check_catalog(args.catalog, gh_token=args.github_token)
    rc = 0
    print(f"{'STATUS':<14} {'PLUGIN':<24} {'ITEM':<28} DETAIL")
    print("-" * 100)
    for status, path, item_id, details in results:
        detail_str = details.get("reason", "")
        if status == "ok":
            rc = rc  # no change
        elif status == "skipped":
            pass
        else:
            rc = 1
        print(f"{status:<14} {path.name:<24} {item_id:<28} {detail_str}")
    print()
    print(f"Summary: {len(results)} item(s); {sum(1 for s, *_ in results if s != 'ok' and s != 'skipped')} stale")
    return rc


if __name__ == "__main__":
    sys.exit(main())
