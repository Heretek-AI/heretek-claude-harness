---
description: Thorough output. Include rationale, edge cases, and tradeoffs.
---

When this style is active:
- Lead with the answer
- Follow with the reasoning
- List edge cases explicitly
- Note tradeoffs when relevant
- Cite file:line for code references

Example:
- User: "What's the bug?"
- Detailed response: "Line 42 calls `foo()` without checking `x` for null. The bug: when `x` is null, `foo()` throws NPE. Fix: add null check at line 41 before the call."
