"""Tests for the security_scan.py orchestrator. External HTTP and scanners
are mocked; see tests/fixtures/security_scan/ for end-to-end integration."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.scanners.base import Finding, ScannerReport
from scripts.security_scan import run


@pytest.fixture
def sample_catalog(tmp_path: Path) -> Path:
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """marketplace:
  name: heretek
plugins:
  - name: mcp-pack
    items:
      - id: context7
        upstream: upstash/context7
        sha: "0000000000000000000000000000000000000000"
        license: MIT
        kind: skill
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    return p


@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_emits_no_report_when_upstream_matches_pinned(
    mock_scan: MagicMock, mock_sha: MagicMock, sample_catalog: Path, tmp_path: Path
) -> None:
    """All items fresh → zero reports, no issues opened."""
    mock_sha.return_value = ("0" * 40, "tag")
    summary = run(
        catalog_path=sample_catalog,
        output_dir=tmp_path,
        dry_run=True,
    )
    assert summary.report_count == 0
    mock_scan.assert_not_called()


@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
@patch("scripts.security_scan.shutil.rmtree")
@patch("scripts.security_scan.subprocess.run")
def test_run_emits_report_when_upstream_changed(
    mock_subprocess: MagicMock,
    mock_rmtree: MagicMock,
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
) -> None:
    """Upstream SHA differs → shallow-clone + scan + report."""
    mock_sha.return_value = ("a" * 40, "tag")
    # mock git clone: creates a fake checkout dir
    def fake_clone(*args, **kwargs):
        target = Path(kwargs.get("cwd", "/")) / "context7"
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text("# fake")
        return MagicMock(returncode=0, stderr="", stdout="")
    mock_subprocess.side_effect = fake_clone
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    summary = run(
        catalog_path=sample_catalog,
        output_dir=tmp_path,
        dry_run=True,
    )
    assert summary.report_count == 1
    report_file = next(tmp_path.glob("*.json"))
    report = json.loads(report_file.read_text())
    assert report["severity"] == "clean"


@patch("scripts.security_scan.draft_issue_and_pr")
@patch("scripts.security_scan._shallow_clone")
@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_errors_when_latest_sha_is_zero_fallback(
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    mock_clone: MagicMock,
    mock_draft: MagicMock,
    tmp_path: Path,
) -> None:
    """Orchestrator guards scripts/issue_drafter.py's JSON-shape-zero-SHA fallback
    (line 238). Upstream changes to a zero SHA → error_count++, no draft."""
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: mcp-pack
    items:
      - id: context7
        upstream: upstash/context7
        sha: "abc123abc123abc123abc123abc123abc123abcd"
        license: MIT
        kind: skill
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    mock_sha.return_value = ("0" * 40, "tag")  # upstream SHA "changed" to zero
    mock_clone.return_value = None
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    summary = run(
        catalog_path=p,
        output_dir=tmp_path,
        dry_run=False,
        gh_token="fake",
    )
    assert summary.report_count == 1
    assert summary.error_count == 1
    mock_draft.assert_not_called()


def test_run_skips_first_party_items(tmp_path: Path) -> None:
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: agents
    items:
      - id: code-reviewer
        upstream: Heretek-AI/heretek-claude-harness
        sha: "first-party-agent"
