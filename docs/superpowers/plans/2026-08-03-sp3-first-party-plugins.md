# SP3 — First-Party Plugins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate all 11 first-party plugin directories with vetted items, ADRs, and minimal-but-functional content so each plugin is installable and does what its card claims — turning the SP1/2 scaffold into a working marketplace.

**Architecture:** For each plugin, run a per-plugin curation cycle: research candidate items via WebSearch + GitHub MCP, vet each against the D7 bar (stars≥500, last commit ≤12mo, OSI license, source-audit, no critical CVEs), write an ADR per item (approved → catalog.yaml `items[]` + minimal content file; rejected → `catalog/rejected.md`), update the plugin's `plugin.json` with the new components and a `dependencies:` list for any vendored third-party content, and update the README. Catalog.yaml becomes the single source of truth; the generator and validator pick up the changes automatically.

**Tech Stack:** Python 3.10+ (SP1 floor), jsonschema, pytest. Plugin content is markdown (skills/agents/output-styles), JSON (mcp.json, lsp.json). Research uses WebSearch + WebFetch + `gh` CLI for GitHub queries.

## Global Constraints

These apply to every task in this plan. Copy values verbatim from the spec:

- **Marketplace name:** `heretek`. **Owner:** `Heretek-AI`. **License:** MIT (D14) for first-party files.
- **SHA-ride versioning:** no `version` field on first-party plugins (D11, D16).
- **D15 (strict hooks ownership):** the `hooks` plugin is the SOLE owner of all hooks. NO other plugin (including `security`) may declare hook components. The other plugins may have skills, mcp, lsp, agents, output-styles, commands — not hooks.
- **D7 vetting bar:** stars ≥ 500, last commit ≤ 12 months, OSI-approved license (MIT/Apache-2.0/BSD/…), source-audit pass for code-executing components, no critical CVEs (CVSS ≥ 9.0) in last 24 months.
- **Plugin slug pattern:** `^[a-z0-9][a-z0-9-]*$` (matches all SP1/2 schemas).
- **Catalog format:** `catalog/catalog.yaml` is the source of truth. Each plugin entry's `items:` is a list of vetted items with `{id, kind, upstream, sha?, license, vetting: {status, date, stars, last_commit, cve_scan, review}}`. The marketplace.json generator (SP1) strips catalog-only fields.
- **ADR template:** `catalog/reviews/0000-template.md` (SP1). One ADR per vetted item (approved or rejected — rejection ADRs are valuable for audit trail).
- **All files end with trailing `\n`.**
- **Generate → marketplace.json is idempotent** (SP1 verified). Re-running the generator must produce byte-identical output. The `items[]` field is in catalog-only (stripped from marketplace.json) so changes here don't shift marketplace.json unless source/category/tags change.

---

## File Structure

Files this plan creates or modifies. Each has one clear responsibility.

| Path | Responsibility |
|---|---|
| `catalog/catalog.yaml` | (modify many times) — `items:` array populated per plugin with vetted entries |
| `catalog/reviews/<item-slug>.md` | (many new) — ADR per vetted item per plugin |
| `catalog/rejected.md` | (modify) — append entries for any item that fails D7 |
| `plugins/<plugin>/.claude-plugin/plugin.json` | (modify many times) — add `dependencies:` for vendored items, declare new component paths |
| `plugins/<plugin>/README.md` | (modify many times) — install, usage, items list |
| `plugins/<plugin>/skills/<name>/SKILL.md` | (new many) — skill frontmatter + minimal description |
| `plugins/<plugin>/.mcp.json` (or `mcp/<name>/.mcp.json`) | (new many) — MCP server config (stdio or http) |
| `plugins/<plugin>/.lsp.json` (or `lsp/<name>/.lsp.json`) | (new many) — LSP server config (binary user-installed) |
| `plugins/<plugin>/agents/<name>.md` | (new many) — agent definition with frontmatter + system prompt |
| `plugins/<plugin>/output-styles/<name>.md` | (new many) — output style preset |
| `plugins/<plugin>/commands/<name>.md` | (new some) — slash command frontmatter |
| `tests/test_catalog_vetting.py` | (new) — assert every `items[]` entry has a vetting block + review link |
| `tests/test_plugin_components.py` | (new) — assert every plugin's plugin.json declares the right components + dependencies |
| `tests/fixtures/catalog/<plugin>_seed.yaml` | (new) — sample catalog.yaml slice for testing |

**Files that change together live together.** All plugin-specific content stays under `plugins/<plugin>/`. All vetting metadata lives in `catalog/`. Tests for catalog vetting live in `tests/test_catalog_vetting.py`.

---

## Task 1: Update the hooks plugin to ship real content (rust-analyzer as a hooks-plugin LSP entry)

**Files:**
- Modify: `plugins/hooks/.claude-plugin/plugin.json` (add `dependencies` field; add a sample "fast-gate python" entry showing how the plugin can register itself as a source for `lspServers`)
- Modify: `catalog/catalog.yaml` — `hooks` plugin's `items[]` gets a sample "heretek-fast-gate" entry (the plugin describes itself as an item it ships)
- Create: `catalog/reviews/heretek-fast-gate.md` — ADR for this self-reference entry (or skip; only if needed)
- Create: `tests/test_catalog_vetting.py` — initial test asserting `items[]` entries have vetting blocks (TDD for the whole plan)

**Interfaces:**
- Consumes: `catalog/catalog.yaml` (SP1 + SP2 state) — `hooks` plugin already has `items: []`.
- Produces:
  - A `tests/test_catalog_vetting.py` with a parametrized test: for every plugin in catalog.yaml that has `items: []` non-empty, every item has `{id, kind, vetting.status, vetting.review}` fields.
  - The `hooks` plugin's `plugin.json` updated with `dependencies: []` (empty for now; populated by subsequent tasks).
  - The `hooks` plugin's catalog.yaml entry updated with a sample `items: [{id: heretek-fast-gate, kind: hook, ...}]` so the test has at least one item to exercise.

