---
name: heretek-manifest-fetch
description: Fetch the llama-builds manifest with retries.
allowed-tools: ['Bash']

---

# heretek-manifest-fetch

Fetch the llama-builds manifest with retries.

## When to use

Use this skill when the harness detects a relevant pattern.

## Procedure

1. fetch https://heretek-ai.github.io/llama-builds/manifest.json
2. retry up to 3 times
3. verify SHA-256 against sha256sum.txt
