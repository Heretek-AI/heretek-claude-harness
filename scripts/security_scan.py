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
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._allowlist import (  # noqa: I001
    require_id_segment,
    require_ref_segment,
    require_sha,
    require_upstream,
)
from scripts._http import check_content_length

import requests
import yaml

from scripts.catalog_updater import bump_item_sha
from scripts.issue_drafter import draft_issue_and_pr
from scripts.scanners.base import Finding, ScannerReport
from scripts.scanners.lsp import scan_lsp
from scripts.scanners.mcp import scan_mcp
from scripts.scanners.skills import scan_skill
from scripts.suppression import load_suppressions

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Default upstream repo. Used as fallback when GITHUB_REPOSITORY is unset
# (e.g. local CLI runs). CI / workflow runs always have GITHUB_REPOSITORY set
# by the Actions runner, so forks open issues/PRs against the fork, not upstream.
DEFAULT_REPO = "Heretek-AI/heretek-claude-harness"


@dataclasses.dataclass
class ScanSummary:
    report_count: int
    error_count: int


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _get_latest_release_sha(
    upstream: str, *, gh_token: str | None
) -> tuple[str | None, str | None]:
    """Return (sha, tag) of the latest upstream release, or (None, None).

    Resolves branch-name `target_commitish` to a commit SHA via the
    branches/<name> endpoint when the release's target is not already a
    40-hex SHA (common for repos that release from main).
    """
    headers = {"Accept": "application/vnd.github+json"}
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"
    r = requests.get(
        f"{GITHUB_API}/repos/{upstream}/releases/latest",
        headers=headers,
        timeout=10,
    )
    check_content_length(r)
    if r.status_code != 200:
        return None, None
    data = r.json()
    target = data.get("target_commitish")
    tag = data.get("tag_name")
    if target and not _SHA_RE.match(target):
        # target_commitish is a branch name; resolve to SHA via branches API
        r2 = requests.get(
            f"{GITHUB_API}/repos/{upstream}/branches/{target}",
            headers=headers,
            timeout=10,
        )
        check_content_length(r2)
        if r2.status_code == 200:
            target = r2.json().get("commit", {}).get("sha") or None
        else:
            target = None
    return target, tag


def _shallow_clone(upstream: str, sha: str, target: Path) -> None:
    """Clone <upstream> @<sha> into target.

    Uses `--no-checkout` (full clone, no working tree) so `git checkout <sha>`
    works on any git >= 2.0 without triggering an auto-fetch round-trip.
    Resolves issue #34: `--depth 1` + auto-fetch breaks on git < 2.30 or
    sandboxed networks that block the auto-fetch.
    """
    require_upstream(upstream)
    require_sha(sha)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    # MUST be called before URL interpolation; security contract: require_upstream + require_sha
    # defense-in-depth against SSRF via git transport options (e.g. --upload-pack=evil).
    subprocess.run(
        ["git", "clone", "--no-checkout", f"https://github.com/{upstream}.git", "."],
        cwd=str(target),
        check=True,
        capture_output=True,
        timeout=300,
    )
    subprocess.run(
        ["git", "checkout", sha],
        cwd=str(target),
        check=True,
        capture_output=True,
        timeout=30,
    )


def _dispatch_scanner(item: dict, path: Path, *, vt_token: str | None) -> ScannerReport:
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
    if default_branch:
        try:
            require_ref_segment("HERETEK_DEFAULT_BRANCH", default_branch)
        except ValueError as exc:
            log.warning(
                "ignoring invalid HERETEK_DEFAULT_BRANCH=%r: %s",
                default_branch,
                exc,
            )
            default_branch = None
    if not default_branch:
        probe = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        probed = probe.stdout.strip() if probe.returncode == 0 else "main"
        if probed != "main":
            try:
                require_ref_segment("default_branch_probe", probed)
            except ValueError as exc:
                log.warning("ignoring invalid default_branch_probe=%r: %s", probed, exc)
                probed = "main"
        default_branch = probed
    subprocess.run(
        ["git", "checkout", default_branch],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )

    return branch


def _setup_state(state_dir: Path | None) -> tuple[Path | None, set[str]]:
    """Initialize the checkpoint state file for resumption.

    Returns (state_file, done_items). state_file is None when checkpointing
    is disabled; done_items is always a fresh set.
    """
    if state_dir is None:
        return None, set()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"security-scan-{date.today().isoformat()}.json"
    return state_file, _load_done_items(state_file)


def _should_skip_item(item: dict, composite_id: str, done_items: set[str]) -> str | None:
    """Return a skip-reason string if this item should be skipped, else None.

    Skips: first-party items, malformed upstream, items already in checkpoint.
    """
    sha = item.get("sha", "")
    if sha.startswith("first-party-"):
        return "first-party"
    upstream = item.get("upstream")
    if not upstream or "/" not in upstream:
        return "malformed upstream"
    if composite_id in done_items:
        return "already done"
    return None


