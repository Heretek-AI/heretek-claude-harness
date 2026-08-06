"""Regression test for #15 — cargo-clippy skill file must exist."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "plugins" / "rust" / "skills" / "cargo-clippy" / "SKILL.md"


def test_cargo_clippy_skill_exists() -> None:
    assert SKILL_PATH.exists(), (
        f"{SKILL_PATH.relative_to(REPO_ROOT)} missing — catalog declares cargo-clippy "
        f"but the skill file is absent (#15)"
    )


def test_cargo_clippy_skill_has_frontmatter() -> None:
    """SKILL.md starts with `---` and has `name` + `description` keys."""
    text = SKILL_PATH.read_text()
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    # Strip frontmatter and check the body has at least one section.
    body = text.split("---\n", 2)[2]
    assert "##" in body, "SKILL.md body must contain at least one section"


def test_catalog_declares_cargo_clippy() -> None:
    """catalog/catalog.yaml declares cargo-clippy under the rust plugin."""
    import yaml

    data = yaml.safe_load((REPO_ROOT / "catalog" / "catalog.yaml").read_text())
    rust = next(p for p in data["plugins"] if p["name"] == "rust")
    ids = {it["id"] for it in rust["items"]}
    assert "cargo-clippy" in ids, "rust plugin must declare cargo-clippy"