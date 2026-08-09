# Enforcement Surface Audit (Spec 3 of 3) — Audit-the-Auditors

## Goal

Hostile audit of the heretek enforcement surface — the scripts, CI gates, and
hooks that *claim* to enforce quality standards — against the question:
**does the enforcement actually catch what it should?**

This is **Spec 3 of 3** in a full-repo audit decomposition:

| Spec | Scope | Question it answers |
|------|-------|---------------------|
| 1 | Harness self-audit: `scripts/`, `tests/`, `plugins/hooks/`, root configs + root docs | Do *we* meet the bar in the code we own? |
| 2 | First-party plugins marketplace: `plugins/*/`, `catalog/catalog.yaml`, D7 vetting | Do the plugins we ship meet the bar? |
| **3 (this spec)** | Enforcement surface: `scripts/scanners/`, `scripts/validate.py`, `.github/workflows/`, hooks enforcement behavior | Does the enforcement actually catch what it should? |

Spec 1 audited the enforcement scripts as **code** (readability, complexity,
correctness). Spec 3 audits them as **enforcement** — do they have gaps, false
negatives, or bypass paths? Same files, different question.

## In scope

- `scripts/scanners/` — fast-gate scanners (`ast_grep_scanner.py`,
  `forbidden_pattern_scanner.py`, `base.py`, `lsp.py`, `mcp.py`, `skills.py`)
- `scripts/validate.py` — schema validation against `catalog.yaml` + manifests
- `scripts/generate_marketplace.py` — marketplace JSON generator (enforcement
  of D11: never hand-edit generated file)
- `scripts/refresh_pins.py` — quarterly D7-bar verification (enforcement of
  freshness: stars, last_commit, license, CVEs)
- `.github/workflows/` — CI gates: `validate.yml`, `smoke-test.yml`,
  `security-scan.yml`, `security-scan-pr.yml`, `security-scan-digest.yml`,
  `shellcheck.yml`, `spec-issue-hygiene.yml`
- `plugins/hooks/` — hook enforcement behavior (fast-block, slow-command,
  pre-commit); Spec 1 audited hooks as **code**, Spec 3 audits them as
  **enforcement**

## Out of scope

- Plugin code quality (Spec 2)
- Harness code quality (Spec 1)
- Root docs that drive behavior (`CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`) — audited as docs in Spec 1
- Code changes (audit produces findings + issues; fixing is downstream)
- External CI/CD (only `.github/workflows/` in this repo)

## Cluster breakdown (5 parallel research lanes)

| ID | Cluster | What it covers |
|----|---------|----------------|
| A | Scanner coverage & false negatives | Do the fast-gate scanners catch what CLAUDE.md §D7 + `catalog/forbidden_patterns.yaml` claims? Gap analysis: patterns not scanned, code-executing components not checked |
| B | CI gate completeness | Does every PR trigger validation? Are there bypass paths? Do all workflows fail loud on violation? Are there missing gates for new categories? |
| C | Vetting bar enforcement | Does `validate.py` enforce D7 bar on `catalog.yaml` entries? Does `refresh_pins.py` catch stale stars/license/last_commit/CVEs? Are there items that slip through? |
| D | Hook enforcement behavior | Do hooks actually block the agent loop on violation? Fast-gate latency < 100ms? Slow analyzers reachable via `/quality-gate:run`? Git hooks (pre-commit/pre-push) wired correctly? |
| E | Audit-the-auditors meta | Cross-cutting: are enforcement scripts themselves tested? Do scanner tests cover edge cases? Are there TODO/FIXME in enforcement code? Do findings from Spec 1's code-quality audit of these same files indicate fragility? |

## Per-finding schema

Identical to Spec 1/2 — reused from `scripts/audit/`:

```yaml
- finding_id: "X-NNN"
  cluster: "<cluster name>"
  principle: "<enforcement gap or bypass>"
  severity: critical | high | medium | low | info
  adversarial_posture: violated | partial | justified
  evidence:
    code_refs: ["<file>:<line>"]
    file: "<relative path>"
    line_range: "<start>-<end>"
    metric: "<measured value>"
  failure_scenario: "<concrete bypass scenario>"
  recommended_action: refactor | document | suppress | accept | escalate
  rationale: "<one sentence>"
  principle_reference: "<cluster> > <specific gap>"
  drift_signals: []
```