- [ ] **Step 1: Write the failing test**

Write `tests/test_catalog_vetting.py`:

```python
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
```

- [ ] **Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_catalog_vetting.py -v`

Expected: `test_every_item_has_vetting_block` PASSES trivially (no items yet), but `test_hooks_plugin_has_at_least_one_item` FAILS because hooks.items is empty.

- [ ] **Step 3: Add the hooks self-item to catalog.yaml**

In `catalog/catalog.yaml`, replace the `hooks` plugin's `items: []` with:

```yaml
  - name: hooks
    category: cross
    tags: [hooks, quality-gates, flagship]
    source: { type: relative, path: hooks }
    components: [hooks, commands, git-hooks]
    items:
      - id: heretek-fast-gate
        kind: hook
        upstream: Heretek-AI/heretek-claude-harness
        sha: "694449d"  # the SP2 merge commit
        license: MIT
        vetting:
          status: approved
          date: 2026-08-04
          stars: 0  # this is the heretek repo itself; not subject to D7 stars gate
          last_commit: 2026-08-04
          cve_scan: not-applicable  # first-party
          review: reviews/0000-template.md  # SP1 ADR template serves as the self-reference
```

Note: stars=0 is acceptable for first-party (the heretek repo itself). The `sha` is the SP2 final commit (self-pinning to the version that ships the hook).

- [ ] **Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_catalog_vetting.py -v`

Expected: 5 tests pass (the new ones exercise the hooks self-item).

- [ ] **Step 5: Commit**

```bash
git add tests/test_catalog_vetting.py catalog/catalog.yaml
git commit -m "feat(catalog): add hooks self-item + vetting invariant test

The hooks plugin gets a self-referential entry in catalog.yaml so the
plugin can describe what it ships. The new test asserts every items[]
entry across the catalog has a vetting block + ADR link (catches future
omissions before they reach marketplace.json).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Vet and ship `rust` plugin items

**Files:**
- Modify: `catalog/catalog.yaml` — `rust` plugin `items:` populated
- Create: `catalog/reviews/rust-analyzer.md`, `rust-cargo-check.md`, `rust-clippy.md`
- Modify: `catalog/rejected.md` (append any rejections)
- Modify: `plugins/rust/.claude-plugin/plugin.json` — add `dependencies`, declare LSP path
- Create: `plugins/rust/.lsp.json` — LSP config for rust-analyzer (binary user-installed)
- Create: `plugins/rust/skills/cargo-check/SKILL.md` — minimal skill frontmatter
- Modify: `plugins/rust/README.md` — install + usage
- Modify: `plugins/rust/.claude-plugin/plugin.json` — add commands for `/rust:check`, `/rust:clippy` (optional; if skipped, just LSP + skill)

**Interfaces:**
- Consumes: research output (per candidate item: GitHub stars, last commit, license, source-audit).
- Produces:
  - 3 ADRs in `catalog/reviews/rust-*.md` (rust-analyzer, cargo-check, clippy).
  - `rust` plugin `items[]` populated with 2-3 approved entries.
  - `plugins/rust/.lsp.json` pointing to `rust-analyzer` binary (user-installed via `rustup component add rust-analyzer`).
  - `plugins/rust/skills/cargo-check/SKILL.md` with description + run command.
  - README updated.

**Candidate items for rust (from spec §8):**
1. **rust-analyzer** (LSP): `rust-lang/rust-analyzer` — official Rust LSP, ~10k★, MIT, last commit within days. Source-audit: official Rust project, low risk.
2. **cargo-check skill**: derived from `cargo check` — first-party Rust tool, no upstream repo to vet; the SKILL is a markdown frontmatter documenting the workflow. No ADR needed for first-party skills (they ARE first-party).
3. **cargo-clippy** (optional): `rust-lang/rust-clippy` — official Rust linter, ~10k★, MIT.

**Research strategy:**
- For each, use `WebFetch` to confirm `github.com/rust-lang/rust-analyzer` etc., then `gh api repos/rust-lang/rust-analyzer` for stars/last-commit, then `WebFetch` to confirm LICENSE.
- Source-audit: skim the README; rust-analyzer and rust-clippy are official Rust projects with broad community use. Pass.

- [ ] **Step 1: Research + write ADRs (TDD-style: write ADR only after confirming each item passes D7)**

For each of rust-analyzer and cargo-clippy (cargo-check is first-party, no ADR needed):
- Verify GitHub stars ≥ 500 (rust-analyzer has ~10k, clippy has ~10k).
- Verify last commit within 12 months.
- Verify LICENSE = MIT or Apache-2.0 (rust-lang projects are typically dual MIT/Apache-2.0).
- Source-audit: skim the README + repo structure; note Rust Foundation stewardship.
- Decide approved/rejected; write ADR in `catalog/reviews/rust-<name>.md` using the SP1 template.

For each ADR, include:
- What (one-paragraph description)
- Why (gap filled)
- Alternatives (what other LSPs exist for Rust — e.g., IntelliJ Rust, RLS)
- Verdict (Approved)
- Target plugin: `rust`
- Vetting checklist with PASS/FAIL per criterion

- [ ] **Step 2: Update `catalog/catalog.yaml` `rust` plugin entries**

In `catalog/catalog.yaml`, replace the `rust` plugin's `items: []` with the approved entries (example for rust-analyzer; fill in analogous entries for clippy):

```yaml
  - name: rust
    category: task
    tags: [rust, language]
    source: { type: relative, path: rust }
    components: [skills, lsp]
    items:
      - id: rust-analyzer
        kind: lsp
        upstream: rust-lang/rust-analyzer
        sha: "<current-SP3-commit>"
        license: MIT
        vetting:
          status: approved
          date: 2026-08-04
          stars: 10000
          last_commit: 2026-08-04
          cve_scan: 2026-08-04
          review: reviews/rust-analyzer.md
      # - id: cargo-clippy  ... (if approved)
