# Enforcement Surface Audit (Spec 3) Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add enforcement-specific cluster definitions to the existing audit toolkit so the hostile audit can verify that `scripts/scanners/`, `scripts/validate.py`, `.github/workflows/`, and `plugins/hooks/` enforcement behavior actually catch what they claim.

**Reuse:** Same `scripts/audit/` toolkit as Spec 1 and Spec 2. This plan adds enforcement-specific cluster prompts and a driver subcommand.

**Tech Stack:** Python 3.10+, same as Spec 1/2. No new deps.

## Global Constraints

- **Spec under implementation:** `docs/superpowers/specs/2026-08-09-heretek-enforcement-audit-design.md`
- **In scope:** `scripts/scanners/`, `scripts/validate.py`, `scripts/generate_marketplace.py`, `scripts/refresh_pins.py`, `.github/workflows/`, `plugins/hooks/` enforcement behavior
- **Out of scope:** Plugin code quality (Spec 2), harness code quality (Spec 1 — except as cross-reference for meta-audit)
- **Per-finding schema:** Same `tests/schemas/audit_finding.schema.json`
- **Severity → auto-issue:** critical → P0, high → P1
- **Auto-issue cap:** 5 per cluster + 1 umbrella per cluster
- **Labels:** `audit`, `enforcement-audit`, `principles-audit`, `P0`/`P1`, `audit-2026-08-09`
- **GitHub access:** MCP only

---

## Task 1: Add enforcement cluster definitions to prompts module

**What:** Add 5 new cluster definitions for the enforcement audit lanes.

**Files:**
- `scripts/audit/prompts.py` — add `_ENFORCEMENT_CLUSTERS` dict + `render_enforcement_prompt(letter, repo_root, commit_sha)`
- `tests/test_audit_prompts.py` — add tests

**Cluster definitions:**

| Letter | Name | Key questions |
|--------|------|---------------|
| A | Scanner coverage & false negatives | Does every pattern in `forbidden_patterns.yaml` get caught? Are code-executing components (hooks, bin/, MCP servers, pre-commit) scanned? Gap analysis. |
| B | CI gate completeness | Does every PR trigger validation? Bypass paths? Fail-loud on violation? Missing gates for new categories? |
| C | Vetting bar enforcement | Does `validate.py` enforce D7 on catalog entries? Does `refresh_pins.py` catch stale stars/license/last_commit/CVEs? Items that slip through? |
| D | Hook enforcement behavior | Do hooks block the agent loop? Fast-gate < 100ms? Slow analyzers callable? Git hooks wired correctly? |
| E | Audit-the-auditors meta | Are enforcement scripts tested? Scanner test edge cases? TODO/FIXME in enforcement code? Findings from Spec 1 code-quality audit of these files? |

**Acceptance criteria:**
- [ ] 5 enforcement cluster definitions exist with enforcement-specific principles and evidence strategies
- [ ] Each template scopes the agent to the enforcement surface directories
- [ ] `render_enforcement_prompt()` returns a usable prompt
- [ ] `python -m pytest tests/test_audit_prompts.py` passes
- [ ] CLI: `python scripts/audit/prompts.py A --repo-root . --commit-sha SHA --spec enforcement` works

---

## Task 2: Add enforcement-specific issue labels

**What:** Extend `issues.py` to support `spec="enforcement"` label prefix.

**Files:**
- `scripts/audit/issues.py` — extend `spec_label` parameter
- `tests/test_audit_issues.py` — add tests for spec-3 labels

**Acceptance criteria:**
- [ ] `build_issue_payloads(findings, spec="enforcement")` produces labels with `enforcement-audit`
- [ ] Umbrella titles read `[audit:spec-3:<cluster>]`
- [ ] `python -m pytest tests/test_audit_issues.py` passes

---

## Task 3: Add enforcement synthesis output naming

**What:** Support `report_prefix="audit-enforcement"` in `synthesize()`.

**Files:**
- `scripts/audit/synthesis.py` — already supports `report_prefix` from Spec 2 Task 3
- `tests/test_audit_synthesis.py` — add test for enforcement prefix

**Acceptance criteria:**
- [ ] `synthesize(..., report_prefix="audit-enforcement")` writes `audit-enforcement-YYYY-MM-DD.{md,json}`
- [ ] `python -m pytest tests/test_audit_synthesis.py` passes

---

## Task 4: Add enforcement audit CLI subcommand

**What:** Add `enforcement` subcommand to `harness_self.py`.

**Files:**
- `scripts/audit/harness_self.py` — add `enforcement` subcommand
- `tests/test_audit_harness_self.py` — add tests

**Acceptance criteria:**
- [ ] `python scripts/audit/harness_self.py enforcement emit-prompts` generates 5 enforcement-scoped prompts
- [ ] `python scripts/audit/harness_self.py enforcement synthesize` produces `audit-enforcement-YYYY-MM-DD.*`
- [ ] `python scripts/audit/harness_self.py enforcement build-issues` produces spec-3 labeled payloads
- [ ] `python -m pytest tests/test_audit_harness_self.py` passes

---

## Task 5: End-to-end smoke test

**What:** Add fixture cluster results and smoke test for the enforcement audit.

**Files:**
- `tests/fixtures/audit/cluster_results/` — add enforcement-scoped fixtures
- `tests/test_audit_e2e.py` — add enforcement smoke test

**Acceptance criteria:**
- [ ] Fixtures match the enforcement finding schema
- [ ] Smoke test: load → synthesize → verify output → build-issues → verify spec-3 labels
- [ ] `python -m pytest tests/test_audit_e2e.py` passes
- [ ] `python -m pytest` full suite passes

---

## Exit criteria

When all 5 tasks are complete:

1. Enforcement cluster prompts are usable — `emit-prompts` generates 5 enforcement-scoped prompts
2. Synthesis produces correctly-named reports for the enforcement audit
3. Issue payloads carry spec-3 labels and umbrella titles
4. CLI subcommand `enforcement` wires everything together
5. End-to-end smoke test passes

Operator-driven execution follows the same workflow as Spec 1/2:
1. `enforcement emit-prompts` → paste into Explore-agents
2. Collect YAML → `enforcement synthesize` → review report
3. `enforcement build-issues` → operator files issues via GitHub MCP

---

## Three-spec summary

After all three specs are implemented, the CLI supports:

```bash
# Spec 1: Harness self-audit (shipped)
python scripts/audit/harness_self.py run-all --repo-root . --commit-sha SHA

# Spec 2: Plugins marketplace audit
python scripts/audit/harness_self.py plugins-marketplace emit-prompts ...
python scripts/audit/harness_self.py plugins-marketplace synthesize ...
python scripts/audit/harness_self.py plugins-marketplace build-issues ...

# Spec 3: Enforcement surface audit
python scripts/audit/harness_self.py enforcement emit-prompts ...
python scripts/audit/harness_self.py enforcement synthesize ...
python scripts/audit/harness_self.py enforcement build-issues ...
```

All three share `validate.py`, `findings.py`, `synthesis.py`, `issues.py` — only the cluster definitions and output naming differ. Minimal code, maximum coverage.
