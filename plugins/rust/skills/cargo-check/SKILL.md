---
name: cargo-check
description: Run `cargo check` on the current Rust crate and surface errors. Use after modifying Rust source.
---

Run `cargo check --message-format=short --color=never` from the crate root. Surface the first 50 lines of output. If errors are present, list each with file:line. Do not run tests; that's a separate workflow.

For a fast pass on changed files only, use `cargo check --message-format=short` after editing `.rs` files.