"""
    )
    summary = run(catalog_path=p, output_dir=tmp_path, dry_run=True)
    assert summary.report_count == 0


def test_scan_summary_dataclass_basic() -> None:
    from scripts.security_scan import ScanSummary
    s = ScanSummary(report_count=0, error_count=0)
    assert s.report_count == 0


@patch("scripts.security_scan.draft_issue_and_pr")
@patch("scripts.security_scan.bump_item_sha")
@patch("scripts.security_scan.subprocess.run")
@patch("scripts.security_scan.scan_skill")
@patch("scripts.security_scan._get_latest_release_sha")
def test_run_commits_catalog_bump_before_drafting_pr(
    mock_sha: MagicMock,
    mock_scan: MagicMock,
    mock_subprocess: MagicMock,
    mock_bump: MagicMock,
    mock_draft: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
) -> None:
    """C1: when upstream changes, bump_item_sha + git commit/push must
    happen BEFORE draft_issue_and_pr so the daily cron opens PRs with
    the catalog.yaml edit already in their diff."""
    mock_sha.return_value = ("a" * 40, "v1.0.0")

    call_order: list[str] = []

    def bump_side(*args, **kwargs):
        call_order.append("bump_item_sha")

    def subprocess_side(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, list) and cmd:
            label = cmd[1] if len(cmd) > 1 else cmd[0]
            call_order.append(f"git:{label}")
        # Make git clone create the scratch dir so dispatch_scanner gets a path.
        if isinstance(cmd, list) and len(cmd) >= 3 and cmd[1] == "clone":
            cwd = kwargs.get("cwd", "/")
            Path(cwd).mkdir(parents=True, exist_ok=True)
            (Path(cwd) / "SKILL.md").write_text("# fake")
        return MagicMock(returncode=0, stderr="", stdout="")

    def draft_side(*args, **kwargs):
        call_order.append("draft_issue_and_pr")
        return ("http://issue", "http://pr")

    mock_bump.side_effect = bump_side
    mock_subprocess.side_effect = subprocess_side
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    mock_draft.side_effect = draft_side

    summary = run(
        catalog_path=sample_catalog,
        output_dir=tmp_path,
        gh_token="fake-token",
        repo_root=tmp_path,
    )

    assert summary.report_count == 1
    # bump_item_sha must be called before draft_issue_and_pr.
    assert "bump_item_sha" in call_order, call_order
    assert "draft_issue_and_pr" in call_order, call_order
    bump_idx = call_order.index("bump_item_sha")
    draft_idx = call_order.index("draft_issue_and_pr")
    assert bump_idx < draft_idx, f"bump must precede draft: {call_order}"
    # git commit must happen before draft_issue_and_pr.
    commit_idx = next(
        (i for i, c in enumerate(call_order) if c == "git:commit"), -1
    )
    assert commit_idx >= 0, f"expected git commit, got: {call_order}"
    assert commit_idx < draft_idx, f"git commit must precede draft: {call_order}"
    # git push must happen before draft_issue_and_pr.
    push_idx = next(
        (i for i, c in enumerate(call_order) if c == "git:push"), -1
    )
    assert push_idx >= 0, f"expected git push, got: {call_order}"
    assert push_idx < draft_idx, f"git push must precede draft: {call_order}"


@patch("scripts.security_scan.shutil.rmtree")
@patch("scripts.security_scan.subprocess.run")
def test_shallow_clone_uses_no_checkout_for_old_git_compat(
    mock_subprocess: MagicMock, mock_rmtree: MagicMock, tmp_path: Path
) -> None:
    """Issue #34: _shallow_clone must use `--no-checkout` (full clone without
    working tree) so `git checkout <sha>` works on any git >= 2.0 without
    the auto-fetch round-trip that breaks on git < 2.30 or sandboxed networks.
    """
    from scripts.security_scan import _shallow_clone

    target = tmp_path / "scan"
    captured_cmds: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        # Make the checkout land something so dispatch_scanner's path checks pass.
        if cmd[1] == "checkout":
            (Path(kwargs.get("cwd", "/")) / "SKILL.md").write_text("# fake")
        return MagicMock(returncode=0, stderr="", stdout="")

    mock_subprocess.side_effect = fake_run

    _shallow_clone("upstream/repo", "a" * 40, target)

    # Find the clone + checkout invocations.
    clone_cmds = [c for c in captured_cmds if c[1] == "clone"]
    checkout_cmds = [c for c in captured_cmds if c[1] == "checkout"]
    assert len(clone_cmds) == 1, captured_cmds
    assert len(checkout_cmds) == 1, captured_cmds
    # The clone must use --no-checkout, NOT --depth 1 (issue #34's whole point).
    assert "--no-checkout" in clone_cmds[0], clone_cmds[0]
    assert "--depth" not in clone_cmds[0], clone_cmds[0]
    # The checkout must target the requested SHA verbatim.
    assert checkout_cmds[0] == ["git", "checkout", "a" * 40], checkout_cmds[0]


@patch("scripts.security_scan.draft_issue_and_pr")
@patch("scripts.security_scan.subprocess.run")
@patch("scripts.security_scan._shallow_clone")
@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_uses_github_repository_env_var_when_present(
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    mock_clone: MagicMock,
    mock_subprocess: MagicMock,
    mock_draft: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #32: forks must draft issues/PRs against the fork (GITHUB_REPOSITORY),
    not the upstream hardcoded value."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "fork-user/heretek-claude-harness")
    mock_sha.return_value = ("a" * 40, "v1.0.0")
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    mock_subprocess.return_value = MagicMock(returncode=0, stderr="", stdout="")
    mock_draft.return_value = ("https://x/issue/1", "https://x/pr/2")
    run(
        catalog_path=sample_catalog,
        output_dir=tmp_path,
        gh_token="fake-token",
        repo_root=tmp_path,
    )
    assert mock_draft.called
    repo_arg = mock_draft.call_args.kwargs.get("repo") or mock_draft.call_args[1].get("repo")
    assert repo_arg == "fork-user/heretek-claude-harness", repo_arg


@patch("scripts.security_scan.draft_issue_and_pr")
@patch("scripts.security_scan.subprocess.run")
@patch("scripts.security_scan._shallow_clone")
@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_falls_back_to_default_repo_when_env_var_absent(
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    mock_clone: MagicMock,
    mock_subprocess: MagicMock,
    mock_draft: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #32: local CLI invocations (no GITHUB_REPOSITORY) default to upstream."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    mock_sha.return_value = ("a" * 40, "v1.0.0")
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    mock_subprocess.return_value = MagicMock(returncode=0, stderr="", stdout="")
    mock_draft.return_value = ("https://x/issue/1", "https://x/pr/2")
    run(
        catalog_path=sample_catalog,
        output_dir=tmp_path,
        gh_token="fake-token",
        repo_root=tmp_path,
    )
    assert mock_draft.called
    repo_arg = mock_draft.call_args.kwargs.get("repo") or mock_draft.call_args[1].get("repo")
    assert repo_arg == "Heretek-AI/heretek-claude-harness", repo_arg


# ---------------------------------------------------------------------------
# Issue #31 — coverage gap fills for scripts/security_scan.py (target ≥90%).
# These exercise the previously-untouched branches: _get_latest_release_sha
# non-200 path, _dispatch_scanner unsupported-kind branch, the
# "no upstream release found" path, and the main() CLI entry point.
# ---------------------------------------------------------------------------


@patch("scripts.security_scan.requests.get")
def test_get_latest_release_sha_returns_none_on_non_200(mock_get: MagicMock) -> None:
    """Upstream API non-200 (deleted repo, 404, 403 rate-limit) → (None, None)."""
    from scripts.security_scan import _get_latest_release_sha
    mock_get.return_value = MagicMock(status_code=404)
    sha, tag = _get_latest_release_sha("upstream/repo", gh_token=None)
    assert sha is None
    assert tag is None


@patch("scripts.security_scan.requests.get")
def test_get_latest_release_sha_returns_target_commitish_when_200(mock_get: MagicMock) -> None:
    """200 response → returns target_commitish + tag_name from JSON."""
    from scripts.security_scan import _get_latest_release_sha
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"target_commitish": "abc" * 13 + "d", "tag_name": "v1.2.3"},
    )
    sha, tag = _get_latest_release_sha("upstream/repo", gh_token="token")
    assert sha == "abc" * 13 + "d"
    assert tag == "v1.2.3"


def test_dispatch_scanner_unsupported_kind_returns_block(tmp_path: Path) -> None:
    """Unknown item kind → `block` finding listing the offending kind."""
    from scripts.security_scan import _dispatch_scanner
    item = {"id": "weird", "kind": "exotic-format"}
    report = _dispatch_scanner(item, tmp_path, vt_token=None)
    assert report.severity == "block"
    assert any("unsupported" in f.message for f in report.findings)


def test_run_increments_error_count_when_no_release_found(tmp_path: Path) -> None:
    """Upstream API returns None (e.g. no releases yet) → error_count++,
    no report emitted, no draft attempted."""
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: mcp-pack
    items:
      - id: context7
        upstream: upstash/context7
        sha: "abc123abc123abc123abc123abc123abc123abcd"
        license: MIT
        kind: skill
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    with patch("scripts.security_scan._get_latest_release_sha") as mock_sha, \
         patch("scripts.security_scan.draft_issue_and_pr") as mock_draft:
        mock_sha.return_value = (None, None)
        summary = run(catalog_path=p, output_dir=tmp_path, dry_run=True, gh_token="t")
    assert summary.report_count == 0
    assert summary.error_count == 1
    mock_draft.assert_not_called()


def test_run_skips_malformed_upstream(tmp_path: Path) -> None:
    """Items with a missing or malformed `upstream` (no slash) are skipped
    without incrementing error_count — they're catalog metadata bugs, not
    upstream-side failures."""
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: mcp-pack
    items:
      - id: context7
        upstream: norg
        sha: "abc123abc123abc123abc123abc123abc123abcd"
        license: MIT
        kind: skill
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    with patch("scripts.security_scan._get_latest_release_sha") as mock_sha:
        summary = run(catalog_path=p, output_dir=tmp_path, dry_run=True)
    assert summary.report_count == 0
    assert summary.error_count == 0
    mock_sha.assert_not_called()


def test_main_returns_zero_when_no_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI: empty catalog → exit 0."""
    from scripts.security_scan import main
    p = tmp_path / "catalog.yaml"
    p.write_text("plugins: []\n")
    monkeypatch.setattr("sys.argv", [
        "security_scan",
        "--catalog", str(p),
        "--output", str(tmp_path / "out"),
        "--dry-run",
    ])
    rc = main()
    assert rc == 0


