---
date: 2026-08-08
topic: hook-orchestrator-decision
status: accepted
parent: docs/superpowers/specs/2026-08-05-v2-code-quality-issue-set-design.md
related_issues: [20, 17, 19]
---

# Hook Orchestrator Decision

> Date: 2026-08-08. ADR accepts pre-commit as canonical Layer 3 orchestrator. Closes #20. Unblocks #17 (coverage-pack) and #19 (quality-pack).

## Context

The `hooks` plugin (Layer 1: PreToolUse + Layer 2: lint wrappers) keeps ownership per D15. The Layer 3 (git-hooks side) has three viable OSS orchestrators surfaced in deep-research for issue #20:

| Orchestrator | License | Notes |
|---|---|---|
| pre-commit | MIT | De-facto standard, 15.5k stars verified 2026-08-05 |
| lefthook | MIT | Single Go binary, no Python dep |
| megalinter | AGPL-3.0 | Easiest onboarding, AGPL is license risk |

The new `quality-pack` (#19) and `coverage-pack` (#17) plugins both need Layer 3 hooks and inherit the same orchestrator choice. Fragmentation across orchestrators would multiply maintenance burden.

## Decision

Adopt **pre-commit** as the canonical Layer 3 orchestrator for all heretek plugins that ship git hooks. Document lefthook as opt-in alternative for Python-free environments. Document megalinter as opt-in only (AGPL license risk; D7 fail for first-party adoption).

## Alternatives Considered

- **lefthook** — single Go binary, faster cold-start than pre-commit, no Python dependency. Trade-off: smaller ecosystem, fewer pre-built hooks. Status: documented opt-in for users who can't or won't install Python.
- **megalinter** — easiest onboarding via Docker wrapper. Trade-off: AGPL-3.0 license (D7 fail for first-party). Status: opt-in only; never the default.
- **No orchestrator (custom shell glue)** — current state pre-#20. Trade-off: every plugin reinvents Layer 3 plumbing; review burden scales with plugin count. Status: rejected.

## Consequences

- `hooks` plugin's Layer 3 README links to this ADR (one-line addition under the relevant heading, if such a heading exists; otherwise skip).
- `quality-pack` (#19) and `coverage-pack` (#17) inherit pre-commit. They do NOT need their own orchestrator decision.
- Layer 1 (PreToolUse) and Layer 2 (lint wrappers) ownership of the `hooks` plugin is unchanged per D15. pre-commit operates purely at the git-hooks layer (Layer 3).
- D11 (no version field on first-party plugins): unaffected — pre-commit is a dependency, not a versioned plugin.
- D7 vetting bar: unaffected — pre-commit is MIT, primary-source verified, 15.5k stars as of 2026-08-05.

## Cross-references

- Issue #20 (closes) — design: choose canonical hook orchestrator (pre-commit vs lefthook vs megalinter)
- Issue #17 (unblocked) — v2: coverage-pack plugin (enforceable coverage thresholds via git hooks)
- Issue #19 (unblocked) — v2: quality-pack plugin (SAST + SCA + orchestrator consolidation)
- Spec: `docs/superpowers/specs/2026-08-05-v2-code-quality-issue-set-design.md` §3 Issue D
- Precedent ADR: `docs/superpowers/specs/2026-08-05-marketplace-versioning-decision.md` (D11 SHA-ride)
- PLAN.md §6 (hooks plugin layering)
