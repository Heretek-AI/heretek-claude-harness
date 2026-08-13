---
name: heretek-upstream-sync
description: Test a new llama.cpp upstream SHA before promoting to a release.
allowed-tools: ['Bash']

---

# heretek-upstream-sync

Test a new llama.cpp upstream SHA before promoting to a release.

## When to use

Use this skill when the harness detects a relevant pattern.

## Procedure

1. checkout upstream SHA
2. run audit_matrix.py
3. report PR-ready status