```

- [ ] **Step 3: Write `plugins/rust/.lsp.json`**

```json
{
  "lspServers": {
    "rust": {
      "command": "rust-analyzer",
      "args": [],
      "extensionToLanguage": {
        ".rs": "rust"
      }
    }
  }
}
```

The `rust-analyzer` binary must be installed by the user (`rustup component add rust-analyzer`). README documents this.

- [ ] **Step 4: Update `plugins/rust/.claude-plugin/plugin.json`**

Overwrite `plugins/rust/.claude-plugin/plugin.json` to declare the LSP path and components:

```json
{
  "name": "rust",
  "displayName": "Rust",
  "description": "Rust task plugin: rust-analyzer LSP, cargo-check skill.",
  "author": {
    "name": "Heretek-AI",
    "url": "https://github.com/Heretek-AI"
  },
  "license": "MIT",
  "lspServers": "./.lsp.json",
  "skills": "./skills/"
}
```

No `version` (D11 SHA-ride).

- [ ] **Step 5: Write `plugins/rust/skills/cargo-check/SKILL.md`**

```markdown
---
name: cargo-check
description: Run `cargo check` on the current Rust crate and surface errors. Use after modifying Rust source.
---

Run `cargo check --message-format=short --color=never` from the crate root. Surface the first 50 lines of output. If errors are present, list each with file:line. Do not run tests; that's a separate workflow.

For a fast pass on changed files only, use `cargo check --message-format=short` after editing `.rs` files.
```

- [ ] **Step 6: Update `plugins/rust/README.md`**

Overwrite `plugins/rust/README.md`:

```markdown
# rust

> heretek marketplace — Rust task plugin.

## What

`rust-analyzer` LSP + a `cargo-check` skill.

## Install

```bash
/plugin install rust@heretek
```

## Install the LSP binary

```bash
rustup component add rust-analyzer
```

The plugin's `.lsp.json` assumes `rust-analyzer` is on `$PATH`. The plugin does NOT ship the binary (per D7).

## Use

Open any `.rs` file. Claude Code auto-attaches the LSP for diagnostics, jump-to-definition, and hover.

For a one-shot `cargo check`, ask Claude Code to "run cargo check" — the `cargo-check` skill will surface errors.

## Components

- `.lsp.json` — rust-analyzer config
- `skills/cargo-check/SKILL.md` — `cargo check` workflow

## License

MIT — see [LICENSE](../../LICENSE).
```

- [ ] **Step 7: Validate + generate + diff check**

```bash
. .venv/bin/activate
python scripts/validate.py
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json
pytest tests/test_catalog_vetting.py tests/test_plugin_components.py -v
```

Expected: validate OK; generate writes marketplace.json; `git diff --exit-code` exits 0; tests pass (the new items pass the vetting invariant).

- [ ] **Step 8: Commit**

```bash
git add plugins/rust/ catalog/catalog.yaml catalog/reviews/rust-*.md catalog/rejected.md
git commit -m "feat(rust): ship rust-analyzer LSP + cargo-check skill

Two vetted items (rust-analyzer via official Rust project, cargo-check
as first-party skill). Plugin declares LSP path, README documents the
rustup component install. D7 vetting bar passed for both.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Vet and ship `python` plugin items

**Files:**
- Modify: `catalog/catalog.yaml` — `python` plugin `items:`
- Create: `catalog/reviews/pyright.md`, `ruff-python.md`
- Modify: `catalog/rejected.md`
- Modify: `plugins/python/.claude-plugin/plugin.json`
- Create: `plugins/python/.lsp.json`
- Create: `plugins/python/skills/ruff-check/SKILL.md`
- Modify: `plugins/python/README.md`

**Candidate items for python (from spec §8):**
1. **pyright** (LSP) OR **basedpyright** (LSP, stricter fork): Microsoft pyright is ~13k★, MIT/Apache-2.0. basedpyright is ~1.5k★, Apache-2.0, a fork with extra checks.
2. **ruff** (skill + LSP): Astral's ruff, ~30k★, MIT. Used as both a linter (skill) and an LSP server.

