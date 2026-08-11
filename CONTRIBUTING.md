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

## Pre-commit framework

A `pre-commit` framework config lives at `plugins/hooks/.pre-commit-config.yaml`
and runs hygiene, Ruff, Biome, shellcheck, gitleaks, and the heretek fast gate
on every `git commit` and `git push`. To install it locally:

```bash
# Install the framework
pip install pre-commit

# Bind it to this repo (idempotent)
python3 -m pre_commit install --config plugins/hooks/.pre-commit-config.yaml
```

To run the full suite manually without committing:

```bash
python3 -m pre_commit run --all-files --config plugins/hooks/.pre-commit-config.yaml
```

If a hook fails, fix the issue (or use `git commit --no-verify` to bypass — but
this is **discouraged**; the CI workflow `.github/workflows/pre-commit.yml`
will block the PR anyway). The install is also bundled into the hooks plugin:

```bash
/plugin install hooks@heretek
/hooks:install-git-hooks
```

## ShellCheck

CI enforces [ShellCheck](https://www.shellcheck.net/) on every `*.sh` file. To run locally:

```bash
# Install (pick one):
#   Ubuntu/Debian: sudo apt-get install shellcheck
#   macOS:         brew install shellcheck

shellcheck -x --severity=warning $(find . -name '*.sh' -not -path '*/.claude/worktrees/*' -not -path '*/node_modules/*')
```

The pre-commit hook (installed via `plugins/hooks/install.sh`) also runs ShellCheck on changed scripts before each commit.

## Quarterly refresh

Once per quarter, a maintainer runs:

```bash
python scripts/refresh_pins.py --github-token $GH_TOKEN
```

This re-verifies every catalog entry against the D7 bar. Stale items are flagged for review; SHAs can be bumped with `--update-shas`.

## Code of conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/). Be excellent to each other.
