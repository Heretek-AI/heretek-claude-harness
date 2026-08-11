---
name: sonarcloud-batch-remediation
description: Use when remediating a batch of 10+ SonarCloud findings on this repo. Full reference is at docs/SONAR-BATCH-REMEDIATION.md.
---

# SonarCloud Batch Remediation

Canonical reference: **`docs/SONAR-BATCH-REMEDIATION.md`** (read this for
the 7-PR slice template, severity-first rationale, and workflow).

This skill is the entry point. The skill file is the pointer; the doc has
the patterns.

## TL;DR

- Severity-first slicing (BLOCKER → CRITICAL → MAJOR → MINOR), not
  file-first. Reviewers can match their expertise to the slice.
- Each PR is <500 LOC diff (reviewable in one sitting).
- Sequential PRs (not parallel) — cross-file issues + pattern application +
  CI feedback loop require order.
- Check the Quality Gate status between PRs:
  `curl -sS -L "https://sonarcloud.io/api/qualitygates/project_status?projectKey=Heretek-AI_heretek-claude-harness&pullRequest=<N>"`
- All BLOCKER + CRITICAL resolve by PR 2; code smells and shell scripts
  land last.

## When to use

- 10+ open SonarCloud findings on this repo.
- You want to close them efficiently without creating a 1000+ LOC PR.

## When to skip

- 1-3 findings → use [sonarcloud-suppression](.) and ship a single PR.

See `docs/SONAR-BATCH-REMEDIATION.md` for the full template, the
severity-first rationale, and the parallel-vs-sequential trade-offs.