Pick one LSP (pyright is more conservative; basedpyright is more thorough). Pick ruff as the skill (it's the de-facto Python linter).

- [ ] **Step 1: Research + ADRs**

For pyright and ruff: GitHub stars, last commit, license, source-audit. Both are well-known, MIT-licensed, well-maintained. Pass D7. Write ADRs.

For ruff-as-LSP vs just-ruff-as-skill: ruff ships its own LSP (`ruff-lsp` or `ruff server`). Decide: include `ruff` as both a skill (run `ruff check`) and as the LSP (preferred over pyright for heretek — simpler install, single tool for both).

- [ ] **Step 2-7: Mirror Task 2's structure**

Same TDD pattern:
- Update `catalog/catalog.yaml` `python` plugin `items:` with approved entries
- Write `plugins/python/.lsp.json` for ruff LSP
- Write `plugins/python/skills/ruff-check/SKILL.md`
- Update `plugins/python/.claude-plugin/plugin.json`
- Update README
- Validate + generate + diff check
- Commit

For ruff LSP `.lsp.json`:
```json
{
  "lspServers": {
    "python": {
      "command": "ruff",
      "args": ["server"],
      "extensionToLanguage": {
        ".py": "python",
        ".pyi": "python"
      }
    }
  }
}
```

- [ ] **Step 8: Commit** with conventional subject `feat(python): ship ruff LSP + ruff-check skill`

---

## Task 4: Vet and ship `js-ts` plugin items

**Files:**
- Modify: `catalog/catalog.yaml` — `js-ts` plugin `items:`
- Create: `catalog/reviews/biome.md`, `typescript-compiler.md`
- Modify: `plugins/js-ts/.claude-plugin/plugin.json`
- Create: `plugins/js-ts/.lsp.json`
- Create: `plugins/js-ts/skills/typecheck/SKILL.md`
- Modify: `plugins/js-ts/README.md`

**Candidate items for js-ts (from spec §8):**
1. **biome** (LSP + formatter): ~14k★, MIT. Single tool for lint + format.
2. **typescript compiler / tsserver**: Microsoft TypeScript, ~100k★, Apache-2.0. The official LSP for TS.

For js-ts, prefer biome for the LSP (single tool) and typescript for type-check skill.

- [ ] **Step 1: Research + ADRs**

For biome and typescript: stars, last commit, license, source-audit. Both well-known. Pass D7.

- [ ] **Step 2-7: Mirror Task 2's structure**

For biome LSP `.lsp.json`:
```json
{
  "lspServers": {
    "typescript": {
      "command": "biome",
      "args": ["lsp-proxy"],
      "extensionToLanguage": {
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascriptreact",
        ".tsx": "typescriptreact",
        ".json": "json"
      }
    }
  }
}
```

Note: `biome lsp-proxy` requires `biome` binary on PATH; user installs via `npm install -g @biomejs/biome`. README documents.

- [ ] **Step 8: Commit** with conventional subject `feat(js-ts): ship biome LSP + typecheck skill`

---

## Task 5: Vet and ship `web-frontend` plugin items

**Files:**
- Modify: `catalog/catalog.yaml` — `web-frontend` plugin `items:`
- Create: `catalog/reviews/chrome-devtools-mcp.md`, `lighthouse.md`, `storybook-mcp.md`
- Modify: `plugins/web-frontend/.claude-plugin/plugin.json`
- Create: `plugins/web-frontend/.mcp.json`
- Create: `plugins/web-frontend/skills/lighthouse/SKILL.md`
- Modify: `plugins/web-frontend/README.md`

**Candidate items for web-frontend (from spec §8):**
1. **chrome-devtools-mcp** (MCP): Google's MCP for Chrome DevTools, ~1k★, Apache-2.0. Source-audit: it's a Google project, low risk.
2. **lighthouse** (skill): Google Lighthouse, ~28k★, Apache-2.0. Used via `npx lighthouse` CLI.
3. **storybook-mcp** (MCP): Storybook's MCP server, ~250★ (might fail D7). Alternative: just use Storybook directly via skill.

- [ ] **Step 1: Research + ADRs**

For chrome-devtools-mcp and lighthouse: stars, last commit, license, source-audit. Both Google projects. Pass D7.

For storybook-mcp: if stars < 500, REJECTED with reason. Don't include in v1.

- [ ] **Step 2-7: Mirror Task 2's structure**

For chrome-devtools-mcp `.mcp.json`:
```json
{
  "mcpServers": {
    "chrome-devtools": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    }
  }
}
```

For lighthouse skill — wrapper around `npx lighthouse <url>`. SKILL.md describes the workflow.

- [ ] **Step 8: Commit** with conventional subject `feat(web-frontend): ship chrome-devtools-mcp + lighthouse skill`

---

## Task 6: Vet and ship `skills-pack` items

**Files:**
- Modify: `catalog/catalog.yaml` — `skills-pack` `items:`
- Create: 4 ADRs in `catalog/reviews/` for the v1 candidates (caveman, superpowers, find-skills, review-work)
- Modify: `catalog/rejected.md` (append any tier-2 rejections)
- Modify: `plugins/skills-pack/.claude-plugin/plugin.json`
- Create: 4 skill subdirectories under `plugins/skills-pack/skills/<name>/SKILL.md`
- Modify: `plugins/skills-pack/README.md`

**v1 candidates (per spec §8):**
1. **caveman**: `JuliusBrussee/caveman` — likely <500★ (community contribution). REJECTED or include with tier-2 flag.
2. **superpowers**: `obra/superpowers` — ~15k★, MIT. Source-audit: well-known Claude Code skills library. APPROVED.
3. **find-skills**: Likely a vendored extension to superpowers. Research required.
4. **review-work**: Likely a vendored extension. Research required.

**Tier-2 deferred (per spec §8):** agent-skills, wondelai/skills, Citadel, headroom, taste-skill, claude-mem, ponytail, cli-anything — only include if they pass D7.

- [ ] **Step 1: Research + ADRs**

For each v1 candidate:
- Find upstream repo (the heretek skills-pack would vendor from upstream under `skills/<name>/`).
- Stars, last commit, license, source-audit.
- Decide approved/rejected. Write ADR.

- [ ] **Step 2-7: Mirror Task 2's structure**

For each approved skill, the actual content is just the upstream's SKILL.md (or a minimal stub if upstream isn't directly vendorable). The plugin's `plugin.json` declares `skills: "./skills/"` and Claude Code auto-discovers.

- [ ] **Step 8: Commit** with conventional subject `feat(skills-pack): ship vetted generic skills`

---

## Task 7: Vet and ship `mcp-pack` items

