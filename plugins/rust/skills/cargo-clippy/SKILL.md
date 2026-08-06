---
name: cargo-clippy
description: Run `cargo clippy` on a Rust project and report lints as structured findings (file, line, severity, rule).
---

# cargo-clippy

Invoke Rust's official linter via the `cargo-clippy` skill. Mirrors the maintainer workflow of running `cargo clippy --all-targets -- -D warnings` and triaging each lint.

## When to use

Use this skill when the user asks to lint, review, or audit a Rust project — or when an automated review wants a code-quality signal before merging.

## Steps

### Step 1: Run clippy

```bash
cargo clippy --all-targets --message-format=json | tee /tmp/clippy.json
```

If `cargo` isn't installed, fail fast with the install instructions (rustup).

### Step 2: Parse findings

Read `/tmp/clippy.json` line-by-line. Each line is a JSON message. Filter for `reason: "compiler-message"` and `severity: "warning"` or `"error"`.

### Step 3: Group by file

For each finding, record:
- `file` (relative path)
- `line`
- `column`
- `severity` (warning | error)
- `code` (the lint rule, e.g. `clippy::needless_borrow`)

Group by file; emit one block per file with all lines in order.

### Step 4: Surface

Print a summary:
- Total findings
- Findings per file
- Top 5 lint rules by frequency

If any `severity: "error"` exists, fail the skill with exit 1.

## Acceptance criteria

- Runs `cargo clippy --all-targets` (not just default target)
- Parses JSON output (not human-readable compiler output)
- Groups by file for readability
- Exits non-zero if any error-severity lint exists