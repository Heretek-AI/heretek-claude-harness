---
name: elixir-check
description: Run mix format --check-formatted and mix credo on Elixir projects to enforce code quality.
---

# elixir-check

Execute Elixir compilation, formatting, and linter quality gates.

## Step 1: Run Formatting Check

```bash
mix format --check-formatted
```

## Step 2: Run Mix Credo Linter

```bash
mix credo --strict
```

## Step 3: Interpret Diagnostics

Format Credo issues and compiler warnings into file:line diagnostic findings.
