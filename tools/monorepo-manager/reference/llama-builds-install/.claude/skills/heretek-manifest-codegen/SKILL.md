---
name: heretek-manifest-codegen
description: Generate manifest.json from targets/*/build.sh.
allowed-tools: ['Bash', 'Read']

---

# heretek-manifest-codegen

Generate manifest.json from targets/*/build.sh.

## When to use

Use this skill when the harness detects a relevant pattern.

## Procedure

1. read targets/*/build.sh
2. emit manifest.json
3. validate against schemas/manifest.schema.json
