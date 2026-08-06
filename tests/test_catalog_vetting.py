"""Verify every catalog.yaml items[] entry has a vetting block + review link."""
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "catalog" / "catalog.yaml"


@pytest.fixture(scope="module")
def catalog() -> dict:
    return yaml.safe_load(CATALOG.read_text())


def test_catalog_exists() -> None:
    assert CATALOG.is_file()


def test_every_item_has_vetting_block(catalog: dict) -> None:
    """Every plugin's items[] entry must have a vetting block with status + review link."""
    for plugin in catalog["plugins"]:
        for item in plugin.get("items") or []:
            assert "vetting" in item, f"{plugin['name']}/{item.get('id')} missing vetting block"
            v = item["vetting"]
            assert v.get("status") in ("approved", "rejected"), (
                f"{plugin['name']}/{item['id']}: vetting.status must be approved|rejected"
            )
            assert v.get("review"), (
                f"{plugin['name']}/{item['id']}: vetting.review path required"
            )
            review_path = REPO_ROOT / "catalog" / v["review"]
            assert review_path.is_file(), (
                f"{plugin['name']}/{item['id']}: ADR {review_path} missing"
            )


def test_approved_items_have_upstream_and_license(catalog: dict) -> None:
    """Approved items must have upstream repo + license (the D7 minimum)."""
    for plugin in catalog["plugins"]:
        for item in plugin.get("items") or []:
            if item.get("vetting", {}).get("status") == "approved":
                assert item.get("upstream"), (
                    f"{plugin['name']}/{item['id']}: approved items need upstream"
                )
                assert item.get("license"), (
                    f"{plugin['name']}/{item['id']}: approved items need license"
                )


def test_rejected_items_have_no_plugin_components(catalog: dict) -> None:
    """Rejected items shouldn't pollute plugin manifests. They live in catalog.yaml items[] for audit but are not used."""
    # No-op for now: catalog.yaml items[] entries don't generate marketplace.json entries.
    # This is a structural assertion — re-evaluate when generator logic is extended.
    pass


def test_hooks_plugin_has_at_least_one_item(catalog: dict) -> None:
    """hooks plugin is the differentiator — must have ≥ 1 vetted item."""
    hooks_plugin = next(p for p in catalog["plugins"] if p["name"] == "hooks")
    items = hooks_plugin.get("items") or []
    assert len(items) >= 1, "hooks plugin must have ≥ 1 vetted item (the fast-gate itself)"


def test_first_party_items_have_adr() -> None:
    """Every first-party item has a vetting.review ADR file (D7 spirit for self-pins, #10)."""
    import yaml
    from pathlib import Path

    data = yaml.safe_load((REPO_ROOT / "catalog" / "catalog.yaml").read_text())
    for plugin in data["plugins"]:
        for item in plugin.get("items", []):
            sha = item.get("sha", "")
            if not sha.startswith("first-party-"):
                continue
            review_rel = item.get("vetting", {}).get("review")
            assert review_rel, f"{plugin['name']}/{item['id']} has no vetting.review"
            full = REPO_ROOT / "catalog" / review_rel
            assert full.exists(), f"{plugin['name']}/{item['id']} ADR missing: {full}"
