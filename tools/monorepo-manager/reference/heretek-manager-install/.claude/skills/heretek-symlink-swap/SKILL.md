---
name: heretek-symlink-swap
description: Apply the atomic symlink swap recipe.
allowed-tools: ['Bash', 'Edit']

---

# heretek-symlink-swap

Apply the atomic symlink swap recipe.

## When to use

Use this skill when the harness detects a relevant pattern.

## Procedure

1. write to a temp symlink
2. rename atomically
3. verify symlink target
