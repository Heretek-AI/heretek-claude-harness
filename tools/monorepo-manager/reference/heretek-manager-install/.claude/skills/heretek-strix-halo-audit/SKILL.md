---
name: heretek-strix-halo-audit
description: Audit host hardware and recommend a backend.
allowed-tools: ['Bash']

---

# heretek-strix-halo-audit

Audit host hardware and recommend a backend.

## When to use

Use this skill when the harness detects a relevant pattern.

## Procedure

1. shell out to nvidia-smi/rocminfo/vulkaninfo
2. parse output
3. recommend backend
