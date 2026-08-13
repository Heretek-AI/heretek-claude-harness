# Contributing to heretek-manager

This project follows the Heretek harness contract. See
[`docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md`](docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md)
for the umbrella spec.

## Tracking

Long-lived design debates, decision logs, and progress notes live as
[GitHub Issues](../../issues) and [Project](../../projects) items — not
as separate Markdown files.

`docs/superpowers/specs/*.md` is the engineering source of truth only
for *in-flight* designs (spec → plan → implementation). Once an
implementation lands, the design lives in the issue/PR conversation and
in the code.

Exceptions (release notes, ADRs needing cross-repo visibility) are
explicitly small and recorded in the same Project.

## Required CI checks

The four required checks on `main` are:

- `super-linter`
- `pre-commit`
- `sonarcloud`
- `gitleaks`

No merge without all four green.
