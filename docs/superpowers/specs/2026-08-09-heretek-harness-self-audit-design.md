# Harness Self-Audit (Spec 1 of 3) — Hostile Principles Audit

## Goal

Hostile audit of the heretek-claude-harness self-hosted code against the principles
of software engineering (code quality + best practices + meta-principles).
Output: a ranked findings report + one GitHub issue per HIGH/CRITICAL finding.

This is **Spec 1 of 3** in a full-repo audit decomposition:

| Spec | Scope | Question it answers |
|------|-------|---------------------|
| **1 (this spec)** | Harness self-audit: `scripts/`, `tests/`, `plugins/hooks/`, root configs + root docs that drive behavior | Do *we* meet the bar in the code we own? |
| 2 | First-party plugins marketplace (agents/, skills/, output-styles/, commands/) | Do the plugins we ship meet the bar? |
| 3 | Enforcement surface: `scripts/scanners/`, `scripts/validate.py`, `.github/workflows/`, hooks (audit-the-auditors) | Does the enforcement actually catch what it should? |

The cuts overlap intentionally. `scripts/scanners/` is audited twice — once as
**code** in Spec 1 (readability, complexity, correctness), once as
**enforcement** in Spec 3 (does it catch what it claims?). Same with
`.github/workflows/`. Each question gets asked cleanly.

## In scope

- `scripts/*.py` — `validate.py`, `generate_marketplace.py`, `refresh_pins.py`,
  `new_plugin.py`, `suppression.py`, `drift_detector.py`, `freshness_*.py`,
  `issue_drafter.py`, `scanner_base.py`, etc. (the harness Python)
- `scripts/scanners/*.py` — audited here as **code**; enforcement angle deferred to Spec 3
- `tests/` — pytest suite, `conftest.py`, fixtures, `detection/`, `enforcement/`,
  `freshness_eval/`, `vision/`, `smoke/`, `schemas/`
- `plugins/hooks/` — the flagship hook plugin (owns ALL hook components per D15);
  audited here as a **plugin** but its code shape is harness-critical
- Root configs: `pyproject.toml`, `sonar-project.properties`,
  `requirements.txt`, `requirements-dev.txt`, `requirements.lock.txt`, `.gitignore`
- Root docs that drive behavior: `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`

## Out of scope (deferred or excluded)

- `catalog/` — data, not code; covered indirectly by Spec 3's enforcement audit
- `docs/superpowers/{specs,plans,reviews,spikes,research,issue-drafts}/` — design artifacts
- `plugins/*/` other than `plugins/hooks/` → Spec 2
- `.github/workflows/` enforcement behavior → Spec 3 (Spec 1 only asks "are they readable/maintainable?")
- `.omc/`, `.agents/`, `.claude/`, `.superpowers/` — harness control surface; not auditable source code
- `README.md`, `LICENSE`, `CHANGELOG.md` — boilerplate
- Catalog data files (`catalog.yaml`, `catalog/reviews/`, `catalog/rejected.md`, `catalog/forbidden_patterns.yaml`) — data

## Boundaries

- No code changes during the audit
- No auto-closing of issues
- No new ADRs (audit findings may *trigger* ADRs later, but the audit itself only produces findings + issues)

## Methodology — 5 cluster lanes (Option A)

Single-pass adversarial per cluster, parallelized via 5 Explore-agents.
Pattern mirrors the proven 2026-08-08 issue-codebase audit. Each cluster is
independent — no shared state, no cluster coordination.

| ID | Cluster | Principles covered | Primary evidence |
|----|---------|-------------------|------------------|
| A | Readability & quality bar | Small focused functions, naming, comments-why-not-what, DRY, KISS, dead code, duplication | File/function size, cyclomatic + cognitive complexity, lint output, line counts, duplication scan |
| B | Design & architecture | SOLID, composition-over-inheritance, Tell-don't-ask, Law of Demeter, separation of concerns, loose coupling/high cohesion | Import graph, class/method counts, god-file detection, base-class fanout, module boundaries |
| C | Correctness & safety | Error handling, input validation, type safety, idempotency, immutability, defensive programming | try/except scan, type-hint coverage scan, mutability patterns, parameter validation markers |
| D | Testing & verification | Test pyramid, isolation, coverage, TDD evidence, flaky markers, test smells, mutation-test indicators | pytest markers, conftest review, test counts per source module, fixture audit, commit history TDD check |
| E | Operations & docs | Observability, CI/CD maturity, feature flags, rollback, security hygiene, doc freshness, ADRs, onboarding | log/print scan, requirements freshness, GH workflow audit (readability only), docstring coverage, README freshness |

## Per-finding schema

Each cluster agent returns one card per finding:

```yaml
- finding_id: A-001                    # <cluster_letter>-<NNN>, deterministic
  cluster: "Readability & quality bar"
  principle: "Small, focused functions"
  severity: critical | high | medium | low | info
  adversarial_posture: violated | partial | justified
  evidence:
    code_refs: ["scripts/validate.py:124-187"]
    file: "scripts/validate.py"
    line_range: [124, 187]
    metric: "cognitive_complexity=42 (threshold=15, repo p95=12)"
  failure_scenario: "When a plugin manifest has 5 nested conditional branches, this function returns the wrong D7 status because the early-exit path is missed."
  recommended_action: refactor | document | suppress | accept | escalate
  rationale: "<one sentence — the why, not the what>"
  principle_reference: "Code quality → Maintainability → 'small, focused functions'"
  drift_signals: ["pr-149 already flagged S3516 here — duplicate?"]
```

