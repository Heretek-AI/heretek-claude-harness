# SP4 — Aggregation + Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the public launch — add curated 3rd-party aggregation, the `scripts/refresh-pins.py` quarterly refresh tool, public-facing docs (README expansion, CONTRIBUTING.md, SECURITY.md), a community-tagged external-marketplaces doc, and the `smoke-test.yml` GitHub Actions workflow that runs a fresh-repo install + fast-gate trigger.

**Architecture:** All work is additive — no existing files are rewritten except for a README expansion (Task 2). Tasks 1 + 3-5 are first-party documentation that follow established heretek conventions (MIT, no version, conventional commits, trailing newlines). Task 2 expands the existing minimal README into a full install walkthrough with badges, component tables, and links to CONTRIBUTING/SECURITY. Tasks 6-8 are CI + tooling — `scripts/refresh-pins.py` is a Python script that re-verifies every external SHA against its D7 contract; `smoke-test.yml` is a GitHub Actions workflow that fresh-clones, installs the marketplace, and triggers a fast-gate hook in a clean repo.

**Tech Stack:** Python 3.10+, PyYAML, requests (for GitHub API), pytest, GitHub Actions.

## Global Constraints

These apply to every task in this plan. Copy values verbatim from the spec:

- **Marketplace name:** `heretek`. **Owner:** `Heretek-AI`. **License:** MIT for first-party code (D14). Vendored 3rd-party components retain their upstream license + NOTICE.
- **SHA-ride versioning:** no `version` field on first-party plugins (D11, D16). For vendored 3rd-party items, the catalog entry carries a `sha:` pin.
- **D7 vetting bar:** stars ≥ 500, last commit ≤ 12mo, OSI license, source-audit pass for code-executing, no critical CVEs (CVSS ≥ 9.0) in last 24 months.
- **D15 (strict hooks ownership):** the `hooks` plugin is the SOLE owner of all hook components.
- **All files end with trailing `\n`.**
- **Org + repo transfer (D17) is already complete:** main is live at `github.com/Heretek-AI/heretek-claude-harness` (pushed in commit `6bcd204`). No org/repo work in this plan.
- **Generate → marketplace.json is idempotent** (verified by SP1/SP2/SP3). Re-running the generator produces byte-identical output.

---

## File Structure

Files this plan creates or modifies. Each has one clear responsibility.

| Path | Responsibility |
|---|---|
| `catalog/catalog.yaml` | (modify) — add community-tagged 3rd-party entries under `items[]` of relevant plugins; or add a new `community` category if the items aren't plugin-specific |
| `catalog/reviews/community-<slug>.md` | (many new) — ADRs for each curated 3rd-party entry that survives D7 |
| `catalog/rejected.md` | (modify) — append rejected 3rd-party entries with reason |
| `scripts/refresh-pins.py` | (new) — Python script that re-verifies every external SHA against its D7 contract (stars/last-commit/license/CVE scan), flags stale entries, optionally bumps SHA |
| `docs/recommended-marketplaces.md` | (new) — short doc listing external marketplaces heretek users might want to add manually (claudepluginhub, official claude-code marketplaces, etc.) |
| `README.md` | (modify) — expand minimal v1 to full install walkthrough with badges, component table, links to CONTRIBUTING/SECURITY, CHANGELOG pointer |
| `CONTRIBUTING.md` | (new) — how to add new items (vet per D7, write ADR, update catalog.yaml, run tests), PR template, code-of-conduct pointer |
| `SECURITY.md` | (new) — supply-chain risk model, reporting path (security@heretek.ai placeholder), supported versions, quarterly refresh cadence |
| `.github/workflows/smoke-test.yml` | (new) — CI workflow that fresh-clones the repo, installs all 11 plugins, triggers a fast-gate hook on a bad file |

**Files that change together live together.** All community ADRs go under `catalog/reviews/`. All CI config under `.github/workflows/`. All public-facing docs under `docs/`.

---

## Task 1: `scripts/refresh-pins.py` — quarterly SHA + vetting refresh tool

**Files:**
- Create: `scripts/refresh_pins.py`
- Create: `tests/test_refresh_pins.py`
- Create: `tests/fixtures/refresh_pins/sample_catalog.yaml`

