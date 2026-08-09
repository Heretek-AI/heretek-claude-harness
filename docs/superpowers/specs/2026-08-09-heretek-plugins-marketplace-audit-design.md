# First-Party Plugins Marketplace Audit (Spec 2 of 3) — Hostile Principles Audit

## Goal

Hostile audit of every first-party plugin shipped by the heretek marketplace
against the same principles of software engineering applied in Spec 1.
Output: a ranked findings report + one GitHub issue per HIGH/CRITICAL finding.

This is **Spec 2 of 3** in a full-repo audit decomposition:

| Spec | Scope | Question it answers |
|------|-------|---------------------|
| 1 | Harness self-audit: `scripts/`, `tests/`, `plugins/hooks/`, root configs + root docs | Do *we* meet the bar in the code we own? |
| **2 (this spec)** | First-party plugins marketplace: `plugins/*/` (excluding `plugins/hooks/`), `catalog/catalog.yaml`, D7 vetting enforcement on plugin items | Do the plugins we ship meet the bar? |
| 3 | Enforcement surface: `scripts/scanners/`, `scripts/validate.py`, `.github/workflows/`, hooks (audit-the-auditors) | Does the enforcement actually catch what it should? |

The cuts overlap intentionally. Plugin code is audited as **code** in Spec 2
(readability, complexity, correctness of the plugin itself). The same plugin's
**vetting record** (D7 bar compliance, ADR quality, catalog entry consistency)
is also audited in Spec 2. Spec 3 separately asks whether the enforcement
scripts and CI gates actually catch vetting regressions.

## In scope

- `plugins/agents/`, `plugins/js-ts/`, `plugins/lsp-pack/`, `plugins/mcp-pack/`,
  `plugins/output-styles/`, `plugins/python/`, `plugins/rust/`, `plugins/security/`,
  `plugins/skills-pack/`, `plugins/web-frontend/` — all first-party plugins except
  `plugins/hooks/` (hooks is harness-critical and already covered by Spec 1)
- `catalog/catalog.yaml` — source of truth for plugin items, vetting status, SHA pins
- `catalog/reviews/*.md` — ADRs documenting vetting decisions per item
- Per-plugin `.claude-plugin/plugin.json` manifests
- D7 vetting bar compliance: stars, last_commit, license, source-audit, CVEs,
  vetting record (status + review link)

## Out of scope

- `plugins/hooks/` — audited as harness code in Spec 1
- `.claude-plugin/marketplace.json` — generated file; audit concerns the
  generator (`scripts/generate_marketplace.py`) in Spec 1, not the output
- Enforcement behavior (does CI actually catch D7 regressions?) — Spec 3
- Code changes (audit produces findings + issues; fixing is downstream)
- Third-party items in catalog (only first-party plugins)

## Cluster breakdown (5 parallel research lanes)

Each cluster is one Explore-agent dispatch. Clusters are independent — no
shared state. The per-finding schema is identical to Spec 1 (reused from
`scripts/audit/`).

| ID | Cluster | What it covers |
|----|---------|----------------|
| A | Plugin code quality | Readability, naming, complexity, dead code, copy-paste, test coverage per plugin |
| B | Plugin architecture | SOLID, composition, separation of concerns, module boundaries across plugin dirs |
| C | D7 vetting compliance | Every `items[]` entry in `catalog/catalog.yaml` — stars bar, last_commit freshness, license SPDX, source-audit status, CVE scan, review link presence |
| D | Catalog & manifest consistency | `catalog.yaml` ↔ `.claude-plugin/plugin.json` ↔ actual plugin directory structure; SHA pin format, vetting record completeness |
| E | Plugin docs & onboarding | Per-plugin README accuracy, install instructions, usage examples; cross-references to catalog and ADRs |

## Per-finding schema

Identical to Spec 1 — the existing `tests/schemas/audit_finding.schema.json`
and `scripts/audit/` toolkit are reused without modification. Each finding card:

