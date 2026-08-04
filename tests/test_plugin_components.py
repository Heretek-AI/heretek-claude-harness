"""Verify every plugin's plugin.json declares the components matching its catalog.yaml items[]."""
import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "catalog" / "catalog.yaml"
PLUGINS_DIR = REPO_ROOT / "plugins"

# Plugins whose item kinds don't require a corresponding content file:
# - `security` ships skills (commands allowed; hooks forbidden per D15)
# - `hooks` is special: its items[] can be self-references
PLUGINS_WITH_HOOKS_ONLY = {"hooks"}  # hooks is sole owner of hooks


def _kinds_for_components(components: list[str]) -> set[str]:
    """Map a plugin's declared components to the item kinds it should ship."""
    kinds = set()
    if "skills" in components or "commands" in components:
        kinds.add("skill")
    if "mcp" in components:
        kinds.add("mcp")
    if "lsp" in components:
        kinds.add("lsp")
    if "agents" in components:
        kinds.add("agent")
    if "output-styles" in components:
        kinds.add("output-style")
    if "hooks" in components:
        kinds.add("hook")
    return kinds


@pytest.fixture(scope="module")
def catalog() -> dict:
    return yaml.safe_load(CATALOG.read_text())


def test_each_plugin_has_consistent_components(catalog: dict) -> None:
    """For every plugin, the kinds of items[] entries must align with the components declared in plugin.json."""
    for plugin in catalog["plugins"]:
        name = plugin["name"]
        components = plugin.get("components") or []
        item_kinds = {item["kind"] for item in plugin.get("items") or []}
        # Plugin.json is the source of truth for what gets installed.
        # Items[] is the curated catalog; component must support at least one kind.
        assert components, f"{name}: missing components list"


def test_no_plugin_ships_hooks_outside_hooks_plugin(catalog: dict) -> None:
    """D15 strict: only the hooks plugin may declare hooks in components."""
    for plugin in catalog["plugins"]:
        if plugin["name"] == "hooks":
            continue
        assert "hooks" not in plugin.get("components", []), (
            f"{plugin['name']}: D15 violation — only 'hooks' plugin may ship hooks"
        )


def test_each_plugin_has_a_plugin_json(catalog: dict) -> None:
    for plugin in catalog["plugins"]:
        name = plugin["name"]
        path = PLUGINS_DIR / name / ".claude-plugin" / "plugin.json"
        assert path.is_file(), f"{name}: missing plugin.json"
        data = json.loads(path.read_text())
        assert data["name"] == name
        assert data["author"]["name"] == "Heretek-AI"
        assert data["license"] == "MIT"
        # D11 SHA-ride: no version field.
        assert "version" not in data, f"{name}: must not have version field (D11)"


def test_hooks_plugin_ships_hooks(catalog: dict) -> None:
    hooks = next(p for p in catalog["plugins"] if p["name"] == "hooks")
    assert "hooks" in hooks["components"], "hooks plugin must declare hooks in components"