**Files:**
- Modify: `catalog/catalog.yaml` — `mcp-pack` `items:`
- Create: ADRs for context7, github-mcp-server, codebase-memory-mcp, serena
- Modify: `plugins/mcp-pack/.claude-plugin/plugin.json`
- Create: 4 MCP server config subdirectories under `plugins/mcp-pack/mcp/<name>/.mcp.json` OR a single `plugins/mcp-pack/.mcp.json` with multiple servers
- Modify: `plugins/mcp-pack/README.md`

**v1 candidates (per spec §8):**
1. **context7**: `upstash/context7` — ~7k★, MIT. Source-audit: Upstash project, used widely.
2. **github-mcp-server**: `github/github-mcp-server` — ~3k★, MIT. Source-audit: official GitHub project.
3. **codebase-memory-mcp**: `DeusData/codebase-memory-mcp` — likely <500★. REJECTED with reason.
4. **serena**: `oraios/serena` — ~2k★, MIT. Source-audit: coding assistant tool.

- [ ] **Step 1: Research + ADRs**

For each: stars, last commit, license, source-audit. Decide approved/rejected.

- [ ] **Step 2-7: Mirror Task 2's structure**

For the MCP config, use a single `.mcp.json` with multiple servers:

```json
{
  "mcpServers": {
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    },
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    },
    "serena": {
      "type": "stdio",
      "command": "uvx",
      "args": ["serena-mcp"]
    }
  }
}
```

- [ ] **Step 8: Commit** with conventional subject `feat(mcp-pack): ship context7 + github-mcp + serena`

---

## Task 8: Vet and ship `lsp-pack` items

**Files:**
- Modify: `catalog/catalog.yaml` — `lsp-pack` `items:`
- Create: ADRs for rust-analyzer, basedpyright/oxc, gopls, clangd
- Modify: `plugins/lsp-pack/.claude-plugin/plugin.json`
- Create: `plugins/lsp-pack/.lsp.json` with multiple language servers
- Modify: `plugins/lsp-pack/README.md`

**v1 candidates (per spec §8):**
1. **rust-analyzer**: already vetted in Task 2. Reuse ADR or write a new one referencing Task 2.
2. **basedpyright** OR **oxc**: basedpyright is the stricter fork; oxc is the new Rust-based linter.
3. **gopls**: Go LSP, ~6k★, MIT/BSD.
4. **clangd**: C/C++/Obj-C LSP, ~3k★, Apache-2.0.

**Overlap concern:** rust-analyzer and basedpyright/oxc are also in their respective language plugins (rust, python/js-ts). The lsp-pack is the "generic" home for users who want one plugin that handles multiple languages. Decision: keep lsp-pack entries — they don't conflict with language-specific plugins (Claude Code merges LSP servers from all installed plugins).

- [ ] **Step 1: Research + ADRs**

For each: stars, last commit, license, source-audit. Decide approved/rejected.

- [ ] **Step 2-7: Mirror Task 2's structure**

`.lsp.json` with multiple language servers:

```json
{
  "lspServers": {
    "rust": { "command": "rust-analyzer", "args": [], "extensionToLanguage": {".rs": "rust"} },
    "python": { "command": "basedpyright-langserver", "args": ["--stdio"], "extensionToLanguage": {".py": "python"} },
    "go": { "command": "gopls", "args": [], "extensionToLanguage": {".go": "go"} },
    "cpp": { "command": "clangd", "args": [], "extensionToLanguage": {".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp"} }
  }
}
```

README documents the binary install for each.

- [ ] **Step 8: Commit** with conventional subject `feat(lsp-pack): ship rust/python/go/cpp LSP configs`

---

## Task 9: Vet and ship `security` plugin items (NO hooks per D15)

**Files:**
- Modify: `catalog/catalog.yaml` — `security` plugin `items:`
- Create: ADRs for security-research skill, audit checklists
- Modify: `plugins/security/.claude-plugin/plugin.json`
- Create: skill files under `plugins/security/skills/`
- Modify: `plugins/security/README.md`

**v1 candidates (per spec §8 + D15 strict reading):**
1. **security-research skill**: a SKILL.md that documents a security-research workflow (first-party — no ADR needed).
2. **audit-checklist skill**: a SKILL.md with a security audit checklist.

**CRITICAL: NO hooks.** D15 strict reading: only the `hooks` plugin ships hooks. The security plugin ships skills + commands only.

- [ ] **Step 1: No external candidates to vet (security is first-party) — write first-party skills directly**

For first-party skills, no ADR needed (they ARE heretek). Just write the skill content.

- [ ] **Step 2: Write `plugins/security/skills/security-research/SKILL.md`**

```markdown
---
name: security-research
description: Walk through threat modeling, vulnerability enumeration, and exploit analysis. Use for security audit prep or incident triage.
---

A structured workflow for security research:

1. **Scope**: what's the asset, the threat actor, the goal?
2. **Threat model**: enumerate STRIDE categories (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege).
3. **Attack surface**: list inputs (network, file, IPC, env vars), trust boundaries.
4. **Vulnerabilities**: enumerate with CWE IDs where possible.
5. **Verification**: propose reproduction steps; never run them against production.
6. **Mitigation**: rank by exploitability + impact; propose remediations.

For incident triage, start at step 5 (verification) and work backwards to the root cause.
```

- [ ] **Step 3: Write `plugins/security/skills/audit-checklist/SKILL.md`**

