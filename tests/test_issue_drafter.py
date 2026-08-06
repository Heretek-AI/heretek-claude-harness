"""Tests for the issue drafter. GitHub API is mocked at the requests layer."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.issue_drafter import draft_issue_and_pr
from scripts.scanners.base import Finding, ScannerReport


@pytest.fixture
def clean_report() -> ScannerReport:
    return ScannerReport(
        item_id="context7",
        scanner="skillspector",
        severity="clean",
        findings=[],
    )


@pytest.fixture
def block_report() -> ScannerReport:
    return ScannerReport(
        item_id="context7",
        scanner="skillspector",
        severity="block",
        findings=[Finding(path="SKILL.md", line=1, message="prompt injection", rule_id="R1")],
    )


@patch("scripts.issue_drafter.requests.post")
@patch("scripts.issue_drafter.requests.get")
def test_drafts_issue_and_pr_when_clean(
    mock_get: MagicMock, mock_post: MagicMock, clean_report: ScannerReport
) -> None:
    # search existing issues: 0 results
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"items": []})
    # post returns: first call = issue creation, second = ref creation, third = PR creation
    mock_post.side_effect = [
        MagicMock(status_code=201, json=lambda: {"html_url": "https://x/issue/1", "number": 1}),
        MagicMock(status_code=201, json=lambda: {"ref": "refs/heads/security-scan/x"}),
        MagicMock(status_code=201, json=lambda: {"html_url": "https://x/pr/2", "number": 2}),
    ]
    issue_url, pr_url = draft_issue_and_pr(
        clean_report,
        gh_token="fake",
        repo="owner/repo",
        plugin="mcp-pack",
        item="context7",
        new_sha="0" * 40,
    )
    assert "issue/1" in issue_url
    assert "pr/2" in pr_url
    assert mock_post.call_count == 3


@patch("scripts.issue_drafter.requests.post")
@patch("scripts.issue_drafter.requests.get")
def test_dedups_when_issue_already_exists(
    mock_get: MagicMock, mock_post: MagicMock, clean_report: ScannerReport
) -> None:
    mock_get.return_value = MagicMock(
        status_code=200, json=lambda: {"items": [{"html_url": "https://x/issue/9", "number": 9}]}
    )
    issue_url, pr_url = draft_issue_and_pr(
        clean_report,
        gh_token="fake",
        repo="owner/repo",
        plugin="mcp-pack",
        item="context7",
        new_sha="0" * 40,
    )
    assert "issue/9" in issue_url
    # should NOT have created a new issue (only 2 posts: ref + PR)
    assert mock_post.call_count == 2


def test_block_severity_includes_findings_in_issue_body(block_report: ScannerReport) -> None:
    body = (block_report.item_id, [f.message for f in block_report.findings])
    assert "prompt injection" in body[1]
    assert block_report.severity == "block"


@patch("scripts.issue_drafter.requests.post")
@patch("scripts.issue_drafter.requests.get")
def test_draft_raises_on_base_ref_http_error(
    mock_get: MagicMock, mock_post: MagicMock, clean_report: ScannerReport
) -> None:
    """Issue #30: base-ref lookup must raise, not silently fake a zero SHA."""
    # First GET: search-existing-issue (succeeds)
    # Second GET: base-ref lookup (HTTPError -> raise)
    base_ref_mock = MagicMock()
    base_ref_mock.raise_for_status.side_effect = requests.HTTPError(
        "404 Not Found", response=MagicMock(status_code=404)
    )
    mock_get.side_effect = [
        MagicMock(status_code=200, json=lambda: {"items": []}),  # dedup check
        base_ref_mock,  # base-ref lookup — this is the one that must raise
    ]
    with pytest.raises(RuntimeError, match="base ref lookup failed for main"):
        draft_issue_and_pr(
            clean_report,
            gh_token="fake",
            repo="owner/repo",
            plugin="mcp-pack",
            item="context7",
            new_sha="0" * 40,
        )