def test_main_returns_one_when_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI: errors → exit 1 (for shell chaining in CI)."""
    from scripts.security_scan import main
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: mcp-pack
    items:
      - id: context7
        upstream: upstash/context7
        sha: "abc123abc123abc123abc123abc123abc123abcd"
        license: MIT
        kind: skill
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    monkeypatch.setattr("sys.argv", [
        "security_scan",
        "--catalog", str(p),
        "--output", str(tmp_path / "out"),
        "--dry-run",
    ])
    with patch("scripts.security_scan._get_latest_release_sha") as mock_sha:
        mock_sha.return_value = (None, None)  # upstream not found → error++
        rc = main()
    assert rc == 1


# ---------------------------------------------------------------------------
# Issue #33 — spec §8.7 false-positive suppression
# ---------------------------------------------------------------------------


@patch("scripts.security_scan._shallow_clone")
@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_applies_suppressions_to_finding_severity(
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    mock_clone: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
) -> None:
    """§8.7: a finding whose (scanner, rule_id) appears in catalog/reviews/*.md
    `<!-- suppress: ... -->` is downgraded to severity=info."""
    from scripts.security_scan import run
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    (reviews / "context7.md").write_text(
        "<!-- suppress: skillspector:prompt-injection -->\n"
    )
    mock_sha.return_value = ("a" * 40, "v1.0.0")
    mock_scan.return_value = ScannerReport(
        item_id="context7",
        scanner="skillspector",
        severity="block",
        findings=[
            Finding(
                path="SKILL.md",
                line=1,
                message="prompt injection",
                rule_id="prompt-injection",
            ),
        ],
    )
    summary = run(
        catalog_path=sample_catalog,
        output_dir=tmp_path / "out",
        dry_run=True,
        reviews_dir=reviews,
    )
    assert summary.report_count == 1
    report = json.loads(next((tmp_path / "out").glob("*.json")).read_text())
    assert report["severity"] == "info"
    assert report["findings"][0]["rule_id"] == "prompt-injection"
    assert "[suppressed]" in report["findings"][0]["message"]


# ---------------------------------------------------------------------------
# Issue #33 — spec §8.2 VirusTotal rate cap
# ---------------------------------------------------------------------------


@patch("scripts.security_scan._shallow_clone")
@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_mcp")
def test_run_skips_vt_when_cap_reached(
    mock_scan_mcp: MagicMock,
    mock_sha: MagicMock,
    mock_clone: MagicMock,
    tmp_path: Path,
) -> None:
    """§8.2: after vt_cap VT calls, subsequent MCP items scan with vt_token=None
    (soft-fail 'vt-skipped' rather than consuming the daily free tier)."""
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: mcp-pack
    items:
      - id: a
        upstream: org/a
        sha: "1111111111111111111111111111111111111111"
        kind: mcp
        vetting:
          status: approved
          date: 2026-08-04
      - id: b
        upstream: org/b
        sha: "2222222222222222222222222222222222222222"
        kind: mcp
        vetting:
          status: approved
          date: 2026-08-04
      - id: c
        upstream: org/c
        sha: "3333333333333333333333333333333333333333"
        kind: mcp
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    mock_sha.return_value = ("a" * 40, "v1.0.0")
    mock_scan_mcp.return_value = ScannerReport(
        item_id="x", scanner="mcp-combined", severity="clean"
    )
    mock_scan = mock_scan_mcp  # alias for clarity
    run(
        catalog_path=p,
        output_dir=tmp_path / "out",
        dry_run=True,
        vt_token="fake",
        vt_cap=2,
    )
    # scan_mcp called 3 times: first 2 with vt_token="fake", third with None.
    calls = mock_scan.call_args_list
    assert len(calls) == 3
    assert calls[0].kwargs.get("vt_token") == "fake"
    assert calls[1].kwargs.get("vt_token") == "fake"
    assert calls[2].kwargs.get("vt_token") is None


# ---------------------------------------------------------------------------
# Issue #33 — spec §8.4 state-recovery checkpoint
# ---------------------------------------------------------------------------


@patch("scripts.security_scan._shallow_clone")
@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_writes_checkpoint_after_each_item(
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    mock_clone: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
) -> None:
    """§8.4: after each processed item, the state file records its composite id."""
    mock_sha.return_value = ("a" * 40, "v1.0.0")
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    state_dir = tmp_path / "state"
    run(
        catalog_path=sample_catalog,
        output_dir=tmp_path / "out",
        dry_run=True,
        state_dir=state_dir,
    )
    state_files = list(state_dir.glob("security-scan-*.json"))
    assert len(state_files) == 1
    import json as _json
    data = _json.loads(state_files[0].read_text())
    assert data.get("mcp-pack/context7") == "done"


@patch("scripts.security_scan._shallow_clone")
@patch("scripts.security_scan._get_latest_release_sha")
@patch("scripts.security_scan.scan_skill")
def test_run_skips_items_already_in_checkpoint(
    mock_scan: MagicMock,
    mock_sha: MagicMock,
    mock_clone: MagicMock,
    sample_catalog: Path,
    tmp_path: Path,
) -> None:
    """§8.4: a second run with the same state file skips items marked done."""
    mock_sha.return_value = ("a" * 40, "v1.0.0")
    mock_scan.return_value = ScannerReport(
        item_id="context7", scanner="skillspector", severity="clean"
    )
    state_dir = tmp_path / "state"
    # Pre-populate the checkpoint as if a previous run already finished the item.
    import json as _json
    from datetime import date as _date
    state_file = state_dir / f"security-scan-{_date.today().isoformat()}.json"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(_json.dumps({"mcp-pack/context7": "done"}))
    summary = run(
        catalog_path=sample_catalog,
        output_dir=tmp_path / "out",
        dry_run=True,
        state_dir=state_dir,
    )
    assert summary.report_count == 0
    mock_scan.assert_not_called()
    mock_sha.assert_not_called()


def test_load_done_items_handles_missing_file(tmp_path: Path) -> None:
    from scripts.security_scan import _load_done_items
    assert _load_done_items(tmp_path / "missing.json") == set()


def test_load_done_items_handles_corrupt_file(tmp_path: Path) -> None:
    from scripts.security_scan import _load_done_items
    p = tmp_path / "state.json"
    p.write_text("{not json")
    assert _load_done_items(p) == set()