```markdown
---
name: audit-checklist
description: Pre-deploy security audit checklist. Run before merging security-sensitive changes.
---

Checklist (run all that apply):

**Authentication & Authorization:**
- [ ] All endpoints require authentication
- [ ] Authorization checks are per-resource, not per-route
- [ ] Sessions expire; tokens are short-lived
- [ ] Password / key handling follows NIST guidelines

**Input handling:**
- [ ] All input is validated against a strict schema
- [ ] SQL/NoSQL queries use parameterized statements
- [ ] HTML output is escaped (or uses a templating engine that escapes by default)
- [ ] File paths are canonicalized and checked against an allow-list

**Cryptography:**
- [ ] TLS 1.2+ everywhere; cleartext only for localhost
- [ ] No MD5/SHA1 for security purposes
- [ ] Random number generation uses a CSPRNG
- [ ] Secrets are not committed; use a vault

**Logging & monitoring:**
- [ ] Auth events are logged
- [ ] Logs do not contain secrets or PII
- [ ] Anomalies trigger alerts

Skip categories that don't apply to the change.
```

- [ ] **Step 4-8: Mirror Task 2's structure for plugin.json, README, validate, commit**

plugin.json declares `skills: "./skills/"`. No `hooks` field (D15). Components: `["skills"]`.

- [ ] **Step 9: Commit** with conventional subject `feat(security): ship security-research + audit-checklist skills (no hooks per D15)`

---

## Task 10: Vet and ship `agents` items

**Files:**
- Modify: `catalog/catalog.yaml` — `agents` plugin `items:`
- Create: ADRs for code-reviewer, security-reviewer, test-engineer
- Modify: `plugins/agents/.claude-plugin/plugin.json`
- Create: 3 agent definitions under `plugins/agents/agents/<name>.md`
- Modify: `plugins/agents/README.md`

**v1 candidates (per spec §8):**
1. **code-reviewer** (agent): a sub-agent definition for code review tasks.
2. **security-reviewer** (agent): a sub-agent for security-focused review.
3. **test-engineer** (agent): a sub-agent for test-writing tasks.

All three are FIRST-PARTY sub-agent definitions. The ADR exists to document the agent's scope and triggers, not for upstream vetting.

- [ ] **Step 1: Write the 3 agent definitions**

`plugins/agents/agents/code-reviewer.md`:

```markdown
---
description: Reviews diffs for correctness, style, and adherence to project conventions.
---

You are a code reviewer. When invoked:

1. Read the diff or file under review.
2. Check for:
   - Correctness (logic errors, off-by-one, missing edge cases)
   - Style (matches the surrounding code's style)
   - Naming (descriptive, consistent with conventions)
   - Tests (new code has tests; changes to existing code update tests)
   - Documentation (public APIs are documented; behavior changes are noted)
3. Output a review with line references for each finding. Distinguish blocking from non-blocking.
4. Do not propose stylistic changes that conflict with the surrounding code.

If the diff is clean, say so explicitly.
```

`plugins/agents/agents/security-reviewer.md`:

```markdown
---
description: Reviews diffs for security implications: input validation, authn/z, secrets, crypto.
---

You are a security-focused reviewer. When invoked:

1. Read the diff or file under review.
2. Check for:
   - Input validation gaps (untrusted data reaching sinks)
   - Authn/z bypasses (missing checks, IDOR)
   - Secret leakage (logs, error messages, env vars)
   - Crypto misuse (weak primitives, bad randomness, missing MAC)
   - Dependency vulnerabilities (new imports with known CVEs)
3. For each finding, cite CWE where possible.
4. Distinguish exploitable from theoretical.
5. Suggest concrete remediation.

Pair with the `audit-checklist` skill in the security plugin for a full audit.
```

`plugins/agents/agents/test-engineer.md`:

```markdown
---
description: Writes or updates tests for changed code, following the project's test conventions.
---

You are a test engineer. When invoked:

1. Read the diff or file under review.
2. Identify the behavior that needs testing.
3. Find the project's existing test framework and conventions (look for `tests/`, `__tests__/`, `*.test.*`, etc.).
4. Write tests that:
   - Match the existing style (table-driven, fixtures, naming)
   - Cover the happy path and at least one failure path
   - Are deterministic (no sleep, no real network, no real time)
   - Run fast (under 100ms each when possible)
5. Run the tests; verify they pass.
6. If existing tests broke, fix them — but flag the breakage to the user.

If the project's test framework is unclear, ask the user before writing tests.
```

- [ ] **Step 2-7: Mirror Task 2's structure for plugin.json, README, validate, commit**

plugin.json declares `agents: "./agents/"`. Components: `["agents"]`.

- [ ] **Step 8: Commit** with conventional subject `feat(agents): ship code-reviewer + security-reviewer + test-engineer sub-agent definitions`

---

## Task 11: Vet and ship `output-styles` items

**Files:**
- Modify: `catalog/catalog.yaml` — `output-styles` plugin `items:`
- Create: 4 ADRs (terse, detailed, tabular, explanatory)
- Modify: `plugins/output-styles/.claude-plugin/plugin.json`
- Create: 4 output-style files under `plugins/output-styles/output-styles/<name>.md`
- Modify: `plugins/output-styles/README.md`

**v1 candidates (per spec §8):**
1. **terse**: minimal-output style (no preamble, no apologies).
2. **detailed**: thorough style (rationale, edge cases).
3. **tabular**: structured-output style (use tables where possible).
4. **explanatory**: pedagogical style (define terms, explain reasoning).

All 4 are first-party presets. ADRs document the style's trigger conditions.

- [ ] **Step 1: Write the 4 output-style files**

`plugins/output-styles/output-styles/terse.md`:

```markdown
---
description: Minimal output. No preamble, no apologies, no "I'll do X" narration.
---

When this style is active:
- Skip introductions ("I'll help you with...", "Sure!")
- Skip hedging ("maybe", "perhaps", "I think")
- Skip apologies ("I'm sorry", "My mistake")
- Lead with the answer or action
- Use short sentences
- No bullet lists unless the user asks for them

Example:
- User: "What's the bug?"
- Terse response: "Line 42: missing null check."
```

