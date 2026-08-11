---
description: Research and add a vetted third-party item to the heretek marketplace (add-item mode) OR scaffold a new plugin with its first items (add-plugin mode). Uses the D7 vetting bar and writes ADRs per item.
---

# heretek:catalog

Two modes: `add-item` (extend existing plugin) or `add-plugin` (scaffold new).

## D7 vetting bar (CI-enforced)

Every item must pass:

- Stars ≥ 500 (first-party exempt)
- Last commit ≤ 12 months
- License OSI-approved (SPDX id)
- Source-audit pass for code-executing components
- No critical CVEs in last 24 months

## Pipeline

1. **Research** — `gh api repos/{owner}/{repo}` for stars/license/last_commit;
   `gh api .../security-advisories` for critical CVEs.
2. **ADR** — write `catalog/reviews/<plugin>-<item>.md` per
   `catalog/reviews/0000-template.md`. Use real research data, no placeholders.
3. **Catalog** — append to `catalog/catalog.yaml` with full vetting block
   (`status`, `date`, `stars`, `last_commit`, `cve_scan`, `review`).
4. **Content** — write per-kind: `plugins/<plugin>/skills/<name>/SKILL.md`,
   `plugins/<plugin>/.mcp.json`, etc.
5. **Manifest** — update `plugins/<plugin>/.claude-plugin/plugin.json`
   (no `version` field — D11 SHA-ride).
6. **D15 check** — refuse if non-`hooks` plugin declares hooks.
7. **Validate** — `scripts/ci.sh` (pytest + validate + generate + smoke).
8. **Commit** — `feat(catalog): add <item-slug> to <plugin> plugin`.

## ADR template

- `slug:`, `date:`, `status: pending`
- **What** — repo, scope, latest release
- **Why** — gap filled in heretek
- **Alternatives** — what other tools cover the same need
- **Verdict** — Approved / Rejected with reason
- **Vetting checklist** — 5 D7 criteria with PASS/FAIL

## Don't

- Auto-create PRs (manual step)
- Remove existing items
- Modify the D7 bar itself
