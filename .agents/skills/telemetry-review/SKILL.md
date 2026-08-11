---
name: telemetry-review
description: Layer 3 human-in-loop review of weekly harness scorecard. Walks a maintainer through artifact bundles, marks regressions, opens issues.
---

# Telemetry Review Skill (Layer 3)

Interactive human review for the harness eval scorecard.

## When to invoke

- After `/heretek:telemetry-review` is called
- When a maintainer wants to manually grade a specific artifact bundle

## Inputs

- Week (e.g., `2026-W32`)
- Optional: bundle name (default: all bundles for the week)

## Process

1. Fetch `scorecard-<week>.md` from the latest `harness-eval` workflow run.
2. Display the scorecard to the maintainer.
3. For each `fail` verdict, show the artifact bundle (patch.diff + result.json).
4. Maintainer marks each as: `confirmed-regression`, `false-positive`, or `needs-investigation`.
5. Open issues for `confirmed-regression` items with label `harness-regression`.
6. Update the scorecard with maintainer annotations and write `human-review-<week>.md`.

## Example

```
/heretek:telemetry-review 2026-W32
```