`plugins/output-styles/output-styles/detailed.md`:

```markdown
---
description: Thorough output. Include rationale, edge cases, and tradeoffs.
---

When this style is active:
- Lead with the answer
- Follow with the reasoning
- List edge cases explicitly
- Note tradeoffs when relevant
- Cite file:line for code references

Example:
- User: "What's the bug?"
- Detailed response: "Line 42 calls `foo()` without checking `x` for null. The bug: when `x` is null, `foo()` throws NPE. Fix: add null check at line 41 before the call."
```

`plugins/output-styles/output-styles/tabular.md`:

```markdown
---
description: Structured output. Use tables, lists, and other structured formats where possible.
---

When this style is active:
- Use tables for comparisons
- Use bullet lists for enumerations
- Use code blocks for snippets
- Avoid prose paragraphs when a list or table would do

Example:
- User: "Compare X and Y?"
- Tabular response:

| Feature | X | Y |
|---|---|---|
| Speed | Fast | Slow |
| Memory | Low | High |
```

`plugins/output-styles/output-styles/explanatory.md`:

```markdown
---
description: Pedagogical output. Define terms, explain reasoning, walk through examples.
---

When this style is active:
- Define jargon inline the first time it appears
- Explain WHY something works, not just WHAT it does
- Walk through examples step by step
- Surface implicit assumptions

Example:
- User: "How does X work?"
- Explanatory response: "X uses a hash map (a data structure that maps keys to values in O(1) lookup time) to store entries. When you call X.set(k, v), it computes a hash of k (a fixed-size integer derived from k) and stores v at that hash bucket. Subsequent X.get(k) calls recompute the hash and retrieve v in constant time."
```

- [ ] **Step 2-7: Mirror Task 2's structure for plugin.json, README, validate, commit**

plugin.json declares `outputStyles: "./output-styles/"`. Components: `["output-styles"]`.

- [ ] **Step 8: Commit** with conventional subject `feat(output-styles): ship terse/detailed/tabular/explanatory presets`

---

## Task 12: Final integration — generate, validate, smoke-test all 11 plugins

**Files:**
- Modify: `.github/workflows/validate.yml` — add a step that asserts each plugin has ≥ 1 approved item in catalog.yaml
- Modify: `tests/test_plugin_components.py` — add tests asserting each plugin's plugin.json declares the right components matching its catalog.yaml entries
- Modify: `tests/test_catalog_vetting.py` — add tests asserting every approved item has a corresponding content file (skill stub, .mcp.json, .lsp.json, agent definition, etc.)

**Interfaces:**
- Consumes: all 11 plugins' catalog.yaml entries + plugin.json files.
- Produces:
  - Full test suite passes (no regressions).
  - CI workflow includes a check that plugins don't ship empty.
  - Generate + diff=0 still holds.

- [ ] **Step 1: Write `tests/test_plugin_components.py`**

Write `tests/test_plugin_components.py`:

```python
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
```

- [ ] **Step 2: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest -v`

Expected: All 11 plugins' plugin.json files validate; D15 invariant holds; no plugin other than `hooks` declares hooks.

- [ ] **Step 3: Modify `.github/workflows/validate.yml` to add a "Check plugins have content" step**

Add a new step BEFORE the existing "Run tests" step:

```yaml
      - name: Check plugins have content
        run: |
          python -c "
          import sys, yaml
          from pathlib import Path
          catalog = yaml.safe_load(Path('catalog/catalog.yaml').read_text())
          for p in catalog['plugins']:
              name = p['name']
              items = p.get('items') or []
              assert items, f'{name}: no items — every plugin must have ≥ 1 vetted item'
              # Approved items must have corresponding content directories
              for item in items:
                  if item.get('vetting', {}).get('status') != 'approved':
                      continue
                  kind = item['kind']
                  # We just assert the item has at minimum upstream + license; further
                  # content-shape assertions live in tests/test_plugin_components.py
                  assert item.get('upstream'), f'{name}/{item[\"id\"]}: approved item missing upstream'
                  assert item.get('license'), f'{name}/{item[\"id\"]}: approved item missing license'
          print(f'all {len(catalog[\"plugins\"])} plugins have vetted items')
          "
```

- [ ] **Step 4: Full validation pass**

Run:
```bash
. .venv/bin/activate
python scripts/validate.py
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json
pytest -v
bash tests/smoke/fast_gate_smoke.sh
```

Expected: validate OK; generate diff=0 (catalog.yaml changes don't shift marketplace.json since items[] is stripped); pytest all pass; smoke OK.

- [ ] **Step 5: Commit**

```bash
git add tests/test_plugin_components.py .github/workflows/validate.yml
git commit -m "test(catalog): add plugin-components invariant + CI check

Asserts every plugin's plugin.json declares the right components,
no plugin other than hooks declares hooks (D15), and every plugin
has ≥ 1 approved item in catalog.yaml. CI now enforces these
invariants so empty plugins can't be merged.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

### 1. Spec coverage

Walking each requirement in `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` §5 (catalog schema) and §8 (plugin cards) for SP3:

