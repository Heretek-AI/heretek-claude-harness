---
name: headroom
description: Dynamic context compression and log output filtering to prevent model context exhaustion and reduce cost.
---

# headroom

Optimize model context windows during large test, build, or search runs.

## Guidelines

1. **Log Truncation**: When running tests or linters, extract only relevant error tracebacks and failure lines. Do not inject thousands of lines of passing test output into context.
2. **Diff Compression**: For large refactors, summarize modified file lists before outputting full unified diffs.
3. **File Offset Reading**: Use line offset slice parameters (`StartLine`/`EndLine`) when viewing large files instead of loading 5,000 lines into context at once.