def _vt_cap_state(vt_calls: int, vt_cap: int, vt_token: str | None) -> tuple[str | None, bool]:
    """Honour the per-run VT cap. Returns (effective_vt, cap_hit).

    Above the cap we pass vt_token=None so scan_mcp soft-fails via its
    "no VT_TOKEN; skipped" branch; the report still records the scan
    (with vt-skipped finding), so maintainers see it.
    """
    if vt_token and vt_calls >= vt_cap:
        return None, True
    return vt_token, False


def _scan_and_persist(
    *,
    item: dict,
    plugin_name: str,
    item_id: str,
    composite_id: str,
    upstream: str,
    latest_sha: str,
    scratch: Path,
    output_dir: Path,
    effective_vt: str | None,
    suppressions: set[tuple[str, str]],
    state_file: Path | None,
    done_items: set[str],
) -> tuple[ScannerReport | None, str | None]:
    """Clone, dispatch, apply suppressions, write report, checkpoint.

    Returns (report, error_msg). report is None iff error_msg is set.
    """
    try:
        _shallow_clone(upstream, latest_sha, scratch)
        report = _dispatch_scanner(item, scratch, vt_token=effective_vt)
    except Exception as e:
        log.exception("clone/scan failed for %s: %s", composite_id, e)
        return None, str(e)

    report = _apply_suppressions(report, suppressions)

    report_file = output_dir / f"{plugin_name}-{item_id}.json"
    report_file.write_text(json.dumps(dataclasses.asdict(report), indent=2, default=str))

    # Spec §8.4: checkpoint after each item.
    if state_file is not None:
        done_items.add(composite_id)
        _save_done_items(state_file, done_items)

    return report, None


def _bump_and_draft_pr(
    *,
    report: ScannerReport,
    plugin_name: str,
    item_id: str,
    composite_id: str,
    latest_sha: str,
    gh_token: str | None,
    dry_run: bool,
    repo_root: Path,
    catalog_path: Path,
) -> str | None:
    """Bump catalog.yaml on a branch + draft a tracking issue/PR.

    Returns an error message string on failure, None on success.

    Skipped (no-op) when dry_run or gh_token is missing.

    The defensive zero-SHA check guards against draft_issue_and_pr's base-ref
    lookup silently falling back to "0"*40 (Task 8, task-7-report.md).
    """
    if dry_run or not gh_token:
        return None
    if latest_sha == "0" * 40:
        log.error(
            "refusing to draft PR for %s: latest_sha is zero-SHA fallback",
            composite_id,
        )
        return "zero-SHA fallback"
    try:
        _commit_catalog_bump(
            catalog_path=catalog_path,
            repo_root=repo_root,
            plugin=plugin_name,
            item_id=item_id,
            new_sha=latest_sha,
            vetting_date=date.today().isoformat(),
        )
    except subprocess.CalledProcessError as e:
        log.exception("git commit/push failed for %s: %s", composite_id, e)
        return "git commit/push failed"

    issue_url, pr_url = draft_issue_and_pr(
        report,
        gh_token=gh_token,
        repo=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO),
        plugin=plugin_name,
        item=item_id,
        new_sha=latest_sha,
    )
    log.info("issue: %s | pr: %s", issue_url, pr_url)
    return None


