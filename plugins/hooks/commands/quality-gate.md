---
description: Run slow quality analyzers (clippy, megalinter, tdd-guard, jscpd, sonarqube) on demand.
---

Run Layer 2 slow analyzers. By default runs on the whole repo; pass `diff` to limit to staged/unstaged changes, or a path to limit to a specific directory.

Available tools (only the installed ones run):
- `cargo clippy` — Rust lints
- `megalinter` — aggregator for many linters
- `tdd-guard` — TDD enforcement
- `jscpd` — copy-paste detector
- `sonar-scanner` — SonarQube static analysis (requires `sonar-project.properties`)

The runner fails open on missing tools (skips them). Exit code is 0 if all available tools pass, 2 if any fail.

Usage from Claude Code: `/quality-gate:run` or `/quality-gate:run diff` or `/quality-gate:run src/foo`.

Claude Code invokes this command frontmatter; the actual work is in `quality_gate.py`.
