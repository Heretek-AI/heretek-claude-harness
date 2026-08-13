"""Tests for the seed loader (schema validation + body markdown emitter)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.lib.seed_loader import (
    SeedValidationError,
    emit_body_markdown,
    load_seed,
    validate_issue,
)

LABELS = {
    "phase": [
        "phase/1-ci-setup",
        "phase/2-cli-runtime",
        "phase/3-webui",
        "phase/4-matrix-pkg",
        "phase/meta",
    ],
    "component": [
        "component/ci",
        "component/manifest",
        "component/auditor",
        "component/symlink",
        "component/upstream-sync",
        "component/webui",
        "component/api",
        "component/store",
        "component/infra",
        "component/manager",
        "component/docs",
    ],
    "status": [
        "status/backlog",
        "status/in-progress",
        "status/blocked",
        "status/review",
        "status/done",
    ],
}
ALL_LABELS = [label for axis in LABELS.values() for label in axis]


def _good_issue() -> dict:
    return {
        "id": "lb-0001",
        "title": "Set up CI matrix",
        "phase": "phase/1-ci-setup",
        "component": "component/ci",
        "status": "status/backlog",
        "source": {"doc": "design.md", "section": "§2.1"},
        "goal": "Create the matrix workflow skeleton.",
        "acceptance": ["Workflow file committed", "Runs on pull_request"],
        "out_of_scope": ["Real matrix entries"],
        "depends_on": [],
    }


def _write_seed(tmp_path: Path, seed: dict) -> Path:
    path = tmp_path / "seed.yaml"
    path.write_text(json.dumps(seed))
    return path


def test_validate_issue_accepts_well_formed_issue():
    assert validate_issue(_good_issue(), ALL_LABELS) == []


def test_validate_issue_rejects_unknown_phase_label():
    issue = _good_issue()
    issue["phase"] = "phase/9-future"
    errors = validate_issue(issue, ALL_LABELS)
    assert any("phase" in e for e in errors)


def test_validate_issue_rejects_bad_id_format():
    issue = _good_issue()
    issue["id"] = "LB-1"
    errors = validate_issue(issue, ALL_LABELS)
    assert any("id" in e for e in errors)


def test_validate_issue_rejects_empty_acceptance():
    issue = _good_issue()
    issue["acceptance"] = []
    errors = validate_issue(issue, ALL_LABELS)
    assert any("acceptance" in e for e in errors)


def test_validate_issue_rejects_depends_on_unknown_id(tmp_path: Path):
    seed = {
        "schema_version": 1,
        "repo": "Heretek-AI/llama-builds",
        "project_id": "",
        "issues": [_good_issue()],
    }
    seed["issues"][0]["depends_on"] = ["lb-9999"]
    seed_path = _write_seed(tmp_path, seed)
    with pytest.raises(SeedValidationError) as exc:
        load_seed(str(seed_path), known_labels=ALL_LABELS)
    assert "lb-9999" in str(exc.value)


def test_emit_body_markdown_contains_all_five_sections():
    body = emit_body_markdown(_good_issue())
    for section in (
        "## Source",
        "## Goal",
        "## Acceptance criteria",
        "## Out of scope",
        "## Dependencies",
    ):
        assert section in body
    assert "<!-- seed-id: lb-0001 -->" in body.splitlines()[0]


def test_load_seed_raises_seed_validation_error_on_malformed_yaml(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    # Indentation/structure makes this malformed YAML (PyYAML scanner error).
    bad.write_text("not: a: real: seed\n  - mixed: indent\n  oops: : :\n")
    with pytest.raises(SeedValidationError) as exc:
        load_seed(str(bad), known_labels=ALL_LABELS)
    assert "invalid YAML" in str(exc.value)


def test_seed_loader_cli_validate_exits_nonzero_on_missing_schema():
    bad = Path("/tmp/__no_such_schema__.yaml")
    bad.write_text("not: a: real: seed\n")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.lib.seed_loader", "validate", str(bad)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_load_seed_raises_seed_validation_error_on_invalid_label(tmp_path: Path):
    """load_seed must call validate_issue for each issue, catching unknown labels."""
    seed = {
        "schema_version": 1,
        "repo": "Heretek-AI/llama-builds",
        "project_id": "",
        "issues": [dict(_good_issue(), phase="phase/9-future")],
    }
    seed_path = _write_seed(tmp_path, seed)
    with pytest.raises(SeedValidationError) as exc:
        load_seed(str(seed_path), known_labels=ALL_LABELS)
    assert "phase/9-future" in str(exc.value)
    assert "lb-0001" in str(exc.value)


def test_load_seed_raises_seed_validation_error_on_duplicate_ids(tmp_path: Path):
    """load_seed must detect duplicate ids before dependency validation."""
    seed = {
        "schema_version": 1,
        "repo": "Heretek-AI/llama-builds",
        "project_id": "",
        "issues": [_good_issue(), _good_issue()],
    }
    seed_path = _write_seed(tmp_path, seed)
    with pytest.raises(SeedValidationError) as exc:
        load_seed(str(seed_path), known_labels=ALL_LABELS)
    assert "duplicate issue ids" in str(exc.value)
    assert "lb-0001" in str(exc.value)


def test_load_seed_per_issue_validation_runs_before_dep_validation(tmp_path: Path):
    """Per-issue validation errors must surface even when deps are also broken."""
    issue = _good_issue()
    issue["phase"] = "phase/9-future"  # unknown label
    issue["depends_on"] = ["lb-9999"]  # dangling dep
    seed = {
        "schema_version": 1,
        "repo": "Heretek-AI/llama-builds",
        "project_id": "",
        "issues": [issue],
    }
    seed_path = _write_seed(tmp_path, seed)
    with pytest.raises(SeedValidationError) as exc:
        load_seed(str(seed_path), known_labels=ALL_LABELS)
    # Per-issue error mentioned (validate_issue is now wired in)
    assert "phase" in str(exc.value)


def test_load_seed_accepts_a_well_formed_seed(tmp_path: Path):
    """load_seed returns the parsed seed dict when every issue is valid."""
    seed = {
        "schema_version": 1,
        "repo": "Heretek-AI/llama-builds",
        "project_id": "",
        "issues": [_good_issue()],
    }
    seed_path = _write_seed(tmp_path, seed)
    result = load_seed(str(seed_path), known_labels=ALL_LABELS)
    assert result["schema_version"] == 1
    assert result["repo"] == "Heretek-AI/llama-builds"
    assert result["issues"][0]["id"] == "lb-0001"


def test_load_seed_loads_canonical_labels_from_sibling_labels_yaml(tmp_path: Path):
    """Without an explicit known_labels, loader finds labels.yaml next to the seed."""
    labels_yaml = tmp_path / "labels.yaml"
    labels_yaml.write_text(
        "schema_version: 1\n"
        "labels:\n"
        "  - name: phase/1-ci-setup\n"
        "    color: '0E8A16'\n"
        "    description: x\n"
        "  - name: component/ci\n"
        "    color: 'D4C5F9'\n"
        "    description: x\n"
        "  - name: status/backlog\n"
        "    color: 'BFBFBF'\n"
        "    description: x\n"
    )
    seed_path = _write_seed(
        tmp_path,
        {
            "schema_version": 1,
            "repo": "Heretek-AI/llama-builds",
            "project_id": "",
            "issues": [_good_issue()],
        },
    )
    result = load_seed(str(seed_path))
    assert result["issues"][0]["id"] == "lb-0001"


def test_load_seed_loads_canonical_labels_from_repo_umbrella_when_no_sibling(tmp_path: Path):
    """Without a sibling labels.yaml, loader falls back to the umbrella's labels."""
    # The tmp_path has no labels.yaml; the loader should fall back to the umbrella's
    # seeds/labels.yaml file (which is the canonical location) and succeed.
    seed_path = _write_seed(
        tmp_path,
        {
            "schema_version": 1,
            "repo": "Heretek-AI/llama-builds",
            "project_id": "",
            "issues": [_good_issue()],
        },
    )
    result = load_seed(str(seed_path))
    assert result["issues"][0]["id"] == "lb-0001"
