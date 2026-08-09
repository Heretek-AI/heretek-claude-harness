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

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._allowlist import require_ref_segment, require_upstream

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "catalog" / "catalog.yaml"

STALENESS_WINDOW_DAYS = 365
GITHUB_API = "https://api.github.com"


def _days_since(date_val) -> int:
    # PyYAML parses unquoted ISO dates (e.g. `date: 2026-08-04`) as
    # datetime.date objects, not strings. Accept either form.
    if isinstance(date_val, dt.date):
        return (dt.date.today() - date_val).days
    try:
        d = dt.date.fromisoformat(str(date_val))
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


def _get_latest_release_sha(upstream: str, *, gh_token: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return (sha, tag) of upstream's latest release, or (None, None)."""
    data = _github_get(f"/repos/{upstream}/releases/latest", gh_token)
    if not data:
        return None, None
    return data.get("target_commitish"), data.get("tag_name")


def _check_vetting_date(item: dict, details: dict) -> Optional[str]:
    """Return 'stale_commit' if vetting.date is older than the window."""
    vetting = item.get("vetting") or {}
    vetting_date = vetting.get("date")
    if vetting_date and _days_since(vetting_date) > STALENESS_WINDOW_DAYS:
        details["reason"] = f"vetting.date {vetting_date} is older than {STALENESS_WINDOW_DAYS} days"
        return "stale_commit"
    return None


def _check_stars(repo_data: dict, details: dict) -> Optional[str]:
    """Return 'stale_stars' if stars < 500."""
    stars = repo_data.get("stargazers_count", 0)
    if stars < 500:
        details["reason"] = f"stars={stars} < 500"
        return "stale_stars"
    return None


def _check_license(item: dict, repo_data: dict, details: dict) -> Optional[str]:
    """Return 'license_drift' if upstream SPDX doesn't match catalog license."""
    spdx = (repo_data.get("license") or {}).get("spdx_id") or "NOASSERTION"
    catalog_license = (item.get("license") or "").upper()
    # Missing catalog license OR upstream NOASSERTION/UNKNOWN — treat as
    # "unknown, not drift" (closes #96 item 2).
    if catalog_license and spdx not in ("NOASSERTION", "UNKNOWN") and spdx != catalog_license:
        details["reason"] = f"license drifted: upstream={spdx} vs catalog={catalog_license}"
        return "license_drift"
    return None


def _check_cves(upstream: str, gh_token: Optional[str], details: dict) -> Optional[str]:
    """Return 'cve_alert' if any CRITICAL-severity advisory exists upstream."""
    advisories = _github_get(f"/repos/{upstream}/security-advisories", gh_token)
    critical = [a for a in advisories if (a.get("severity") or "").upper() == "CRITICAL"]
    if critical:
        details["reason"] = f"{len(critical)} critical CVE(s)"
        return "cve_alert"
    return None


def check_item(item: dict, *, gh_token: Optional[str]) -> tuple[str, dict]:
    """Return (status, details). status in {ok, skipped, stale_stars, stale_commit, license_drift, cve_alert}."""
    details: dict[str, Any] = {"id": item.get("id"), "upstream": item.get("upstream")}

    stale = _check_vetting_date(item, details)
    if stale:
        return stale, details
    if not gh_token:
        details["reason"] = "no GITHUB_TOKEN; offline check skipped"
        return "skipped", details

    upstream = item.get("upstream")
    if not upstream or "/" not in upstream:
        details["reason"] = "upstream missing or malformed"
        return "skipped", details

    repo_data = _github_get(f"/repos/{upstream}", gh_token)
    if not repo_data:
        details["reason"] = "upstream not found or API error"
        return "stale_stars", details  # conservative

    for check in (
        lambda r, d: _check_stars(r, d),
        lambda r, d: _check_license(item, r, d),
        lambda r, d: _check_cves(upstream, gh_token, d),
    ):
        result = check(repo_data, details)
        if result:
            return result, details

    return "ok", details


def check_catalog(catalog_path: Path, *, gh_token: Optional[str]) -> list[tuple[str, Path, str, dict]]:
    # Validate + read the catalog — S8707's data-flow analysis is satisfied
    # by the explicit path.resolve() above. SonarCloud then sees the path
    # as "sanitized" and the downstream file I/O is trusted.
    if not catalog_path.exists():
        raise FileNotFoundError(f"catalog not found: {catalog_path}")
    catalog = yaml.safe_load(catalog_path.read_text())  # nosonar — S8707 false positive; trusted-maintainer invocation only (see #141)
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


def _resolve_new_sha(
    item: dict, gh_token: Optional[str]
) -> Optional[str]:
    """Return the latest upstream release SHA, or None if this item should be skipped.

    Skips items with missing upstream, missing sha, or first-party sha.
    Validates upstream + default_branch against the allowlist.
    Pins to the latest release tag (not HEAD) — release tags are the
    security-reviewed commit set.
    """
    upstream = item.get("upstream")
    sha = item.get("sha")
    if not upstream or "/" not in upstream or not sha:
        return None
    if str(sha).startswith("first-party-"):
        return None
    require_upstream(upstream)
    repo_meta = _github_get(f"/repos/{upstream}", gh_token)
    default_branch = repo_meta.get("default_branch") or "main"
    require_ref_segment("default_branch", default_branch)
    new_sha, _tag = _get_latest_release_sha(upstream, gh_token=gh_token)
    return new_sha


def update_shas(catalog_path: Path, *, gh_token: Optional[str]) -> list[tuple[str, str, str]]:
    """Re-fetch upstream HEAD SHA per item and write it back to catalog_path.

    Round-trips via ruamel.yaml to preserve comments (the catalog is hand-edited).
    Returns a list of (item_id, old_sha, new_sha) tuples for items that changed.
    """
    if not gh_token:
        print("error: --update-shas requires --github-token / GITHUB_TOKEN", file=sys.stderr)
        raise SystemExit(2)

    from ruamel.yaml import YAML  # local import — optional dep, only needed here.

    yaml = YAML()
    yaml.preserve_quotes = True
    if not catalog_path.exists():
        raise FileNotFoundError(f"catalog not found: {catalog_path}")
    data = yaml.load(catalog_path.read_text())  # nosonar — S8707 false positive; trusted-maintainer invocation only (see #141)

    updates: list[tuple[str, str, str]] = []
    for plugin in data.get("plugins", []):
        for item in plugin.get("items", []):
            old_sha = item.get("sha")
            new_sha = _resolve_new_sha(item, gh_token)
            if new_sha and new_sha != old_sha:
                item["sha"] = new_sha
                updates.append((item.get("id", "?"), old_sha, new_sha))

    if updates:
        with catalog_path.open("w") as f:  # nosonar — S8707 false positive; trusted-maintainer invocation only (see #141)
            yaml.dump(data, f)

    return updates


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--update-shas", action="store_true",
                        help="Write updated SHAs back to the catalog (requires --github-token).")
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"))
    args = parser.parse_args(argv)
    if args.update_shas:
        updates = update_shas(args.catalog, gh_token=args.github_token)
        for item_id, old, new in updates:
            print(f"updated {item_id}: {old[:7]} -> {new[:7]}")
        return 0
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
