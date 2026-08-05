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
