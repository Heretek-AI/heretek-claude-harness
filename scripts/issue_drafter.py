"""Issue + draft-PR creator. Opens a tracking issue and a draft PR that
bumps catalog.yaml's sha for one item.

CLI: not directly invokable — called by scripts/security_scan.py.
"""

from __future__ import annotations

import json
import logging

import requests

from ._http import check_content_length
from .scanners.base import ScannerReport

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _search_existing_issue(*, token: str, repo: str, title: str) -> str | None:
    """Return existing issue html_url if an open issue with this title exists."""
    r = requests.get(
        f"{GITHUB_API}/search/issues",
        headers=_gh_headers(token),
        params={
            "q": f'repo:{repo} is:issue is:open in:title "{title}"',
            "per_page": 1,
        },
        timeout=10,
    )
    check_content_length(r)
    if r.status_code != 200:
        return None
    items = r.json().get("items", [])
    return items[0]["html_url"] if items else None


def _create_issue(
    *, token: str, repo: str, title: str, body: str, labels: list[str]
) -> tuple[str, int]:
    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/issues",
        headers=_gh_headers(token),
        json={"title": title, "body": body, "labels": labels},
        timeout=10,
    )
    check_content_length(r)
    r.raise_for_status()
    data = r.json()
    return data["html_url"], data["number"]


def _create_branch(*, token: str, repo: str, branch: str, base_sha: str) -> str:
    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/git/refs",
        headers=_gh_headers(token),
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        timeout=10,
    )
    check_content_length(r)
    r.raise_for_status()
    return r.json()["ref"]


def _create_pr(
    *, token: str, repo: str, title: str, body: str, head: str, base: str
) -> tuple[str, int]:
    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/pulls",
        headers=_gh_headers(token),
        json={"title": title, "body": body, "head": head, "base": base, "draft": True},
        timeout=10,
    )
    check_content_length(r)
    r.raise_for_status()
    data = r.json()
    return data["html_url"], data["number"]


def _build_issue_body(report: ScannerReport, *, plugin: str, item: str, new_sha: str) -> str:
    findings_md = (
        "\n".join(
            f"- `{f.path}:{f.line}` — {f.message}"
            + (f" (rule `{f.rule_id}`)" if f.rule_id else "")
            + (f" (CVE `{f.cve_id}`)" if f.cve_id else "")
            for f in report.findings
        )
        or "_(no findings)_"
    )
    return (
        f"New upstream release detected for `{plugin}/{item}`.\n\n"
        f"- New SHA: `{new_sha}`\n"
        f"- Severity: **{report.severity}**\n"
        f"- Scanner: `{report.scanner}`\n\n"
        f"### Findings\n\n{findings_md}\n\n"
        f"### Raw scanner output\n\n```json\n{json.dumps(report.raw, indent=2)[:4000]}\n```\n"
    )


def draft_issue_and_pr(
    report: ScannerReport,
    *,
    gh_token: str,
    repo: str,
    plugin: str,
    item: str,
    new_sha: str,
    base_branch: str = "main",
) -> tuple[str, str | None]:
    """Open tracking issue (or update existing) and draft a SHA-bump PR.

    Returns (issue_url, pr_url_or_None).
    """
    title = f"New upstream release: {plugin}/{item}"
    body = _build_issue_body(report, plugin=plugin, item=item, new_sha=new_sha)
    labels = ["security-scan"]
    if report.severity == "block":
        labels.append("severity:block")

    # Dedup: look for existing open issue with this title
    existing = _search_existing_issue(token=gh_token, repo=repo, title=title)
    if existing is not None:
        issue_url = existing
        log.info("issue already open, skipping duplicate: %s", existing)
    else:
        issue_url, _ = _create_issue(
            token=gh_token, repo=repo, title=title, body=body, labels=labels
        )

    # Get the SHA of the base branch to create a new branch from.
    # GitHub API call; loud failure per spec §8.1 — see issue #30.
    try:
        r = requests.get(
            f"{GITHUB_API}/repos/{repo}/git/ref/heads/{base_branch}",
            headers=_gh_headers(gh_token),
            timeout=10,
        )
        check_content_length(r)
        r.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"base ref lookup failed for {base_branch}: {e}") from e
    # JSON-shape fallback: response was 2xx but missing {"object": {"sha": ...}}.
    base_ref = r.json().get("object", {}).get("sha") or ("0" * 40)

    branch = f"security-scan/{item}-{new_sha[:12]}"
    try:
        _create_branch(token=gh_token, repo=repo, branch=branch, base_sha=base_ref)
    except requests.HTTPError as e:
        log.warning("branch %s likely exists already: %s", branch, e)

    pr_url, _ = _create_pr(
        token=gh_token,
        repo=repo,
        title=f"security-scan: bump {plugin}/{item} to {new_sha[:12]}",
        body=f"Closes tracking issue in this branch's commit log.\n\n{body}",
        head=branch,
        base=base_branch,
    )
    return issue_url, pr_url
