# CLAUDE.md

Guidance for Claude Code operating in this repo (the `heretek` Claude Code plugin marketplace).

## What this repo is

Monorepo + source of truth for the `heretek` marketplace (11 first-party plugins + curated 3rd-party). `catalog/catalog.yaml` is the source of truth; `.claude-plugin/marketplace.json` is **generated** from it by `scripts/generate_marketplace.py` — never hand-edit the generated file.

## Common commands

```bash
# Full local CI (must pass before PR)
pytest -q                            # unit tests; add -m integration for scanner tests
python scripts/validate.py           # schema validation against catalog.yaml + manifests
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json  # must be clean

# Quarterly: re-verify D7 bar (stars/license/last_commit/CVEs) and bump SHAs
python scripts/refresh_pins.py --github-token $GH_TOKEN
python scripts/refresh_pins.py --github-token $GH_TOKEN --update-shas  # round-trips via ruamel.yaml to preserve comments

# New plugin skeleton
python scripts/new_plugin.py
```

CI runs the same steps in `.github/workflows/validate.yml` (PR + push to main + weekly Monday 06:00 UTC). `.github/workflows/security-scan*.yml` run scanners in `scripts/scanners/` and `scripts/security_scan.py`.

## Project layout

- `catalog/catalog.yaml` — source of truth (plugins + items[], vetting, SHA pins)
- `catalog/reviews/<plugin>-<item>.md` — ADR per item (required for `vetting.status: approved`)
- `catalog/rejected.md` — items that failed D7
- `catalog/forbidden_patterns.yaml` — fast-gate scanner deny-list
- `plugins/*/` — first-party plugin sources (relative sources per D1)
- `.claude-plugin/marketplace.json` — generated; commit the diff
- `scripts/` — Python 3.10+ (PyYAML, jsonschema, requests, ruamel.yaml). `scanners/` subdir holds fast-gate scanners
- `tests/` — pytest; `tests/schemas/` JSON schemas; `tests/fixtures/` D7 fixtures
- `docs/superpowers/{specs,plans,reviews,spikes,research,issue-drafts}` — design + audit trail

## D7 vetting bar (CI-enforced)

Every `items[]` entry must pass:

| Criterion | Bar |
|---|---|
| Stars | ≥ 500 (first-party exempt — `stars: 0` + `cve_scan: not-applicable`) |
| Last commit | ≤ 12 months ago |
| License | OSI-approved (SPDX id) |
| Source-audit | Pass for code-executing components (hooks, `bin/`, MCP servers, pre-commit) — recorded in ADR |
| CVEs | No critical CVEs in last 24 months |
| Vetting record | `vetting.status: approved` + `vetting.review` pointing to `catalog/reviews/*.md` |

First-party self-pins use `sha: "first-party-style"` etc. — not subject to external SHA pin.

## Hooks plugin (flagship)

`plugins/hooks/` owns ALL hook components per D15. Other plugins must not ship hooks. The fast gate (`plugins/hooks/scripts/`) runs subd-100ms on every Edit/Write/MultiEdit and blocks the agent loop. Slow analyzers run on demand via `/quality-gate:run`. Git hooks install via `plugins/hooks/install.sh`.

## Versioning

No `version` field on first-party plugins (D11 SHA-ride). Marketplace version = commit SHA. Every entry's `sha` pins exact upstream commit — bump via `refresh_pins.py --update-shas`.

## Conventions

- Python 3.10+; tests use `pytest` with markers (`integration` = needs network/secrets)
- Catalog uses `ruamel.yaml` round-trip to preserve comments — do not reformat
- ADRs follow `catalog/reviews/0000-template.md`
- New items: add to `catalog.yaml` + write ADR + run validation. See `CONTRIBUTING.md`
- Supply-chain incidents: see `SECURITY.md` (GitHub Security Advisories intake for v1.0.0)

## Don't

- Hand-edit `.claude-plugin/marketplace.json` (regenerated)
- Add hooks to non-`hooks` plugins
- Lower D7 bar without an ADR
- Commit secrets — `gitleaks` and scanners in `scripts/scanners/` run in CI
