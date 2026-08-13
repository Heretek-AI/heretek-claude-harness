---
name: python-check
description: Run ruff check, ruff format --check, and basedpyright on Python codebases to enforce quality and type safety.
---

# python-check

Execute Python static analysis and strict type checking gates.

## Step 1: Run Ruff Linter & Formatter

```bash
ruff check .
ruff format --check .
```

## Step 2: Run Basedpyright Strict Type Checker

```bash
basedpyright .
```

## Step 3: Interpret Diagnostics

Format output into line-level diagnostic findings with actionable code fix playbooks.