## Severity mapping

| Severity | Meaning | Auto-issue? |
|----------|---------|-------------|
| critical | Enforcement bypass that allows D7-bar regression to ship (e.g., missing CI gate, scanner gap for code-executing components) | P0 |
| high | Enforcement gap that increases risk but isn't a direct bypass (e.g., scanner doesn't cover new pattern type, hook latency > 100ms) | P1 |
| medium | Partial enforcement; catches some violations but not all variants | Report only |
| low | Enforcement exists but has minor gaps (e.g., missing test for edge case) | Report only |
| info | Observation about enforcement architecture; no action needed | Report only |

## Auto-issue rules

Same as Spec 1/2:
- Labels: `audit`, `enforcement-audit`, `principles-audit`, `P0` (critical) or
  `P1` (high), plus `audit-2026-08-09`
- Cap: 5 issues per cluster → umbrella for overflow
- Repo: `Heretek-AI/heretek-claude-harness`
- GitHub access: **GitHub MCP only**

## Synthesis pass

Same pipeline as Spec 1/2 — `scripts/audit/synthesis.py` reused.
Report filename: `audit-enforcement-YYYY-MM-DD.{md,json}`

## Key enforcement mechanisms to verify

### Fast-gate scanners (`scripts/scanners/`)

| Scanner | Claims to catch | Verify |
|---------|----------------|--------|
| `forbidden_pattern_scanner.py` | Patterns listed in `catalog/forbidden_patterns.yaml` | Does it match every pattern? Are there regex edge cases? |
| `ast_grep_scanner.py` | AST-level code patterns | What languages supported? What patterns defined? |
| `lsp.py` | LSP server issues in plugin manifests | Does it validate `lsp` kind items? |
| `mcp.py` | MCP server issues in plugin manifests | Does it validate `mcp` kind items? |
| `skills.py` | Skills pack issues | Does it validate `skill` kind items? |

### CI workflows (`.github/workflows/`)

| Workflow | Claims to enforce | Verify |
|----------|-------------------|--------|
| `validate.yml` | Schema validation on every PR | Runs on all PRs? Blocks merge? |
| `smoke-test.yml` | End-to-end smoke test | Covers critical paths? |
| `security-scan.yml` | Secret scanning, CVE detection | Covers all code-executing components? |
| `shellcheck.yml` | Shell script quality | Matches pre-commit hook severity? |
| `spec-issue-hygiene.yml` | Issue/PR hygiene | Enforces naming conventions? |

### Hook enforcement (`plugins/hooks/`)

| Mechanism | Claims to enforce | Verify |
|-----------|-------------------|--------|
| Fast-gate (PreToolUse) | Blocks agent loop on violation, < 100ms | Actual latency measured? Blocks on what? |
| Slow analyzers | On-demand via `/quality-gate:run` | Actually callable? Produces output? |
| Git hooks (pre-commit) | Blocks commits on violation | Installed correctly? Severity threshold matches CI? |

## Risks / failure modes

| Risk | Mitigation |
|------|------------|
| Enforcer itself has bugs (circular: who audits the auditor?) | Cluster E explicitly addresses this — meta-audit of enforcement code quality |
| Enforcement claims in CLAUDE.md don't match actual code | Cluster A cross-references CLAUDE.md claims against scanner implementations |
| CI bypass via branch protection settings | Cluster B checks workflow trigger conditions; can't verify branch protection via API but flags the gap |
| Hook enforcement is Claude-Code-only (not portable) | Finding if hooks claim cross-platform enforcement but only work on one harness |

## Files this spec will produce

- `docs/superpowers/specs/2026-08-09-heretek-enforcement-audit-design.md` (this file)
- `catalog/reviews/audit-enforcement-YYYY-MM-DD.md` (audit report)
- `catalog/reviews/audit-enforcement-YYYY-MM-DD.json` (machine-readable findings)
- N GitHub issues (HIGH/CRITICAL only, capped at 5/cluster + 1 umbrella/cluster)
- `docs/superpowers/plans/2026-08-09-heretek-enforcement-audit-plan.md` (implementation plan)

## Reuse from Spec 1

Same toolkit reuse as Spec 2:
- `validate.py`, `findings.py`, `synthesis.py`, `issues.py`, `harness_self.py`
- New cluster definitions for the 5 enforcement-specific lanes