def run(
    catalog_path: Path,
    output_dir: Path,
    *,
    gh_token: str | None = None,
    vt_token: str | None = None,
    dry_run: bool = False,
    item_filter: str | None = None,
    repo_root: Path | None = None,
    vt_cap: int | None = None,
    reviews_dir: Path | None = None,
    state_dir: Path | None = None,
) -> ScanSummary:
    """Run the full scan. Emit per-item JSON reports under output_dir.

    vt_cap:     Hard cap on VirusTotal calls per run (spec §8.2, default 100).
                Beyond the cap, MCP tarball scanning is skipped (soft-fail).
    reviews_dir: Directory of catalog/reviews/*.md ADRs scanned for
                `<!-- suppress: <scanner>:<rule_id> -->` tags (spec §8.7).
                None disables suppression.
    state_dir:  Where to write the resume checkpoint
                `.state/security-scan-<YYYY-MM-DD>.json` (spec §8.4).
                None disables checkpointing.
    """
    if repo_root is None:
        repo_root = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd()))
    if vt_cap is None:
        vt_cap = int(os.environ.get("SECURITY_SCAN_VT_CAP", "100"))

    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = yaml.safe_load(catalog_path.read_text())
    suppressions = load_suppressions(reviews_dir) if reviews_dir else set()
    state_file, done_items = _setup_state(state_dir)

    report_count = 0
    error_count = 0
    vt_calls = 0
    vt_cap_hit = False

    for plugin in catalog.get("plugins", []):
        plugin_name = plugin.get("name", "?")
        for item in plugin.get("items") or []:
            item_id = item.get("id", "?")
            composite_id = f"{plugin_name}/{item_id}"
            if item_filter and item_id != item_filter:
                continue

            skip_reason = _should_skip_item(item, composite_id, done_items)
            if skip_reason:
                log.info("skipping %s: %s", composite_id, skip_reason)
                continue

            sha = item.get("sha", "")
            upstream = item["upstream"]
            latest_sha, _ = _get_latest_release_sha(upstream, gh_token=gh_token)
            if latest_sha is None:
                log.warning("no release found for %s", composite_id)
                error_count += 1
                continue
            if latest_sha == sha:
                log.info("up-to-date: %s", composite_id)
                continue
            log.info("NEW RELEASE: %s → %s", composite_id, latest_sha[:12])

            effective_vt, vt_hit = _vt_cap_state(vt_calls, vt_cap, vt_token)
            if vt_hit:
                vt_cap_hit = True
                log.warning("VT cap (%d) reached; skipping further VT lookups", vt_cap)

            # SonarCloud S5443: never use /tmp directly — symlink/TOCTOU risk.
            # mkdtemp creates a 0o700 dir owned by us; cleanup is handled
            # by the next _shallow_clone call.
            scratch = Path(tempfile.mkdtemp(prefix=f"heretek-scan-{plugin_name}-{item_id}-"))
            report, scan_err = _scan_and_persist(
                item=item,
                plugin_name=plugin_name,
                item_id=item_id,
                composite_id=composite_id,
                upstream=upstream,
                latest_sha=latest_sha,
                scratch=scratch,
                output_dir=output_dir,
                effective_vt=effective_vt,
                suppressions=suppressions,
                state_file=state_file,
                done_items=done_items,
            )
            if scan_err or report is None:
                error_count += 1
                continue
            report_count += 1

            if item.get("kind") == "mcp" and effective_vt:
                vt_calls += 1

            bump_err = _bump_and_draft_pr(
                report=report,
                plugin_name=plugin_name,
                item_id=item_id,
                composite_id=composite_id,
                latest_sha=latest_sha,
                gh_token=gh_token,
                dry_run=dry_run,
                repo_root=repo_root,
                catalog_path=catalog_path,
            )
            if bump_err:
                error_count += 1

    if vt_cap_hit:
        log.warning(
            "VT cap of %d was reached; later MCP items scanned with vt_token=None",
            vt_cap,
        )
    return ScanSummary(report_count=report_count, error_count=error_count)


def _apply_suppressions(report: ScannerReport, suppressions: set[tuple[str, str]]) -> ScannerReport:
    """Downgrade suppressed findings to severity=info; preserve them in report."""
    from .suppression import is_suppressed  # local import to avoid cycles in tests

    new_findings = []
    downgraded = False
    for f in report.findings:
        if is_suppressed(suppressions, scanner=report.scanner, rule_id=f.rule_id):
            new_findings.append(
                Finding(
                    path=f.path,
                    line=f.line,
                    message=f"[suppressed] {f.message}",
                    rule_id=f.rule_id,
                    cve_id=f.cve_id,
                )
            )
            downgraded = True
        else:
            new_findings.append(f)
    new_severity = (
        "info" if (downgraded and report.severity in ("warn", "block")) else report.severity
    )
    return ScannerReport(
        item_id=report.item_id,
        scanner=report.scanner,
        severity=new_severity,
        findings=new_findings,
        raw=report.raw,
    )


def _load_done_items(state_file: Path) -> set[str]:
    """Load completed item ids from a checkpoint file. Missing/corrupt → empty set."""
    if not state_file.exists():
        return set()
    try:
        data = json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, dict):
        return set()
    return {k for k, v in data.items() if v == "done"}


def _save_done_items(state_file: Path, done: set[str]) -> None:
    """Atomically write the checkpoint file."""
    tmp = state_file.with_suffix(state_file.suffix + ".tmp")
    tmp.write_text(json.dumps(dict.fromkeys(sorted(done), "done"), indent=2))
    tmp.replace(state_file)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("catalog/catalog.yaml"))
    parser.add_argument("--output", type=Path, default=Path("reports"))
    parser.add_argument("--github-token", default=None)
    parser.add_argument("--vt-token", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--item", default=None, help="restrict to one item id")
    parser.add_argument(
        "--pr-mode",
        action="store_true",
        help="run against a single item whose catalog SHA has been bumped (for PR required check)",
    )
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
