"""Verify the GH Action workflow has required concurrency + permissions blocks."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "terminal-bench-ab.yml"
)


def _load_workflow() -> dict:
    assert WORKFLOW_PATH.exists(), f"missing {WORKFLOW_PATH}"
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def _on_key(workflow: dict):
    """YAML's `on` key parses as Python boolean True; handle both forms."""
    return True if True in workflow else "on"


def test_workflow_file_exists() -> None:
    assert WORKFLOW_PATH.exists(), f"missing {WORKFLOW_PATH}"


def test_workflow_has_concurrency_group() -> None:
    workflow = _load_workflow()
    # concurrency is top-level (sibling of on:, not nested inside it).
    concurrency = workflow.get("concurrency")
    assert concurrency is not None, "workflow must have top-level concurrency block"
    assert concurrency["group"] == "terminal-bench-ab"
    assert concurrency["cancel-in-progress"] is True


def test_workflow_has_required_permissions() -> None:
    workflow = _load_workflow()
    # permissions is top-level too.
    perms = workflow.get("permissions", {})
    assert perms.get("contents") == "read"
    assert perms.get("issues") == "write"
    assert perms.get("actions") == "write", "actions: write required for actions/upload-artifact@v4"


def test_workflow_triggers_on_push_to_main() -> None:
    workflow = _load_workflow()
    triggers = workflow[_on_key(workflow)]
    push = triggers.get("push")
    assert push is not None
    assert "main" in push["branches"]


def test_workflow_supports_workflow_dispatch() -> None:
    workflow = _load_workflow()
    triggers = workflow[_on_key(workflow)]
    assert "workflow_dispatch" in triggers