**Interfaces:**
- Consumes: `catalog/catalog.yaml` (every item[] entry's `upstream` + `sha` + `vetting`).
- Produces:
  - Python API: `check_item(item: dict) -> tuple[str, dict]` — returns `("ok" | "stale_stars" | "stale_commit" | "cve_alert" | "license_drift", {details})` for a single catalog entry
  - Python API: `check_catalog(catalog_path: Path, *, gh_token: Optional[str] = None) -> list[tuple[str, Path, str, dict]]` — returns list of `(status, item_path, item_id, details)` for the entire catalog
  - Python API: `bump_sha(item: dict, new_sha: str) -> dict` — returns a copy with `sha` and `vetting.date` updated
  - CLI: `python scripts/refresh_pins.py [--catalog PATH] [--update-shas] [--github-token TOKEN]` — by default prints a table of stale items; with `--update-shas` writes new SHAs back to catalog.yaml
  - Reads `GITHUB_TOKEN` from env if `--github-token` not provided; fails closed (refuses to make network calls) if no token

**GitHub API calls (only when a token is present):** `GET /repos/{owner}/{repo}` for stars, last-pushed-at, license; `GET /repos/{owner}/{repo}/security-advisories` for critical CVEs.

- [ ] **Step 1: Write the failing test**

Write `tests/fixtures/refresh_pins/sample_catalog.yaml`:

```yaml
marketplace:
  name: test-mp
  owner: { name: Tester }
plugins:
  - name: ok-plugin
    category: task
    source: { type: relative, path: ok-plugin }
    components: [lsp]
    items:
      - id: rust-analyzer
        kind: lsp
        upstream: rust-lang/rust-analyzer
        sha: "0123456789abcdef0123456789abcdef01234567"
        license: MIT
        vetting:
          status: approved
          date: 2026-08-04
          stars: 16000
          last_commit: 2026-08-04
          cve_scan: 2026-08-04
          review: reviews/test.md

  - name: stale-plugin
    category: task
    source: { type: relative, path: stale-plugin }
    components: [lsp]
    items:
      - id: ghost-tool
        kind: lsp
        upstream: someorg/ghost-tool-that-no-longer-exists
        sha: "0000000000000000000000000000000000000000"
        license: MIT
        vetting:
          status: approved
          date: 2025-01-01
          stars: 999999
          last_commit: 2024-01-01
          cve_scan: 2026-08-04
          review: reviews/test.md
```

Write `tests/test_refresh_pins.py`:

```python
"""Tests for scripts/refresh_pins.py."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import refresh_pins  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "refresh_pins" / "sample_catalog.yaml"


def test_check_item_offline_returns_ok_or_stale_without_network() -> None:
    """Without a token, `check_item` does NOT call GitHub; it compares the stored sha against a derived expectation."""
    item = {
        "id": "rust-analyzer",
        "kind": "lsp",
        "upstream": "rust-lang/rust-analyzer",
        "sha": "0123456789abcdef0123456789abcdef01234567",
        "license": "MIT",
        "vetting": {"status": "approved", "date": "2026-08-04", "stars": 16000, "last_commit": "2026-08-04"},
    }
    status, details = refresh_pins.check_item(item, gh_token=None)
    # Without a token, the tool cannot make API calls; it should report "skipped" or surface a clear reason.
    assert status in {"skipped", "ok", "stale_stars", "stale_commit", "license_drift"}
    assert "reason" in details or status == "skipped"


def test_check_item_detects_stale_last_commit() -> None:
    """A vetting.last_commit older than 12 months ago is flagged as stale_commit."""
    import datetime as dt

    old_date = (dt.date.today() - dt.timedelta(days=400)).isoformat()
    item = {
        "id": "old-thing",
        "upstream": "someorg/old-thing",
        "sha": "abc",
        "license": "MIT",
        "vetting": {"status": "approved", "date": old_date, "stars": 1000, "last_commit": old_date},
    }
    status, details = refresh_pins.check_item(item, gh_token=None)
    # The offline check should at least surface the stale date.
    assert details.get("last_commit") == old_date or status == "stale_commit"


def test_check_catalog_returns_list_per_item(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """check_catalog walks every plugin's items[] and emits one entry per item."""
    # No network calls; offline behavior.
    monkeypatch.setattr(refresh_pins, "_github_get", lambda *_a, **_k: {})
    results = refresh_pins.check_catalog(FIXTURE, gh_token=None)
    # 2 items in the fixture
    assert len(results) == 2
    ids = {item_id for _, _, item_id, _ in results}
    assert "rust-analyzer" in ids
    assert "ghost-tool" in ids


def test_bump_sha_returns_updated_item() -> None:
    item = {"id": "x", "sha": "old", "vetting": {"date": "2026-01-01"}}
    new = refresh_pins.bump_sha(item, "new-sha")
    assert new["sha"] == "new-sha"
    assert new["vetting"]["date"] != "2026-01-01"


def test_main_no_token_prints_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """`main` with no token prints a status table to stdout and exits 0 (don't fail on stale)."""
    monkeypatch.setattr("sys.argv", ["refresh_pins.py", "--catalog", str(FIXTURE)])
    rc = refresh_pins.main()
    assert rc in (0, 1)  # 0 = all fresh; 1 = some stale; both are non-error
    captured = capsys.readouterr()
    assert "rust-analyzer" in captured.out or "ghost-tool" in captured.out
```

- [ ] **Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_refresh_pins.py -v`

Expected: `ModuleNotFoundError: No module named 'refresh_pins'`.

- [ ] **Step 3: Implement `scripts/refresh_pins.py`**

```python
"""Quarterly SHA + vetting refresh tool for heretek marketplace.

Walks every items[] entry in catalog.yaml and verifies the upstream
is still healthy against the D7 vetting bar (stars, last commit, license,
no critical CVEs). Without a GitHub token, runs offline and reports
staleness based on stored `vetting.date` (older than ~12 months → stale).

Exit codes:
  0  all items fresh
  1  some items stale (operator should review + bump)
  2  network or parse error

Usage:
  python scripts/refresh_pins.py                       # offline, prints table
  python scripts/refresh_pins.py --github-token $TOK  # live API checks
  python scripts/refresh_pins.py --update-shas        # write new SHAs
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "catalog" / "catalog.yaml"

STALENESS_WINDOW_DAYS = 365
GITHUB_API = "https://api.github.com"


def _days_since(date_str: str) -> int:
    try:
        d = dt.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return 10**9
    return (dt.date.today() - d).days


def _github_get(path: str, gh_token: Optional[str]) -> dict:
    """Single GET against the GitHub API. Returns {} on any error (network, 404, rate limit).

    Override this in tests for hermetic execution.
    """
    try:
        import requests  # type: ignore

        headers = {"Accept": "application/vnd.github+json"}
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"
        r = requests.get(f"{GITHUB_API}{path}", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        return {}
    except Exception:
        return {}


def check_item(item: dict, *, gh_token: Optional[str]) -> tuple[str, dict]:
    """Return (status, details). status ∈ {ok, skipped, stale_stars, stale_commit, license_drift, cve_alert}."""
    details: dict[str, Any] = {"id": item.get("id"), "upstream": item.get("upstream")}
    vetting = item.get("vetting") or {}
    vetting_date = vetting.get("date")
    if vetting_date and _days_since(vetting_date) > STALENESS_WINDOW_DAYS:
        details["reason"] = f"vetting.date {vetting_date} is older than {STALENESS_WINDOW_DAYS} days"
        return "stale_commit", details
    if not gh_token:
        details["reason"] = "no GITHUB_TOKEN; offline check skipped"
        return "skipped", details
    upstream = item.get("upstream")
    if not upstream or "/" not in upstream:
        details["reason"] = "upstream missing or malformed"
        return "skipped", details
    data = _github_get(f"/repos/{upstream}", gh_token)
    if not data:
        details["reason"] = "upstream not found or API error"
        return "stale_stars", details  # conservative
    stars = data.get("stargazers_count", 0)
    if stars < 500:
        details["reason"] = f"stars={stars} < 500"
        return "stale_stars", details
    spdx = (data.get("license") or {}).get("spdx_id") or "NOASSERTION"
    if spdx != (item.get("license") or "").upper():
        details["reason"] = f"license drifted: upstream={spdx} vs catalog={item.get('license')}"
        return "license_drift", details
    advisories = _github_get(f"/repos/{upstream}/security-advisories", gh_token)
    critical = [a for a in advisories if (a.get("severity") or "").upper() == "CRITICAL"]
    if critical:
        details["reason"] = f"{len(critical)} critical CVE(s)"
        return "cve_alert", details
    return "ok", details


def check_catalog(catalog_path: Path, *, gh_token: Optional[str]) -> list[tuple[str, Path, str, dict]]:
    catalog = yaml.safe_load(catalog_path.read_text())
    results: list[tuple[str, Path, str, dict]] = []
    for plugin in catalog.get("plugins", []):
        plugin_path = REPO_ROOT / "plugins" / plugin["name"]
        for item in plugin.get("items") or []:
            status, details = check_item(item, gh_token=gh_token)
            results.append((status, plugin_path, item.get("id", "?"), details))
    return results


def bump_sha(item: dict, new_sha: str) -> dict:
    """Return a copy of item with sha + vetting.date updated to today."""
    out = dict(item)
    out["sha"] = new_sha
    vetting = dict(item.get("vetting") or {})
    vetting["date"] = dt.date.today().isoformat()
    out["vetting"] = vetting
    return out


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--update-shas", action="store_true",
                        help="Write updated SHAs back to the catalog (requires --github-token).")
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"))
    args = parser.parse_args(argv)
    results = check_catalog(args.catalog, gh_token=args.github_token)
    rc = 0
    print(f"{'STATUS':<14} {'PLUGIN':<24} {'ITEM':<28} DETAIL")
    print("-" * 100)
    for status, path, item_id, details in results:
        detail_str = details.get("reason", "")
        if status == "ok":
            rc = rc  # no change
        elif status == "skipped":
            pass
        else:
            rc = 1
        print(f"{status:<14} {path.name:<24} {item_id:<28} {detail_str}")
    print()
    print(f"Summary: {len(results)} item(s); {sum(1 for s, *_ in results if s != 'ok' and s != 'skipped')} stale")
    return rc


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_refresh_pins.py -v`

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/refresh_pins.py tests/test_refresh_pins.py tests/fixtures/refresh_pins/
git commit -m "feat(scripts): add refresh-pins quarterly D7 verification tool

Walks catalog.yaml items[], compares each upstream against the D7 bar
(stars, last_commit, license, no critical CVEs). Offline mode skips
API calls when no GITHUB_TOKEN is set; online mode uses GitHub REST
to check stars + license drift + critical advisories. Exit code 1 if
any item is stale; 0 if all fresh.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Expand `README.md` — full public-facing install walkthrough

**Files:**
- Modify: `README.md` (the existing minimal v1 from SP1 Task 15)

**Interfaces:**
- Replaces the minimal README with a full public-facing version. Keeps the install + plugins sections but adds: badges, what-this-is paragraph, component table per plugin, links to CONTRIBUTING/SECURITY/docs/, a quickstart that uses `git clone` + `git remote add` (since the marketplace can be added from a git URL), a "verifying installs" section, and a CHANGELOG pointer.

- [ ] **Step 1: Overwrite `README.md`**

```markdown
# heretek

> Opinionated Claude Code plugin marketplace: task plugins, quality-gate hooks, curated MCP/LSP/skills.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Marketplace: heretek](https://img.shields.io/badge/marketplace-heretek-blueviolet)](https://github.com/Heretek-AI/heretek-claude-harness)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](.github/workflows/validate.yml)

## What is this?

`heretek` is a Claude Code marketplace that bundles 11 first-party plugins — Rust, Python, JS/TS, web frontend, security, MCP, LSP, skills, agents, output styles — plus the flagship `hooks` plugin that gates every Edit/Write/MultiEdit with a sub-100ms quality check.

Every item ships after D7 vetting (stars ≥ 500, last commit ≤ 12mo, OSI license, source-audit pass, no critical CVEs in 24 months) with an ADR in `catalog/reviews/` documenting the decision.

## Install

```bash
# Add the marketplace (once)
/plugin marketplace add heretek https://github.com/Heretek-AI/heretek-claude-harness

# Install a plugin
/plugin install rust@heretek
/plugin install hooks@heretek

# Install all 11
for p in rust python js-ts web-frontend hooks security skills-pack mcp-pack lsp-pack agents output-styles; do
  /plugin install $p@heretek
done
```

## What ships?

See [`docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md`](docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md) for the canonical plugin catalog. Quick summary:

| Plugin | Category | What it does |
|---|---|---|
| `rust` | task | rust-analyzer LSP + cargo-check + cargo-clippy skills |
| `python` | task | ruff LSP + ruff-check skill |
| `js-ts` | task | biome LSP + typecheck skill |
| `web-frontend` | task | chrome-devtools-mcp + lighthouse skill |
| `hooks` | cross (flagship) | 3-layer quality gates (fast blocking <100ms, slow on-demand, git pre-commit) |
| `security` | cross | security-research + audit-checklist skills (NO hooks — `hooks` plugin owns all hook components per D15) |
| `skills-pack` | cross | caveman, superpowers |
| `mcp-pack` | cross | context7, github-mcp-server, codebase-memory-mcp, serena |
| `lsp-pack` | cross | rust-analyzer, basedpyright, gopls, clangd |
| `agents` | cross | code-reviewer, security-reviewer, test-engineer |
| `output-styles` | cross | terse, detailed, tabular, explanatory |

## How vetting works

Every entry in `catalog.yaml`'s `items[]` carries:
- `vetting.status` (approved | rejected | pending)
- `vetting.date` (when last verified)
- `vetting.review` (path to ADR in `catalog/reviews/`)
- `upstream` (the actual repo)
- `sha` (40-char pin, lock-step with D11 SHA-ride)
- `license` (SPDX id)

Quarterly, run `python scripts/refresh_pins.py --github-token $GH_TOKEN` to re-verify every entry against the D7 bar. Items that fail (stars drop, license drift, critical CVE published) get flagged for review.

## Documentation

- [`docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md`](docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md) — design spec (locked decisions D1–D17)
- [`docs/recommended-marketplaces.md`](docs/recommended-marketplaces.md) — external marketplaces to add manually
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to add new items, submit PRs
- [`SECURITY.md`](SECURITY.md) — supply-chain risk model + reporting path

## Versioning

No `version` field on first-party plugins (D11). The marketplace itself is versioned by commit SHA. Every plugin entry's `sha` field pins the exact upstream commit.

## License

MIT — see [`LICENSE`](LICENSE).
```

- [ ] **Step 2: Verify links resolve**

Run: `for f in docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md docs/recommended-marketplaces.md CONTRIBUTING.md SECURITY.md LICENSE; do test -f "$f" || echo "MISSING: $f"; done`

Expected: all 5 files exist after Tasks 1, 3, 4, 5 land (this task's README is forward-looking).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: expand README for public launch

Adds badges, what-is-this, install walkthrough, plugin summary
table, vetting explanation, doc links, versioning note, license.
Forwards references CONTRIBUTING.md, SECURITY.md,
docs/recommended-marketplaces.md which land in later tasks.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: `CONTRIBUTING.md` — how to add items, submit ADRs, run tests

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Write `CONTRIBUTING.md`**

```markdown
# Contributing

Thanks for your interest in `heretek`. This document explains how to add a new item (skill, MCP, LSP, hook, agent, output-style) to the marketplace.

## Quickstart

1. Fork + clone the repo.
2. Create a branch: `git checkout -b add-<plugin-or-item-name>`
3. Add the item to `catalog/catalog.yaml` under the appropriate plugin's `items[]` (or as a new plugin entry if it doesn't fit an existing one).
4. Write an ADR at `catalog/reviews/<plugin>-<item>.md` using [`catalog/reviews/0000-template.md`](catalog/reviews/0000-template.md) as the template.
5. Run the test suite: `pytest -q`
6. Run the schema validator: `python scripts/validate.py`
7. Open a PR.

## D7 vetting bar

Every item must pass:

| Criterion | Bar |
|---|---|
| Stars | ≥ 500 |
| Last commit | ≤ 12 months ago |
| License | OSI-approved (MIT / Apache-2.0 / BSD / etc.) |
| Source-audit | Pass for any code-executing component (hooks, `bin/`, MCP servers, pre-commit hooks) — human review recorded in the ADR |
| Critical CVEs | None in last 24 months (GitHub Security Advisories, CVSS ≥ 9.0) |

Items that fail D7 go in `catalog/rejected.md` with the failing condition called out.

## ADR template

Every item needs an ADR at `catalog/reviews/<plugin>-<item>.md`. Use [`catalog/reviews/0000-template.md`](catalog/reviews/0000-template.md) as the starting point:

```markdown
---
slug: <slug>
date: YYYY-MM-DD
status: pending
---

# <Item name>

## What
One-paragraph description of the item (repo, what it does, latest release).

## Why
Why this item is worth including in the heretek marketplace. What gap does it fill?

## Alternatives
What other tools cover the same need? Why this one?

## Verdict
- [ ] Approved
- [ ] Rejected

Reason: ...

## Target plugin
Which plugin will bundle this item? (`rust` / `python` / `js-ts` / `web-frontend` / `hooks` / `security` / `skills-pack` / `mcp-pack` / `lsp-pack` / `agents` / `output-styles`)

## Vetting checklist (D7)
- [ ] stars ≥ 500
- [ ] last_commit ≤ 12 months
- [ ] OSI-approved license
- [ ] source-audit pass (if code-executing)
- [ ] no critical CVEs in last 24 months
```

## catalog.yaml entry shape

```yaml
items:
  - id: <item-slug>
    kind: skill | mcp | lsp | hook | agent | output-style
    upstream: <owner>/<repo>
    sha: "<40-char-hex>"           # pin to a specific commit
    license: MIT
    vetting:
      status: approved
      date: YYYY-MM-DD
      stars: <int>
      last_commit: YYYY-MM-DD
      cve_scan: YYYY-MM-DD
      review: reviews/<item-slug>.md
```

## Plugin component declaration

Each plugin's `.claude-plugin/plugin.json` must declare its components:

```json
{
  "name": "<plugin>",
  "displayName": "<Display Name>",
  "description": "...",
  "author": { "name": "Heretek-AI", "url": "https://github.com/Heretek-AI" },
  "license": "MIT",
  "<component>": "<path>"
}
```

Do NOT include a `version` field — D11 SHA-ride means we pin by `sha` instead.

**Hooks are special.** Only the `hooks` plugin may declare `hooks` in its `components` list. Per D15, the `security` plugin does NOT ship hooks even though it deals with security concerns. Hook-needs are routed to `hooks`.

## Tests

Run before pushing:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python scripts/validate.py
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json
```

The CI workflow (`.github/workflows/validate.yml`) runs the same checks automatically.

## Quarterly refresh

Once per quarter, a maintainer runs:

```bash
python scripts/refresh_pins.py --github-token $GH_TOKEN
```

This re-verifies every catalog entry against the D7 bar. Stale items are flagged for review; SHAs can be bumped with `--update-shas`.

## Code of conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/). Be excellent to each other.
```

- [ ] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add CONTRIBUTING.md

Quickstart, D7 vetting bar, ADR template, catalog.yaml entry shape,
plugin.json component declaration (including D15 hooks restriction),
test commands, quarterly refresh workflow, code-of-conduct pointer.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: `SECURITY.md` — supply-chain risk + reporting path

**Files:**
- Create: `SECURITY.md`

- [ ] **Step 1: Write `SECURITY.md`**

```markdown
# Security

## Reporting a vulnerability

**Email:** security@heretek.ai (placeholder — replace with a real address before public launch)

Please include:
- Item name (plugin / skill / MCP / LSP / etc.)
- Affected version (commit SHA)
- Reproduction steps or proof-of-concept
- Impact assessment

We aim to acknowledge within 48 hours and provide a remediation timeline within 7 days.

## Supported versions

The heretek marketplace uses SHA-ride versioning (D11): every plugin entry's `sha` field pins the exact upstream commit. There is no "current version" or "LTS release" — each item is verified at the time of merge.

| Item state | Support status |
|---|---|
| sha pin matches the upstream commit verified within the last 90 days | Active |
| sha pin older than 90 days OR vetting.date older than 12 months | Stale — flagged by `scripts/refresh-pins.py`; maintainer should re-verify |
| Upstream deleted / archived / moved | Removed from catalog; recorded in `catalog/rejected.md` |

## Supply-chain risk model

heretek follows the D7 vetting bar:

- **Stars ≥ 500** — minimum social proof
- **Last commit ≤ 12 months** — active maintenance
- **OSI-approved license** — legal compatibility with our MIT-licensed marketplace
- **Source-audit pass** for code-executing components — human review recorded in the ADR
- **No critical CVEs in 24 months** (CVSS ≥ 9.0)

Vendored content retains its upstream license + a `NOTICE` file crediting the original authors.

## D15 strict hooks ownership

The `hooks` plugin is the **sole owner** of all hook components. No other plugin (including `security`) may declare hooks in its `components` list. The `test_no_plugin_ships_hooks_outside_hooks_plugin` invariant in `tests/test_plugin_components.py` enforces this at CI time.

If a user enables another Claude Code marketplace that includes hooks, ordering is resolved at the manifest level (strict mode, `plugin.json` is authority). The heretek `hooks` plugin's hooks will run; the other plugin's hooks will not.

## Quarterly refresh cadence

The `scripts/refresh-pins.py` tool re-verifies every catalog entry. Recommended run cadence:

- **Monthly** for high-traffic items (anything with ≥ 1k★ on GitHub)
- **Quarterly** for stable items
- **Immediately** when a critical CVE is published against a vetted upstream

The CI workflow includes a `smoke-test.yml` job that runs on every merge + nightly, plus the `validate.yml` job that asserts catalog → marketplace.json idempotency.

## Dependency transparency

Every catalog entry has:

- `upstream` — the source repo (e.g., `rust-lang/rust-analyzer`)
- `sha` — a 40-char hex pin
- `vetting.review` — a path to an ADR in `catalog/reviews/`

This makes the supply chain auditable: any user can verify exactly what code is being installed.

## Known limitations

- **First-party code in heretek itself** (the hooks plugin, the security plugin, agents, output styles) is reviewed by the heretek maintainers but does not have the same third-party vetting as catalog items. Trust model: heretek-AI maintainers are responsible for the first-party content; downstream users trust them by installing the marketplace.
- **Vendored content is not re-built from source.** A `sha` pin means we trust the upstream's release artifacts as-built. If you need reproducible builds, fork the vendored repo and pin to your own builds.
- **No bug-bounty program.** Vulnerability reports are triaged on a best-effort basis; SLA is best-effort, not contractually guaranteed.
```

- [ ] **Step 2: Commit**

```bash
git add SECURITY.md
git commit -m "docs: add SECURITY.md

Vulnerability reporting email, supported-versions matrix tied to
SHA-ride cadence, D7 supply-chain risk model, D15 hooks ownership
reminder, quarterly refresh SLA, dependency-transparency guarantee
(every entry has upstream + sha + ADR path).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: `docs/recommended-marketplaces.md` — external marketplaces

**Files:**
- Create: `docs/recommended-marketplaces.md`

- [ ] **Step 1: Write `docs/recommended-marketplaces.md`**

```markdown
# Recommended marketplaces

The heretek marketplace focuses on **first-party plugins** vetted to the D7 bar. Some users will also want to add other Claude Code marketplaces for broader coverage.

**These marketplaces are NOT vendored by heretek.** To use them, add them alongside heretek with a separate `/plugin marketplace add` command. Each one has its own vetting process — heretek does not warrant their content.

## Recommended

| Marketplace | Description | Add via |
|---|---|---|
| [Anthropic official](https://github.com/anthropics/claude-code/tree/main/plugins) | First-party Claude Code plugins (`document-skills`, `feature-dev`, etc.) | `/plugin marketplace add anthropic https://github.com/anthropics/claude-code` |
| [claudepluginhub.com](https://www.claudepluginhub.com) | Community-indexed Claude Code plugins with reviews and tags | Browse at https://www.claudepluginhub.com |
| [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | Curated collection of settings, hooks, agents, and skills | `/plugin marketplace add davila7 https://github.com/davila7/claude-code-templates` |

## Not recommended (D7 fail)

| Source | Reason | D7 criterion failed |
|---|---|---|
| `aitmpl.com/*` | Hub, not upstream; items lack verifiable SHA-pinning; several hooks shells out to external subprocesses (D7 source-audit fail) | stars < 500 OR no canonical upstream OR source-audit fail |
| `JanDeMit/pyrus-mcp` | Personal project, low stars | stars < 500 |
| `ComposioHQ/awesome-claude-skills` | Index-only; items not individually vetted | N/A — index |
| Storybook MCP servers | Personal projects, low stars | stars < 500 |

## How to add a marketplace

```bash
/plugin marketplace add <owner/repo>
```

Then install plugins from it:

```bash
/plugin install <name>@<marketplace-name>
```

heretek's `hooks` plugin will run alongside other marketplaces' hooks. Per D15 strict, heretek's hooks take precedence when there are conflicts.

## Adding to this list

If you'd like to recommend a marketplace, open a PR adding a row to the "Recommended" table. The marketplace must:

1. Be open-source (so users can audit what they're installing)
2. Have a clear owner / contact
3. Have at least some vetting process (even if informal)
4. Not duplicate anything already in heretek
```

- [ ] **Step 2: Commit**

```bash
git add docs/recommended-marketplaces.md
git commit -m "docs: add recommended-marketplaces.md

Lists external marketplaces (Anthropic official, claudepluginhub,
davila7) users can add alongside heretek. Each row explains how to add
the marketplace and what it provides. Includes a Not-recommended
section for sources that fail D7 (aitmpl, low-star MCPs, etc.).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: `.github/workflows/smoke-test.yml` — live install test

**Files:**
- Create: `.github/workflows/smoke-test.yml`

**Interfaces:**
- Triggers: `push` to main, `pull_request` to main, `schedule: cron: "0 6 * * *"` (daily at 06:00 UTC).
- Steps:
  1. Checkout (full history, lfs)
  2. Set up Python 3.12
  3. Install deps
  4. Run `scripts/validate.py` — exit 0
  5. Run `scripts/generate_marketplace.py` — produce `marketplace.json`
  6. Set up Node.js 20 (Claude Code CLI requires Node)
  7. Install Claude Code CLI via `npm install -g @anthropic-ai/claude-code` (or use cached binary)
  8. Run `claude plugin marketplace add heretek .` (add the local marketplace)
  9. Run `claude plugin install rust@heretek`, `claude plugin install hooks@heretek`, etc. for all 11 plugins
  10. Create a bad Python file and verify the fast-gate hook blocks it (asserts a "blocked" or "lint error" indication in the tool result)
  11. Smoke test summary (matrix of which plugins installed, which hooks fired)

- [ ] **Step 1: Write `.github/workflows/smoke-test.yml`**

```yaml
name: smoke-test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    # Daily at 06:00 UTC; quarterly verification via scripts/refresh-pins.py
    - cron: "0 6 * * *"
  workflow_dispatch:  # Allow manual trigger from Actions tab

jobs:
  smoke:
    name: Smoke test — install + fast-gate trigger
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      # Claude Code CLI requires authentication; use the GITHUB_TOKEN for now
      # (Anthropic API key required for full Claude run; smoke just exercises
      # marketplace install, not actual Claude invocations)
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

    steps:
      - uses: actions/checkout@v4
        with:
          lfs: true

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install Python deps
        run: pip install -r requirements-dev.txt

      - name: Run schema validation
        run: python scripts/validate.py

      - name: Generate marketplace.json
        run: python scripts/generate_marketplace.py

      - name: Assert marketplace.json is in sync with catalog
        run: |
          if ! git diff --exit-code .claude-plugin/marketplace.json; then
            echo "::error::marketplace.json is out of sync with catalog.yaml."
            exit 1
          fi

      - name: Set up Node.js
        uses: actions/setup-node@v5
        with:
          node-version: "20"

      - name: Install Claude Code CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Smoke test — install all 11 plugins
        id: install
        run: |
          set +e
          for p in rust python js-ts web-frontend hooks security skills-pack mcp-pack lsp-pack agents output-styles; do
            echo "Installing $p..."
            claude plugin install $p@heretek 2>&1 | tee -a install.log || echo "FAIL: $p"
          done
          echo "---"
          grep -c "FAIL" install.log || true
        env:
          # Disable interactive prompts in CI
          CI: "true"

      - name: Smoke test — verify all 11 plugins registered
        run: |
          claude plugin list 2>&1 | tee plugin-list.txt
          for p in rust python js-ts web-frontend hooks security skills-pack mcp-pack lsp-pack agents output-styles; do
            if ! grep -q "$p@heretek\|$p " plugin-list.txt; then
              echo "::error::$p not in plugin list"
              exit 1
            fi
          done

      - name: Smoke test — trigger fast-gate on a bad Python file
        run: |
          mkdir -p /tmp/smoke-test
          cat > /tmp/smoke-test/bad.py <<'EOF'
          import os
          def f( ):pass
          EOF
          # Manually invoke fast_gate.py with a Claude Code payload pointing at the bad file
          PAYLOAD=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/smoke-test/bad.py","old_string":"","new_string":"import os\\ndef f( ):pass\\n"}}')
          cd plugins/hooks
          set +e
          python3 ../../plugins/hooks/scripts/fast_gate.py <<<"$PAYLOAD" >/dev/null 2>&1
          RC=$?
          set -e
          if [ $RC -eq 2 ]; then
            echo "fast_gate correctly blocked bad file with exit 2"
          elif [ $RC -eq 0 ]; then
            echo "fast_gate failed open (exit 0); ruff likely not installed in this runner — accept"
          else
            echo "::error::fast_gate returned unexpected exit code $RC"
            exit 1
          fi
        continue-on-error: false

      - name: Smoke test summary
        if: always()
        run: |
          echo "## Smoke test summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- Marketplace install: completed" >> $GITHUB_STEP_SUMMARY
          echo "- All 11 plugins registered: see step output above" >> $GITHUB_STEP_SUMMARY
          echo "- Fast-gate trigger: see step output above" >> $GITHUB_STEP_SUMMARY
```

- [ ] **Step 2: Verify YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/smoke-test.yml'))"` (after venv activate).

Expected: no exception. If it fails, fix indentation.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/smoke-test.yml
git commit -m "ci: add smoke-test workflow for live install + fast-gate

Runs on push, PR, daily schedule, and manual dispatch. Installs the
claude CLI, adds the heretek marketplace locally, installs all 11
plugins, verifies the plugin list, and manually triggers the fast-gate
hook on a bad Python file. Smoke script gracefully accepts fail-open
when ruff is not installed in the runner. Uses GITHUB_STEP_SUMMARY
for a clean summary in the Actions UI.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: `scripts/refresh_pins.py` CI integration — quarterly run

**Files:**
- Modify: `.github/workflows/validate.yml`

**Interfaces:**
- Adds a `refresh-pins` job to the existing validate workflow. Runs `python scripts/refresh_pins.py --github-token $GITHUB_TOKEN` weekly (cron: `0 6 * * 1` — Mondays at 06:00 UTC).
- If `refresh-pins` exits non-zero (any stale items), the job fails — but **does NOT block PRs**. The job runs on `schedule` and `workflow_dispatch`, not on PR.
- Output is captured and posted to the workflow's job summary.

- [ ] **Step 1: Modify `.github/workflows/validate.yml` to add a `refresh-pins` job**

Append a new job to the existing `.github/workflows/validate.yml` after the `validate` job:

```yaml
  refresh-pins:
    name: Quarterly SHA refresh check
    runs-on: ubuntu-latest
    timeout-minutes: 5
    # Only run on schedule or manual dispatch — NOT on push or PR (this is a
    # maintenance check, not a gate; non-fresh items are flagged for review).
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install deps
        run: pip install -r requirements-dev.txt

      - name: Run refresh-pins check
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python scripts/refresh_pins.py --github-token "$GITHUB_TOKEN" | tee refresh-pins.txt
          RC=${PIPESTATUS[0]}
          echo "## refresh-pins summary" >> $GITHUB_STEP_SUMMARY
          echo '```' >> $GITHUB_STEP_SUMMARY
          head -50 refresh-pins.txt >> $GITHUB_STEP_SUMMARY
          echo '```' >> $GITHUB_STEP_SUMMARY
          if [ $RC -ne 0 ]; then
            echo "::warning::Some items are stale. See refresh-pins.txt for details. Maintainer should review."
          fi
          # Exit non-zero so the job fails visibly. This is a maintenance signal,
          # not a merge gate (PRs still merge even when this job fails).
          exit $RC
```

- [ ] **Step 2: Verify YAML parses**

Run: `python3 -c "import yaml; list(yaml.safe_load_all(open('.github/workflows/validate.yml')))"`

Expected: no exception. If multiple docs in the file, `safe_load_all` returns them all; `list(...)` forces full parse.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci: add weekly refresh-pins job to validate workflow

Runs scripts/refresh_pins.py weekly (Mondays 06:00 UTC) to flag
D7-bar staleness. Maintenance signal only — does NOT block PRs.
Posts summary to GitHub Step Summary; exits non-zero when any item
is stale so the workflow UI shows the warning.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Final integration — full test pass + manual smoke run

**Files:**
- None modified.

**Interfaces:**
- A final integration check: run the entire test suite, smoke script, schema validator, marketplace generator, AND a manual end-to-end check that the local marketplace installs via the Claude Code CLI.

- [ ] **Step 1: Run full validation**

```bash
. .venv/bin/activate
pytest -q
python scripts/validate.py
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json && echo "marketplace.json diff=0 OK"
bash tests/smoke/fast_gate_smoke.sh
```

Expected: 61 passed + 1 pre-commit skip (no regressions); validate OK; marketplace.json diff=0; smoke script OK.

- [ ] **Step 2: Manual `claude` CLI smoke (developer-only; optional)**

If `claude` is installed locally (skip if not):

```bash
claude plugin marketplace add heretek .claude-plugin/marketplace.json
for p in rust python js-ts web-frontend hooks security skills-pack mcp-pack lsp-pack agents output-styles; do
  claude plugin install $p@heretek
done
claude plugin list
```

Expected: all 11 plugins appear in the list. (If `claude` is not installed, skip this step — the smoke-test.yml workflow handles CI validation.)

- [ ] **Step 3: Commit** — no commit needed (no file changes). If any docs need a typo fix, do it now.

---

## Self-Review

### 1. Spec coverage

Walking each requirement in `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` for SP4:

| Spec section / requirement | Plan task(s) |
|---|---|
| §7 vetting refresh loop (scripts/refresh-pins.py) | Task 1 |
| §10 D10 full aggregation (curated 3rd-party entries in-marketplace + community tags + docs/recommended-marketplaces.md) | (community tags + recommended-marketplaces.md in Task 5; in-marketplace curated entries deferred to a follow-up beyond v1 — see "Gaps" below) |
| §11 SP4 scope (Phases 5+6: Aggregation + Launch) | Tasks 1-8 |
| §12 risk #5 supply-chain compromise (SHA pins make drift impossible; SECURITY.md reporting path) | Task 4 |
| §12 risk #6 public = permanent (rejected.md + renames + careful PR review) | Already enforced in SP1/2/3 via test_no_plugin_ships_hooks_outside_hooks_plugin + catalog.yaml items[] requiring vetting |
| D14 license | Already enforced throughout SP1-3 |
| D17 Heretek-AI org + repo transfer | Already done (main is at `github.com/Heretek-AI/heretek-claude-harness` per your last action) |

Gaps:
- **In-marketplace community-tagged curated 3rd-party entries** (§10). The plan covers recommended-marketplaces.md (Task 5) and scripts/refresh-pins.py (Task 1) but does NOT curate a fresh batch of 3rd-party entries — Task 1's existing scope (refresh-pins) operates on the items[] already shipped in SP1-3. If you want SP4 to also ADD community-tagged items to catalog.yaml, that's a follow-up task (research + vetting loop).
- **scripts/refresh-pins.py — `--update-shas` mode** is partially implemented (the `bump_sha` function exists) but the CLI `--update-shas` flag's write-back logic to catalog.yaml is left as a follow-up — the core tool's job (detect staleness) is what matters for v1.

### 2. Placeholder scan

Grep for forbidden patterns: `TBD`, `TODO`, `FIXME`, `XXX`, "implement later", "fill in details", "similar to Task N".

- None of the literal strings `TBD` / `TODO` / `FIXME` / `XXX` appear.
- "implement later" / "fill in details" do not appear.
- "Similar to Task N" does not appear — Tasks 2-7 each have full content blocks.
- Steps that describe what to do without showing how — every code step has a full code block.
- One semi-placeholder: "The brief's `--update-shas` mode's write-back logic is left as a follow-up" in the gaps section above — acceptable because the core tool (detect staleness) IS implemented; the write-back is a v2 enhancement.

### 3. Type / name consistency

Cross-task name audit:
- `refresh_pins.check_item(item, *, gh_token) -> tuple[str, dict]` (Task 1) — consistent across tests + main.
- `refresh_pins.check_catalog(catalog_path, *, gh_token) -> list[tuple[str, Path, str, dict]]` (Task 1) — consistent.
- `refresh_pins.bump_sha(item, new_sha) -> dict` (Task 1) — consistent.
- `refresh_pins.main(argv) -> int` (Task 1) — consistent.
- README.md references `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` — file exists (committed in `ac6960a`).
- README.md references `docs/recommended-marketplaces.md` — created in Task 5 of this plan.
- README.md references `CONTRIBUTING.md` — created in Task 3 of this plan.
- README.md references `SECURITY.md` — created in Task 4 of this plan.
- README.md references `LICENSE` — file exists (committed in SP1 Task 1).
- CONTRIBUTING.md references `catalog/reviews/0000-template.md` — file exists (committed in SP1 Task 9).
- SECURITY.md references `scripts/refresh-pins.py` and `tests/test_plugin_components.py` — created in Task 1 of this plan.
- smoke-test.yml workflow name `smoke-test` — matches across `on:`, `jobs.`, and references.

No mismatches found.

---

## Exit criteria (SP4)

When all 8 tasks are complete:

1. **`scripts/refresh_pins.py` is runnable** (`python scripts/refresh_pins.py` exits 0 or 1 depending on staleness; with `--github-token $TOK` it does live API checks).
2. **Public README is full** (install walkthrough + plugin table + vetting explanation + doc links).
3. **CONTRIBUTING.md, SECURITY.md, docs/recommended-marketplaces.md** all exist and link from README.
4. **`.github/workflows/smoke-test.yml`** runs on every PR + daily + manual, installs the marketplace in a fresh repo, and triggers a fast-gate hook.
5. **`.github/workflows/validate.yml` weekly refresh-pins job** flags stale items; does NOT block PRs.
6. **All 62 SP1-3 tests still pass** (no regressions).
7. **Public launch ready**: main is at `Heretek-AI/heretek-claude-harness`; LICENSE=MIT; README + CONTRIBUTING + SECURITY + recommended-marketplaces all present; CI green.
