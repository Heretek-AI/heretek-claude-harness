"""Round-trip tests for the catalog updater. Comments and key order MUST
be preserved — PyYAML loses them, so we use ruamel.yaml."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.catalog_updater import bump_item_sha


SAMPLE = """# heretek marketplace — source of truth.
# Generated from this file by scripts/generate_marketplace.py; do NOT
# hand-edit .claude-plugin/marketplace.json (it's regenerated).

marketplace:
  name: heretek

plugins:
  - name: rust
    items:
      - id: rust-analyzer
        sha: "OLD_SHA_40_CHARS_LONG_xxxxxxxxxxxx"
        vetting:
          status: approved
          date: 2026-08-04
          cve_scan: 2026-08-04
"""


def test_bump_item_sha_updates_sha(tmp_path: Path) -> None:
    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    new_sha = "0" * 40
    bump_item_sha(p, "rust", "rust-analyzer", new_sha, "2026-08-05")
    text = p.read_text()
    assert new_sha in text
    assert "OLD_SHA_40_CHARS_LONG_xxxxxxxxxxxx" not in text
    assert "date: 2026-08-05" in text


def test_bump_item_sha_preserves_comments(tmp_path: Path) -> None:
    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    bump_item_sha(p, "rust", "rust-analyzer", "0" * 40, "2026-08-05")
    text = p.read_text()
    assert "# heretek marketplace — source of truth." in text
    assert "# Generated from this file by scripts/generate_marketplace.py" in text


def test_bump_item_sha_preserves_marketplace_block(tmp_path: Path) -> None:
    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    bump_item_sha(p, "rust", "rust-analyzer", "0" * 40, "2026-08-05")
    text = p.read_text()
    assert "marketplace:" in text
    assert "name: heretek" in text


def test_bump_item_sha_atomic_write(tmp_path: Path) -> None:
    """No leftover .tmp files after a successful bump."""
    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    bump_item_sha(p, "rust", "rust-analyzer", "0" * 40, "2026-08-05")
    assert not (tmp_path / "catalog.yaml.tmp").exists()


def test_bump_item_sha_raises_for_unknown_item(tmp_path: Path) -> None:
    from scripts.catalog_updater import ItemNotFound
    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    with pytest.raises(ItemNotFound):
        bump_item_sha(p, "rust", "nonexistent-item", "0" * 40, "2026-08-05")