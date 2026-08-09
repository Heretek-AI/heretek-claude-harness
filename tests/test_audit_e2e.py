"""End-to-end test: fixture cluster results -> synthesize -> build-issues -> payload sanity."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import findings, harness_self, issues, synthesis, validate  # noqa: E402


@pytest.fixture(autouse=True)
def _set_schema(schemas_dir: Path) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "audit" / "cluster_results"


def test_e2e_synthesize_then_build_issues(tmp_path: Path) -> None:
    """Run the full pipeline against fixture cluster results."""
    # Step 1: synthesize
    result = synthesis.synthesize(
        cluster_results_dir=FIXTURES,
        output_dir=tmp_path / "out",
        commit_sha="e2etest0",
    )
    assert len(result.findings) == 3
    # Verify the report mentions the snapshot SHA.
    md = result.report_path.read_text()
    assert "e2etest0" in md
    assert "Critical: 1" in md
    assert "High: 1" in md
    assert "Medium: 1" in md

    # Step 2: build-issues (via the synthesis JSON)
    fs = [
        findings.Finding.from_dict(d) for d in json.loads(result.json_path.read_text())
    ]
    payloads = issues.build_issue_payloads(fs)
    # 1 critical + 1 high -> 2 issues; medium excluded.
    assert len(payloads) == 2
    titles = {p.title for p in payloads}
    assert any("Small, focused functions" in t for t in titles)
    assert any("Single Responsibility" in t for t in titles)


def test_e2e_run_all_via_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Call the driver's synthesize subcommand end-to-end via the CLI."""
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_self.py",
            "synthesize",
            "--cluster-results",
            str(FIXTURES),
            "--output-dir",
            str(out_dir),
            "--commit-sha",
            "e2etest1",
        ],
    )
    assert harness_self.main() == 0
    assert any(out_dir.glob("audit-harness-self-*.md"))
    assert any(out_dir.glob("audit-harness-self-*.json"))


def test_e2e_emit_prompts_then_synthesize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """emit-prompts + synthesize via the driver."""
    prompts_dir = tmp_path / "prompts"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_self.py",
            "emit-prompts",
            "--repo-root",
            str(tmp_path),
            "--commit-sha",
            "e2etest2",
            "--out-dir",
            str(prompts_dir),
        ],
    )
    assert harness_self.main() == 0
    for letter in ("A", "B", "C", "D", "E"):
        assert (prompts_dir / f"{letter}.txt").is_file()
    assert "Readability" in (prompts_dir / "A.txt").read_text()
