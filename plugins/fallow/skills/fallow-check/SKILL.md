---
name: fallow-check
description: Detect dead code, unreferenced exports, unused dependencies, and calculate token blast radius using Fallow.
---

# fallow-check

Invoke `fallow` static analysis engine inspired by fallow-rs/fallow to audit codebases for dead code and dependency bloat.

## When to use

Use this skill when auditing repositories for unreferenced exports, dead modules, unused packages, and token blast radius before refactoring.

## Steps

### Step 1: Run Fallow CLI

```bash
fallow check --json > /tmp/fallow.json
```

If `fallow` binary is not installed, fall back to checking `Cargo.lock` or `package.json` unreferenced entries.

### Step 2: Parse Cleanup Candidates & Blast Radius

Parse `/tmp/fallow.json` for:
- `unused_exports`: Functions/classes exported but never imported.
- `dead_files`: Source files never imported by any entry point.
- `unused_dependencies`: Package manifests declaring unused dependencies.
- `token_blast_radius`: Estimated impact if target symbols are modified.

### Step 3: Summarize Findings

Print structured report grouped by file and risk level.
