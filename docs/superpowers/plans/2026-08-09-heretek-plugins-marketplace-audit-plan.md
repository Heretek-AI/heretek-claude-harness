# First-Party Plugins Marketplace Audit (Spec 2) Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add plugin-specific cluster definitions to the existing audit toolkit so the hostile principles audit can be run against all 10 first-party plugins (`plugins/*/` excluding `plugins/hooks/`), the catalog vetting records, and the plugin manifest consistency.

**Reuse:** The entire `scripts/audit/` toolkit from Spec 1 is reused unchanged. This plan only adds new cluster prompt templates and an entry-point driver that targets the plugins scope.

**Tech Stack:** Python 3.10+, same as Spec 1. No new deps.

## Global Constraints

- **Spec under implementation:** `docs/superpowers/specs/2026-08-09-heretek-plugins-marketplace-audit-design.md`
- **In scope:** `plugins/{agents,js-ts,lsp-pack,mcp-pack,output-styles,python,rust,security,skills-pack,web-frontend}/`, `catalog/catalog.yaml`, `catalog/reviews/*.md`, `.claude-plugin/plugin.json` per plugin
- **Out of scope:** `plugins/hooks/` (Spec 1), `.claude-plugin/marketplace.json` (generated), enforcement behavior (Spec 3)
- **Per-finding schema:** Same `tests/schemas/audit_finding.schema.json` from Spec 1
- **Severity → auto-issue:** critical → P0, high → P1
- **Auto-issue cap:** 5 per cluster + 1 umbrella per cluster
- **Labels:** `audit`, `plugins-marketplace-audit`, `principles-audit`, `P0`/`P1`, `audit-2026-08-09`
- **GitHub access:** MCP only
- **Audit snapshot:** commit SHA captured at audit start

---

## Task 1: Add plugin cluster definitions to prompts module

**What:** Add 5 new `ClusterDef` entries (letters F-J or reuse A-E with `spec=2` namespace) for the plugins marketplace audit lanes.

**Files:**
- `scripts/audit/prompts.py` — add `_PLUGIN_CLUSTERS` dict + `render_plugin_prompt(letter, repo_root, commit_sha)`
- `tests/test_audit_prompts.py` — add tests for the new cluster definitions

**Acceptance criteria:**
- [ ] 5 new cluster definitions exist: Plugin code quality (A), Plugin architecture (B), D7 vetting compliance (C), Catalog & manifest consistency (D), Plugin docs & onboarding (E)
- [ ] Each template embeds the per-finding schema (same as Spec 1)
- [ ] Each template scopes the agent to `plugins/*/` (excluding `plugins/hooks/`) + `catalog/`
- [ ] `render_plugin_prompt()` works and returns a usable prompt
- [ ] `python -m pytest tests/test_audit_prompts.py` passes (existing + new tests)
- [ ] CLI: `python scripts/audit/prompts.py A --repo-root . --commit-sha SHA --spec plugin` prints the plugin-scoped prompt

---

## Task 2: Add plugin-specific issue labels

**What:** Extend `issues.py` to support a `spec` parameter that changes the label prefix and umbrella title.

**Files:**
- `scripts/audit/issues.py` — add `spec_label` parameter to `build_issue_payloads()`
- `tests/test_audit_issues.py` — add tests for spec-2 labels and umbrella titles

**Acceptance criteria:**
- [ ] `build_issue_payloads(findings, spec="plugin")` produces labels with `plugins-marketplace-audit` instead of `harness-self-audit`
- [ ] Umbrella titles read `[audit:spec-2:<cluster>]` instead of `[audit:spec-1:<cluster>]`
- [ ] `python -m pytest tests/test_audit_issues.py` passes

---

## Task 3: Add plugin-scoped synthesis output naming

**What:** Extend `synthesis.py` to accept a `report_prefix` parameter so Spec 2 reports are named `audit-plugins-marketplace-YYYY-MM-DD.*` instead of `audit-harness-self-YYYY-MM-DD.*`.

**Files:**
- `scripts/audit/synthesis.py` — add `report_prefix` parameter to `synthesize()`
- `tests/test_audit_synthesis.py` — add test for custom prefix

**Acceptance criteria:**
- [ ] `synthesize(..., report_prefix="audit-plugins-marketplace")` writes `audit-plugins-marketplace-YYYY-MM-DD.{md,json}`
- [ ] Default behavior (no prefix) unchanged — backward compatible
- [ ] `python -m pytest tests/test_audit_synthesis.py` passes

---

## Task 4: Add plugin audit CLI subcommand

**What:** Add a `plugins-marketplace` subcommand to `harness_self.py` that wires the plugin cluster definitions into the existing emit-prompts / synthesize / build-issues pipeline.

**Files:**
- `scripts/audit/harness_self.py` — add `plugins-marketplace` subcommand
- `tests/test_audit_harness_self.py` — add tests for the new subcommand

**Acceptance criteria:**
- [ ] `python scripts/audit/harness_self.py plugins-marketplace emit-prompts --repo-root . --commit-sha SHA --out-dir /tmp/` generates 5 prompt files (A-E) scoped to plugins
- [ ] `python scripts/audit/harness_self.py plugins-marketplace synthesize --cluster-results DIR --output-dir catalog/reviews --commit-sha SHA` produces `audit-plugins-marketplace-YYYY-MM-DD.{md,json}`
- [ ] `python scripts/audit/harness_self.py plugins-marketplace build-issues --findings-json FILE --output /tmp/issues.json` produces payloads with spec-2 labels
- [ ] `python -m pytest tests/test_audit_harness_self.py` passes

---

## Task 5: End-to-end smoke test

**What:** Add fixture cluster results for the plugins marketplace audit and a smoke test that exercises the full pipeline.

**Files:**
- `tests/fixtures/audit/cluster_results/` — add plugin-scoped fixture files
- `tests/test_audit_e2e.py` — add smoke test for spec-2 pipeline

**Acceptance criteria:**
- [ ] Fixture files match the plugin finding schema
- [ ] Smoke test: load fixtures → synthesize → verify output files exist → build-issues → verify payloads have spec-2 labels
- [ ] `python -m pytest tests/test_audit_e2e.py` passes
- [ ] `python -m pytest` full suite passes

---

## Exit criteria

When all 5 tasks are complete:

1. Plugin cluster prompts are usable — `emit-prompts` generates 5 plugin-scoped prompts
2. Synthesis produces correctly-named reports for the plugins marketplace audit
3. Issue payloads carry spec-2 labels and umbrella titles
4. CLI subcommand `plugins-marketplace` wires everything together
5. End-to-end smoke test passes

The actual hostile audit execution follows the same operator-driven workflow as Spec 1:
1. `emit-prompts` → paste each prompt into a fresh Explore-agent
2. Collect YAML outputs → `synthesize` → review report
3. `build-issues` → operator runs `mcp__github__github-issue_write` to file issues
