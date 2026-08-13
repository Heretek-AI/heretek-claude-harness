---
name: agentic-readiness
description: Evaluate codebase maintainability and readiness for AI coding agents using the Agentic Readiness Scorecard framework.
---

# agentic-readiness

Evaluate codebase readiness for AI coding agents (inspired by SonarQube's Agentic Readiness Assessment).

## The 4 Agentic Readiness Pillars

Audit the repository across these 4 pillars:

1. **Pillar 1: Deterministic Quality Gates (0-25 pts)**
   - Are linters (`ruff`, `biome`, `cargo clippy`) configured with auto-fix enabled?
   - Is strict type checking (`pyright`, `tsc --noImplicitAny`, `gopls`) active?
2. **Pillar 2: Test Suite Signals (0-25 pts)**
   - Is unit test suite execution fast (<30 seconds)?
   - Are error tracebacks precise and actionable for automated fix loops?
3. **Pillar 3: Context Hygiene (0-25 pts)**
   - Are module boundaries clear with low coupling?
   - Is there a concise `CLAUDE.md` or `AGENTS.md` specifying build/test/lint commands?
4. **Pillar 4: Spec & Plan Discipline (0-25 pts)**
   - Are specifications and task lists maintained during non-trivial edits?

## Score & Output

Report an overall score out of 100 with domain recommendations.
