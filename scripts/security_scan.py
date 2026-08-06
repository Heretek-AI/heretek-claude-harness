"""Security scan orchestrator. Walks catalog.yaml, finds items whose
upstream SHA differs from the pinned SHA, runs the per-kind scanner,
emits per-item JSON reports, bumps the catalog SHA on a new branch,
and drafts a PR against it.

CLI:
    python scripts/security_scan.py                  # daily cron mode
    python scripts/security_scan.py --item context7  # debug: one item
    python scripts/security_scan.py --dry-run        # skip issue/PR creation
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._allowlist import require_id_segment, require_sha, require_upstream  # noqa: E402

import requests
import yaml

from .catalog_updater import bump_item_sha
from .issue_drafter import draft_issue_and_pr
from .scanners.base import Finding, ScannerReport
from .scanners.lsp import scan_lsp
from .scanners.mcp import scan_mcp
from .scanners.skills import scan_skill

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


@dataclasses.dataclass
class ScanSummary:
    report_count: int
    error_count: int


def _get_latest_release_sha(
    upstream: str, *, gh_token: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    """Return (sha, tag) of the latest upstream release, or (None, None)."""
    headers = {"Accept": "application/vnd.github+json"}
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"
    r = requests.get(
        f"{GITHUB_API}/repos/{upstream}/releases/latest",
        headers=headers,
        timeout=10,
    )
    if r.status_code != 200:
        return None, None
    data = r.json()
    return data.get("target_commitish"), data.get("tag_name")


def _shallow_clone(upstream: str, sha: str, target: Path) -> None:
    """git clone --depth 1 <upstream> @<sha> into target."""
    require_upstream(upstream)
    require_sha(sha)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", f"https://github.com/{upstream}.git", "."],
        cwd=str(target),
        check=True,
        capture_output=True,
        timeout=120,
    )
    subprocess.run(
        ["git", "checkout", sha],
        cwd=str(target),
        check=True,
        capture_output=True,
        timeout=30,
    )


def _dispatch_scanner(item: dict, path: Path, *, vt_token: Optional[str]) -> ScannerReport:
    kind = item.get("kind")
    item_id = item.get("id", path.name)
    if kind == "skill":
        return scan_skill(path, item_id=item_id)
    if kind == "mcp":
        return scan_mcp(path, item_id=item_id, vt_token=vt_token)
    if kind == "lsp":
        return scan_lsp(path, item_id=item_id)
    return ScannerReport(
        item_id=item_id,
        scanner="unsupported",
        severity="block",
        findings=[
            Finding(
                path="*",
                line=None,
                message=f"unsupported item kind: {kind!r}",
                rule_id="unsupported-kind",
            )
        ],
    )


def _commit_catalog_bump(
    *,
    catalog_path: Path,
    repo_root: Path,
    plugin: str,
    item_id: str,
    new_sha: str,
    vetting_date: str,
) -> str:
    """Bump catalog.yaml, create a security-scan branch, commit + push.

    The caller is responsible for being on a clean main branch before calling
    this function. After the bump, the new branch is pushed so the subsequent
    draft_issue_and_pr call can attach the PR to a branch with the catalog
    edit already in its commit log.

    Returns the new branch name (`security-scan/<item>-<sha12>`).
    """
    # 1. Edit catalog.yaml in place (sha + vetting.date).
    require_id_segment("item_id", item_id)
    require_sha(new_sha)
    bump_item_sha(catalog_path, plugin, item_id, new_sha, vetting_date)

    branch = f"security-scan/{item_id}-{new_sha[:12]}"

    # 2. Create the branch from current HEAD (assumed to be main); the
    # uncommitted catalog.yaml change stays in the working tree and will be
    # committed onto the new branch.
    subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )

    # 3. Stage + commit the bump on the new branch.
    try:
        rel_catalog = str(catalog_path.relative_to(repo_root))
    except ValueError:
        # catalog_path is outside repo_root (e.g. absolute path passed by
        # an external caller). Compute a relative path so `git add` works.
        rel_catalog = os.path.relpath(catalog_path, repo_root)
    subprocess.run(
        ["git", "add", rel_catalog],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"bump {plugin}/{item_id} to {new_sha[:12]}"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )

    # 4. Push so the PR can be opened against this branch.
    subprocess.run(
        ["git", "push", "origin", branch],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )

    # 5. Return to the repo's default branch so the next item starts from a
    # clean state. Auto-detect via `git rev-parse --abbrev-ref HEAD`
    # (falls back to "main" if detection fails; HERETEK_DEFAULT_BRANCH
    # overrides for CI / scripted environments).
    default_branch = os.environ.get("HERETEK_DEFAULT_BRANCH")
    if not default_branch:
        probe = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        default_branch = probe.stdout.strip() if probe.returncode == 0 else "main"
    subprocess.run(
        ["git", "checkout", default_branch],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )

    return branch


def run(
    catalog_path: Path,
    output_dir: Path,
    *,
    gh_token: Optional[str] = None,
    vt_token: Optional[str] = None,
    dry_run: bool = False,
    item_filter: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> ScanSummary:
    """Run the full scan. Emit per-item JSON reports under output_dir."""
    if repo_root is None:
        repo_root = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd()))

    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = yaml.safe_load(catalog_path.read_text())

    report_count = 0
    error_count = 0

    for plugin in catalog.get("plugins", []):
        plugin_name = plugin.get("name", "?")
        for item in plugin.get("items") or []:
            if item_filter and item.get("id") != item_filter:
                continue
            sha = item.get("sha", "")
            if sha.startswith("first-party-"):
                log.info("skipping first-party item: %s/%s", plugin_name, item.get("id"))
                continue
            upstream = item.get("upstream")
            if not upstream or "/" not in upstream:
                log.warning("skipping malformed upstream: %s/%s", plugin_name, item.get("id"))
                continue

            latest_sha, _ = _get_latest_release_sha(upstream, gh_token=gh_token)
            if latest_sha is None:
                log.warning("no release found for %s/%s", plugin_name, item.get("id"))
                error_count += 1
                continue

            if latest_sha == sha:
                log.info("up-to-date: %s/%s", plugin_name, item.get("id"))
                continue

            log.info("NEW RELEASE: %s/%s → %s", plugin_name, item.get("id"), latest_sha[:12])

            scratch = Path("/tmp") / "scan" / f"{plugin_name}-{item.get('id')}-{latest_sha[:12]}"
            try:
                _shallow_clone(upstream, latest_sha, scratch)
                report = _dispatch_scanner(item, scratch, vt_token=vt_token)
            except Exception as e:
                log.exception("clone/scan failed for %s/%s: %s", plugin_name, item.get("id"), e)
                error_count += 1
                continue

            report_file = output_dir / f"{plugin_name}-{item.get('id')}.json"
            report_file.write_text(json.dumps(dataclasses.asdict(report), indent=2, default=str))
            report_count += 1

            # Defensive SHA check (Task 8): if draft_issue_and_pr's base-ref
            # lookup silently fell back to the zero-SHA, refuse to draft a
            # PR against the bogus ref. Concern flagged in task-7-report.md.
            if latest_sha == "0" * 40:
                log.error(
                    "refusing to draft PR for %s/%s: latest_sha is zero-SHA fallback",
                    plugin_name,
                    item.get("id"),
                )
                error_count += 1
                continue

            if not dry_run and gh_token:
                # C1 (final-review fix): bump catalog.yaml + push the new
                # branch BEFORE drafting the PR. Otherwise the daily cron
                # opens empty draft PRs with no catalog edit in the diff.
                try:
                    _commit_catalog_bump(
                        catalog_path=catalog_path,
                        repo_root=repo_root,
                        plugin=plugin_name,
                        item_id=item["id"],
                        new_sha=latest_sha,
                        vetting_date=date.today().isoformat(),
                    )
                except subprocess.CalledProcessError as e:
                    log.exception(
                        "git commit/push failed for %s/%s: %s",
                        plugin_name,
                        item.get("id"),
                        e,
                    )
                    error_count += 1
                    continue

                issue_url, pr_url = draft_issue_and_pr(
                    report,
                    gh_token=gh_token,
                    repo="Heretek-AI/heretek-claude-harness",
                    plugin=plugin_name,
                    item=item["id"],
                    new_sha=latest_sha,
                )
                log.info("issue: %s | pr: %s", issue_url, pr_url)

    return ScanSummary(report_count=report_count, error_count=error_count)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("catalog/catalog.yaml"))
    parser.add_argument("--output", type=Path, default=Path("reports"))
    parser.add_argument("--github-token", default=None)
    parser.add_argument("--vt-token", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--item", default=None, help="restrict to one item id")
    parser.add_argument("--pr-mode", action="store_true",
                        help="run against a single item whose catalog SHA has been bumped (for PR required check)")
    args = parser.parse_args(argv)

    summary = run(
        catalog_path=args.catalog,
        output_dir=args.output,
        gh_token=args.github_token,
        vt_token=args.vt_token,
        dry_run=args.dry_run or not args.github_token,
        item_filter=args.item,
        repo_root=Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())),
    )
    print(f"reports={summary.report_count} errors={summary.error_count}")
    return 0 if summary.error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
