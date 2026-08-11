---
name: sonarcloud-suppression
description: Use when suppressing or working around SonarCloud Python findings. Full reference is at docs/SONAR-SUPPRESSION.md.
---

# SonarCloud Suppression

Canonical reference: **`docs/SONAR-SUPPRESSION.md`** (read this for the
detailed decision tree, common mistakes, and real-world impact examples).

This skill is the entry point. The skill file is a pointer; the doc has
the patterns.

## TL;DR

- `# nosonar` MUST be on the same line as the violation (within textRange).
- For S8707/S2083/S8705 on CLI args: prefer `Path.resolve()` (sanitizes
  Sonar's data-flow tracking) over `# nosonar`.
- For multi-finding exclusion: `sonar-project.properties` multicriteria
  syntax (`sonar.issue.ignore.multicriteria.N.ruleKey + .resourceKey`).
- Don't bother with `# nosonar S2083` — Sonar ignores the rule ID suffix.

## When NOT to suppress

- True bug → fix it (extract helper for S3776, restructure for S3516).
- False positive on internal CLI → `Path.resolve()` instead of comment.

See `docs/SONAR-SUPPRESSION.md` for the full decision tree and the
"Common Mistakes" table.
