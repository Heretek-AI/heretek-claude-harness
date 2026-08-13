---
name: rust-check
description: Run cargo check, cargo clippy, and cargo fmt on Rust crates to enforce memory safety and code quality.
---

# rust-check

Execute Rust compilation and linter quality gates.

## Step 1: Run Cargo Format Check

```bash
cargo fmt --check
```

## Step 2: Run Cargo Clippy Linter

```bash
cargo clippy --all-targets --all-features -- -D warnings
```

## Step 3: Interpret Diagnostics

Format compiler errors and clippy warnings into file:line diagnostic findings.
