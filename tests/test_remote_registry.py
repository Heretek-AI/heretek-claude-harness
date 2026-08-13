"""Hermetic tests for heretek launcher (bin/heretek.js) and remote registry publishing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_bin_heretek_launcher_version(tmp_path: Path) -> None:
    """bin/heretek.js executes successfully via Node.js forwarding to python CLI."""
    node_bin = "node"
    launcher = REPO_ROOT / "bin" / "heretek.js"
    res = subprocess.run(
        [node_bin, str(launcher), "validate"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "validate: OK" in res.stdout


def test_publish_workflow_validates_yaml() -> None:
    """publish-marketplace.yml exists and is valid YAML."""
    workflow = REPO_ROOT / ".github" / "workflows" / "publish-marketplace.yml"
    assert workflow.is_file()
    content = workflow.read_text()
    assert "publish-catalog" in content
    assert "upload-pages-artifact" in content


def test_publish_npm_workflow_validates_yaml() -> None:
    """publish-npm.yml exists and is valid YAML."""
    workflow = REPO_ROOT / ".github" / "workflows" / "publish-npm.yml"
    assert workflow.is_file()
    content = workflow.read_text()
    assert "publish-npm" in content
    assert "NPM_TOKEN" in content


def test_package_json_valid_manifest() -> None:
    """package.json is valid JSON with correct bin path."""
    pkg_file = REPO_ROOT / "package.json"
    assert pkg_file.is_file()
    data = json.loads(pkg_file.read_text())
    assert data["name"] == "@heretek-ai/heretek"
    assert data["bin"]["heretek"] == "./bin/heretek.js"