## Severity model

| Severity | Definition |
|----------|-----------|
| critical | Principle violated in a way that risks user-visible harm, D7-bar regression, or data loss |
| high | Clear violation; fix belongs on the roadmap but isn't blocking |
| medium | Partially met; patch warranted |
| low | Mostly met; minor inconsistency |
| info | Observation only (often a justified ADR or a metric worth tracking) |

## Adversarial posture

| Value | Meaning |
|-------|---------|
| violated | Evidence clearly cuts against the principle |
| partial | Principle met in some places, violated in others |
| justified | Appears to violate, but a referenced ADR/memo/commit/PR justifies it |

## Recommended action

| Action | Meaning |
|--------|---------|
| refactor | Code change needed |
| document | Comment or ADR addition |
| suppress | Add `# noqa` / `# nosonar` / Sonar exclusion (rationale required) |
| accept | Known debt; tracking issue created |
| escalate | Needs user decision |

## Synthesis pass

A single agent runs after all 5 cluster agents complete:

1. Schema-validate every cluster output (all required fields present, severities in enum, code_refs resolve).
2. **Re-verify** every `severity: critical` finding via direct file inspection.
3. **Re-verify** every `severity: high` finding unless the cluster agent provided strong evidence (numeric metric + cited tool output).
4. Dedupe across clusters by `file + line_range`.
5. Cross-reference all `drift_signals` against `git log` to confirm PR/issue refs are real (no hallucinated SHAs).
6. Cross-reference against the SonarCloud baseline so we don't re-flag what PRs #142–#149 already addressed.
7. Re-run complexity checks (lizard/radon) on every cluster A flagged file to confirm metric numbers.
8. Generate two **coverage-gap** sections:
   - *Principles with zero findings* — possible audit blind spots (call them out, don't fix)
   - *Code with TODO/FIXME/XXX* but no finding card — places the audit might have missed
9. Write ranked summary table (severity desc, then cluster, then file).
10. Output:
    - `catalog/reviews/audit-harness-self-2026-08-09.md` (report)
    - `catalog/reviews/audit-harness-self-2026-08-09.json` (machine-readable for tooling)

## Auto-issue creation rules

HIGH and CRITICAL findings auto-create GitHub issues:

- Title: `[audit:spec-1:<cluster>] <one-line principle violation>`
- Body: YAML finding card + link to the report section
- Labels: `audit`, `harness-self-audit`, `principles-audit`, `P0` (critical) or `P1` (high), plus `audit-2026-08-09` (cross-audit searchability)
- **Cap**: 5 issues per cluster → remainder bundled into one umbrella issue per cluster (`[audit:spec-1:<cluster>] N additional findings from harness self-audit`)
- All issues filed in one batch via **GitHub MCP** (not `gh` CLI — per `issue_drafter` base-ref hardening in Issue #30 plan)
- Repo: `Heretek-AI/heretek-claude-harness` *(to be confirmed before issue creation runs)*

## Verification standard

- Schema validation script committed alongside findings: `scripts/audit_validate.py` (pytest-able)
- Synthesis re-verification is mandatory before any issue creation (the synthesis gate IS the rigor)
- Memory drift refresh applied before citing any auto-recalled facts (per `memory-drift-refresh-protocol`)
- All cited commit SHAs verified via `git log` in synthesis, not in cluster agents
- Pre-commit CLI detection in tests uses `python3 -m pre_commit --version`, not `import pre_commit` (per established convention)

## Risks / failure modes

| Risk | Mitigation |
|------|-----------|
| Cluster overlap (complexity shows in A and B) | Synthesis dedupes by `file + line_range` |
| Adversarial over-flagging | Synthesis re-verification + sonar / git-log cross-check |
| Auto-issue flood | 5-per-cluster cap + umbrella issue |
| Hallucinated metrics | Synthesis re-runs lizard/radon on flagged files; drops finding if metric doesn't reproduce |
| Catalog drift mid-audit | Audit snapshots commit SHA; findings reference SHA, not just paths |
| False-positive HIGH/CRITICAL becoming committed issues | Synthesis gate is mandatory; no issue creation without it |
| Memory drift (recalled facts stale) | Memory drift refresh protocol applied before citing facts |
| gh CLI vs GitHub MCP inconsistency | All API calls in plan use GitHub MCP exclusively |

## Out of scope for this spec

- Spec 2 (plugins marketplace audit) — separate brainstorm
- Spec 3 (enforcement surface audit) — separate brainstorm
- Closing existing already-shipped-but-open issues (audit-only; that's the 2026-08-08 audit's job)
- Code changes to fix findings (the audit produces findings + issues; fixing is downstream work)

## Files this spec will produce

- `docs/superpowers/specs/2026-08-09-heretek-harness-self-audit-design.md` (this file)
- `catalog/reviews/audit-harness-self-2026-08-09.md` (audit report)
- `catalog/reviews/audit-harness-self-2026-08-09.json` (machine-readable findings)
- `scripts/audit_validate.py` (schema validation script for findings)
- `scripts/audit_harness_self.py` (driver script that orchestrates the 5 cluster agents + synthesis)
- N GitHub issues (HIGH/CRITICAL only, capped at 5/cluster + 1 umbrella/cluster)
- `docs/superpowers/plans/2026-08-09-heretek-harness-self-audit-plan.md` (implementation plan, produced by writing-plans)
