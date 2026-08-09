# Heretek Marketplace — Plan

> One-page TL;DR. Full roadmap at `docs/superpowers/roadmap.md`. Design spec at `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md`.

## Status

v1.0.0 shipped 2026-08-05 (CHANGELOG). v1.x frozen.

## Active phases

| Phase | Scope | Tracking |
|---|---|---|
| v2 | Hooks + security | #89 |
| v3 | MCP/ACI | #90 |
| v3.5 | Observability (in flight) | #109-#124 + new tracking issue |
| v4 | Workflow + eval | #91 |
| v5 | BYOK + local | new tracking issue |
| v6 | Meta-harness + ACP | new tracking issue |

## Common commands

```bash
pytest -q
python scripts/validate.py
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json
```

## See also

- `docs/superpowers/roadmap.md` — phased roadmap
- `docs/superpowers/specs/` — design specs
- `docs/superpowers/plans/` — implementation plans
- `catalog/` — source of truth for plugin catalog
- `CONTRIBUTING.md` — contribution guide
- `SECURITY.md` — security reporting