```yaml
- finding_id: "X-NNN"          # cluster letter + sequential number
  cluster: "<cluster name>"
  principle: "<principle violated>"
  severity: critical | high | medium | low | info
  adversarial_posture: violated | partial | justified
  evidence:
    code_refs: ["<file>:<line>"]
    file: "<relative path>"
    line_range: "<start>-<end>"
    metric: "<measured value>"
  failure_scenario: "<concrete inputs/state -> wrong output/crash>"
  recommended_action: refactor | document | suppress | accept | escalate
  rationale: "<one sentence>"
  principle_reference: "<cluster> > <specific principle>"
  drift_signals: []
```

## Severity mapping

| Severity | Meaning | Auto-issue? |
|----------|---------|-------------|
| critical | D7-bar regression risk, shipped plugin with wrong license, or data-loss bug in plugin | P0 |
| high | Clear violation; fix belongs on the roadmap but isn't blocking | P1 |
| medium | Partial compliance; mostly met with minor gaps | Report only |
| low | Minor inconsistency; cosmetic or documentation-only | Report only |
| info | Observation; no action needed | Report only |

## Auto-issue rules

Same as Spec 1:
- HIGH and CRITICAL findings auto-create GitHub issues
- Labels: `audit`, `plugins-marketplace-audit`, `principles-audit`, `P0`
  (critical) or `P1` (high), plus `audit-2026-08-09` (cross-audit searchability)
- Cap: 5 issues per cluster → remainder bundled into one umbrella issue per cluster
  (`[audit:spec-2:<cluster>] N additional findings from plugins marketplace audit`)
- Repo: `Heretek-AI/heretek-claude-harness`
- GitHub access: **GitHub MCP only** (`mcp__github__github-issue_write`)

## Synthesis pass

Same pipeline as Spec 1 — `scripts/audit/synthesis.py` reused:
1. Load all 5 cluster result files (A-E) via `audit.findings.load_findings`
2. Filter SonarCloud exclusions
3. Dedupe by `(file, line_range)` keeping higher-severity entry
4. Sort by severity
5. Write markdown report + JSON findings to `catalog/reviews/`
6. Coverage gap detection (missing clusters, zero-finding clusters)

Report filename: `audit-plugins-marketplace-YYYY-MM-DD.{md,json}`

## Verification

- Cluster agent output validated against the same `audit_finding.schema.json`
- Synthesis re-runs metrics on flagged files; drops finding if metric doesn't reproduce
- Every `critical` finding re-inspected at cited file:line
- Every `high` finding re-inspected unless numeric metric + tool output present

## Risks / failure modes

| Risk | Mitigation |
|------|------------|
| Plugin directory staleness (catalog says one SHA, directory has different code) | Cluster C cross-checks `catalog.yaml` SHA pins against `git log` for each plugin dir |
| D7 bar drift (stars/license thresholds change) | Findings reference the bar as documented in CLAUDE.md §D7; if bar changed, findings flag drift |
| Overlap with Spec 1 on `plugins/hooks/` | Explicitly excluded — hooks plugin audited only in Spec 1 |
| False-positive auto-issues | Same synthesis gate as Spec 1; no issue creation without re-verification |

## Files this spec will produce

- `docs/superpowers/specs/2026-08-09-heretek-plugins-marketplace-audit-design.md` (this file)
- `catalog/reviews/audit-plugins-marketplace-YYYY-MM-DD.md` (audit report)
- `catalog/reviews/audit-plugins-marketplace-YYYY-MM-DD.json` (machine-readable findings)
- N GitHub issues (HIGH/CRITICAL only, capped at 5/cluster + 1 umbrella/cluster)
- `docs/superpowers/plans/2026-08-09-heretek-plugins-marketplace-audit-plan.md` (implementation plan)

## Reuse from Spec 1

The entire `scripts/audit/` toolkit is reused without modification:
- `validate.py` — JSON Schema validation for finding cards
- `findings.py` — Finding dataclass + load/save
- `synthesis.py` — Dedupe + rank + report writer
- `issues.py` — GitHub MCP payload builder (cap + umbrella)
- `harness_self.py` — CLI driver (emit-prompts / synthesize / build-issues)

The only new artifact is `prompts.py` cluster definitions for the 5 plugin-specific
lanes (replacing the harness-specific A-E templates from Spec 1). These will be
added as new constants in `prompts.py` or as a separate `plugin_prompts.py`.
