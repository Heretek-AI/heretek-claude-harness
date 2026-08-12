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


# ---------------------------------------------------------------------------
# Issue #31 — coverage gap fills for scripts/catalog_updater.py (target ≥90%).
# ---------------------------------------------------------------------------


def test_bump_item_sha_rejects_short_sha(tmp_path: Path) -> None:
    """Non-40-char SHA → ValueError before any file I/O."""
    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    with pytest.raises(ValueError, match="40 chars"):
        bump_item_sha(p, "rust", "rust-analyzer", "tooshort", "2026-08-05")


def test_bump_item_sha_updates_cve_scan_when_provided(tmp_path: Path) -> None:
    """Optional cve_scan arg sets vetting.cve_scan to the given date."""
    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    bump_item_sha(p, "rust", "rust-analyzer", "0" * 40, "2026-08-05", cve_scan="2026-08-06")
    text = p.read_text()
    assert "cve_scan: 2026-08-06" in text


def test_bump_item_sha_skips_plugins_until_match(tmp_path: Path) -> None:
    """The internal loop scans all plugins; first non-matching plugin is skipped."""
    p = tmp_path / "catalog.yaml"
    p.write_text(
        """plugins:
  - name: js-ts
    items:
      - id: biome
        sha: "JS_TS_OLD_SHA_40_CHARS_LONG_xxxxxxxxxxxxx"
  - name: rust
    items:
      - id: rust-analyzer
        sha: "RUST_OLD_SHA_40_CHARS_LONG_xxxxxxxxxxxxxx"
        vetting:
          status: approved
          date: 2026-08-04
"""
    )
    bump_item_sha(p, "rust", "rust-analyzer", "0" * 40, "2026-08-05")
    text = p.read_text()
    # The js-ts item is untouched.
    assert "JS_TS_OLD_SHA_40_CHARS_LONG_xxxxxxxxxxxxx" in text
    # The rust item is updated.
    assert "0" * 40 in text


def test_main_returns_zero_on_success(tmp_path: Path) -> None:
    """CLI: success path returns exit 0."""
    from scripts.catalog_updater import main

    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    rc = main(
        [
            "--catalog",
            str(p),
            "--plugin",
            "rust",
            "--item",
            "rust-analyzer",
            "--sha",
            "0" * 40,
            "--vetting-date",
            "2026-08-05",
        ]
    )
    assert rc == 0


def test_main_returns_one_on_item_not_found(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """CLI: unknown item → stderr message + exit 1."""
    from scripts.catalog_updater import main

    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    rc = main(
        [
            "--catalog",
            str(p),
            "--plugin",
            "rust",
            "--item",
            "missing-item",
            "--sha",
            "0" * 40,
            "--vetting-date",
            "2026-08-05",
        ]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert "item not found" in captured.err


def test_module_entry_point_invokes_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m scripts.catalog_updater` dispatches to main() with sys.argv."""
    import runpy

    p = tmp_path / "catalog.yaml"
    p.write_text(SAMPLE)
    monkeypatch.setattr(
        "sys.argv",
        [
            "catalog_updater",
            "--catalog",
            str(p),
            "--plugin",
            "rust",
            "--item",
            "rust-analyzer",
            "--sha",
            "0" * 40,
            "--vetting-date",
            "2026-08-05",
        ],
    )
    # runpy dispatches to __name__ == "__main__" branch.
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("scripts.catalog_updater", run_name="__main__")
    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Issue #158 — list/empty-rooted catalog.yaml must fail cleanly (not via
# AttributeError) once the `isinstance(data, dict)` guard was added.
# ---------------------------------------------------------------------------


def test_bump_item_sha_rejects_non_dict_root(tmp_path: Path) -> None:
    """List-rooted YAML → ValueError (not AttributeError from data.get on list)."""
    p = tmp_path / "catalog.yaml"
    p.write_text("- a\n- b\n")
    with pytest.raises(ValueError, match="catalog.yaml root must be a dict"):
        bump_item_sha(p, "rust", "rust-analyzer", "0" * 40, "2026-08-05")
    # Guard fires before _apply_item_updates, so no .tmp sidecar is ever opened.
    assert not (tmp_path / "catalog.yaml.tmp").exists()


def test_bump_item_sha_rejects_empty_file(tmp_path: Path) -> None:
    """Empty file → ValueError (ruamel returns None for empty input)."""
    p = tmp_path / "catalog.yaml"
    p.write_text("")
    with pytest.raises(ValueError, match="catalog.yaml root must be a dict"):
        bump_item_sha(p, "rust", "rust-analyzer", "0" * 40, "2026-08-05")
    assert not (tmp_path / "catalog.yaml.tmp").exists()