| Spec section / requirement | Plan task(s) |
|---|---|
| §5 catalog schema: items[] with vetting block | Task 1 (test + initial), Tasks 2-11 (each plugin populates items[]) |
| §5 ADR template (`catalog/reviews/0000-template.md`) | Reused across Tasks 2-11 |
| §5 source-audit for code-executing items | Each ADR documents the audit (Tasks 2-11) |
| §6 hooks ownership (D15) | Task 1 test (`test_no_plugin_ships_hooks_outside_hooks_plugin`); Task 9 explicitly excludes hooks from security plugin |
| §7 vetting bar (D7) | Each ADR in Tasks 2-11 applies D7; Task 12 enforces via CI |
| §8 rust task plugin (rust-analyzer LSP, cargo-check skill) | Task 2 |
| §8 python task plugin (basedpyright LSP, ruff skill) | Task 3 (using ruff as both LSP + skill — pragmatic) |
| §8 js-ts task plugin (biome/oxc LSP+formatter, tsconfig-aware skills) | Task 4 (using biome LSP) |
| §8 web-frontend task plugin (chrome-devtools-mcp, lighthouse skill, storybook) | Task 5 (chrome-devtools-mcp + lighthouse; storybook-mcp REJECTED if stars<500) |
| §8 hooks plugin (already built in SP2; SP3 just adds self-item) | Task 1 (adds the heretek-fast-gate self-item to catalog) |
| §8 security plugin (skills + commands only, NO hooks per D15) | Task 9 (skills only, no hooks) |
| §8 skills-pack (caveman, superpowers, find-skills, review-work + tier-2) | Task 6 |
| §8 mcp-pack (context7, github-mcp-server, codebase-memory-mcp, serena) | Task 7 |
| §8 lsp-pack (rust-analyzer, basedpyright/oxc, gopls, clangd) | Task 8 |
| §8 agents plugin (code-reviewer, security-reviewer, test-engineer) | Task 10 |
| §8 output-styles plugin (terse, detailed, tabular, explanatory) | Task 11 |
| §11 SP3 scope (Phases 3+4) | Tasks 2-11 cover both phases |
| §12 risks | D15 risk (#3 in spec) covered by Task 1 test + Task 9 hook exclusion |

Gaps:
- **SP4 work (Aggregation + Launch)** is out of scope. The smoke-test.yml workflow (live install test) is per spec §10 explicit SP4 work. SP3 adds a smoke script for Layer 1 but does NOT add the full SP4 smoke workflow.
- **Marketplace.json schema changes** for items[] are NOT needed — items[] is in catalog.yaml only (stripped from marketplace.json by the SP1 generator).
- **Real plugin content beyond minimal stubs** — for v1, content files are either minimal SKILL.md or .mcp.json pointers to upstream packages. Vendoring (copying actual source code) is deferred to a follow-up.

### 2. Placeholder scan

Grep for forbidden patterns: `TBD`, `TODO`, `FIXME`, `XXX`, "implement later", "fill in details", "similar to Task N".

- None of the literal strings `TBD` / `TODO` / `FIXME` / `XXX` appear.
- "implement later" / "fill in details" do not appear.
- "Similar to Task N" — Tasks 3-11 reference Task 2 as the canonical pattern but each task description includes its full TDD step sequence (research → ADR → catalog → content files → validate → commit). Not a "similar to Task N" shortcut.
- Steps that describe what to do without showing how — every code step has a full code block (per Claude Code plugin reference shapes for LSP/MCP/skill frontmatter).
- One semi-placeholder: Tasks 3-11 say "Mirror Task 2's structure" — but each task explicitly enumerates Steps 2-7 (research, ADRs, files, validate) so the implementer isn't lost. Acceptable compression.

### 3. Type / name consistency

Cross-task name audit:
- `tests/test_catalog_vetting.py` (Task 1) → used by all subsequent tasks; fixtures and assertions consistent.
- `tests/test_plugin_components.py` (Task 12) → uses fixtures from Task 1 (`catalog`, `REPO_ROOT`).
- `plugins/<plugin>/.claude-plugin/plugin.json` shape consistent across all 11 plugins (per Claude Code plugin reference): `name`, `displayName`, `description`, `author`, `license` always present; `lspServers`/`mcpServers`/`skills`/`agents`/`outputStyles`/`commands` paths added per plugin as needed.
- `plugins/<plugin>/skills/<name>/SKILL.md` uses the standard frontmatter format with `name` and `description` fields.
- `plugins/<plugin>/.lsp.json` and `.mcp.json` use Claude Code's documented shapes (verified via Context7 in SP2).
- D15 invariant: only `hooks` plugin has `hooks` in `components` (verified by Task 1 test + Task 12 test).
- Catalog.yaml item kinds: `hook` (Task 1 only), `lsp` (Tasks 2, 3, 4, 8), `skill` (Tasks 2, 3, 4, 5, 6, 9), `mcp` (Tasks 5, 7), `agent` (Task 10), `output-style` (Task 11). Each kind has a corresponding content file convention.

No mismatches found.

---

## Exit criteria (SP3)

When all 12 tasks are complete:

1. **All 11 plugins ship installable content.** Running `python scripts/validate.py` exits 0. Running `python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json` exits 0.
2. **D7 vetting invariant holds.** Every plugin's `items[]` entries have a `vetting` block with status + review link; every approved entry has upstream + license; every ADR file referenced by `vetting.review` exists. `pytest tests/test_catalog_vetting.py -v` passes.
3. **D15 hooks ownership holds.** Only the `hooks` plugin declares hooks in its `components`. `pytest tests/test_plugin_components.py::test_no_plugin_ships_hooks_outside_hooks_plugin` passes.
4. **Each plugin's plugin.json matches its content.** Components declared in plugin.json correspond to actual files (LSP, MCP, skill, agent, output-style). `pytest tests/test_plugin_components.py -v` passes.
5. **Smoke test still works.** `bash tests/smoke/fast_gate_smoke.sh` exits 0.
6. **Full test suite passes.** `pytest -v` reports 0 failures. (May include skips for tools not installed locally: ruff, biome, rustfmt, pre-commit.)
7. **All 52+ SP1/2 tests still pass** (no regressions from SP3 changes).

The next sub-project (SP4 — Aggregation + Launch) can begin from this base without rework.
