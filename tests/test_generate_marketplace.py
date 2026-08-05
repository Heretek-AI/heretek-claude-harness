"""Tests for scripts/generate_marketplace.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_marketplace  # noqa: E402


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_generate_empty_catalog(tmp_path: Path, fixtures_dir: Path) -> None:
    catalog = fixtures_dir / "catalog" / "empty.yaml"
    out = tmp_path / "marketplace.json"
    result = generate_marketplace.generate(catalog, out)
    assert result["name"] == "empty-test"
    assert result["plugins"] == []
    assert out.is_file()
    on_disk = json.loads(out.read_text())
    assert on_disk == result


def test_generate_single_plugin(tmp_path: Path, fixtures_dir: Path) -> None:
    catalog = fixtures_dir / "catalog" / "single_plugin.yaml"
    out = tmp_path / "marketplace.json"
    result = generate_marketplace.generate(catalog, out)
    assert result["name"] == "single-test"
    assert len(result["plugins"]) == 1
    plugin = result["plugins"][0]
    assert plugin["name"] == "alpha"
    assert plugin["source"] == "./plugins/alpha"  # relative source becomes ./<pluginRoot>/<path>
    assert plugin["category"] == "task"
    assert plugin["tags"] == ["example"]


def test_generate_is_idempotent(tmp_path: Path, fixtures_dir: Path) -> None:
    """Running the generator twice must produce identical output."""
    catalog = fixtures_dir / "catalog" / "single_plugin.yaml"
    out = tmp_path / "marketplace.json"
    first = generate_marketplace.generate(catalog, out)
    second = generate_marketplace.generate(catalog, out)
    assert first == second


def test_generate_strips_internal_fields(tmp_path: Path, fixtures_dir: Path) -> None:
    """catalog.yaml-only fields like 'components' must not appear in marketplace.json."""
    catalog = fixtures_dir / "catalog" / "single_plugin.yaml"
    out = tmp_path / "marketplace.json"
    result = generate_marketplace.generate(catalog, out)
    plugin = result["plugins"][0]
    assert "components" not in plugin
    assert "items" not in plugin


def test_generate_3rd_party_source_object_preserved(
    tmp_path: Path, fixtures_dir: Path
) -> None:
    """3rd-party source objects with sha pins must be preserved as-is."""
    _write(
        tmp_path / "catalog.yaml",
        """\
marketplace:
  name: t
  description: t
  owner:
    name: t
plugins:
  - name: third
    category: community
    tags: [3rd-party]
    source:
      type: git-subdir
      url: https://github.com/acme/monorepo.git
      path: tools/p
      sha: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
    components: []
    items: []
""",
    )
    out = tmp_path / "marketplace.json"
    result = generate_marketplace.generate(tmp_path / "catalog.yaml", out)
    plugin = result["plugins"][0]
    assert plugin["source"] == {
        "source": "git-subdir",
        "url": "https://github.com/acme/monorepo.git",
        "path": "tools/p",
        "sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    }


def test_main_writes_and_exits_zero(
    tmp_path: Path, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = fixtures_dir / "catalog" / "empty.yaml"
    out = tmp_path / "marketplace.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_marketplace.py", "--catalog", str(catalog), "--output", str(out)],
    )
    assert generate_marketplace.main() == 0
    assert out.is_file()
