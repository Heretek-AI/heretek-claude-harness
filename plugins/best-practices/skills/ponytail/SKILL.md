---
name: ponytail
description: Apply the 7-Rung Lazy Ladder heuristic to prevent code over-engineering and bloated diffs.
---

# ponytail

Apply senior engineering discipline to minimize unnecessary code generation.

## The 7-Rung Lazy Ladder

Before writing any new function, class, or dependency, evaluate the request against this ladder:

1. **Rung 1 (YAGNI)**: Does this code need to exist at all? (If not, drop it).
2. **Rung 2 (Reuse)**: Is this functionality already in the codebase? (If so, call existing function).
3. **Rung 3 (Stdlib)**: Does the language standard library do this? (If so, use stdlib).
4. **Rung 4 (Native Platform)**: Does a native platform/browser feature cover it? (e.g. `<input type="date">` instead of custom JS picker).
5. **Rung 5 (Installed Dependency)**: Does an already-installed dependency solve it cleanly?
6. **Rung 6 (One Line)**: Can it be expressed cleanly in one line?
7. **Rung 7 (Minimum Working Code)**: Write the absolute minimum lines required to pass verification.

## Root-Cause Bug Fixing Rule

Before editing a function to fix a bug:
- Find and inspect ALL callers across the codebase.
- Trace the root cause upstream rather than wrapping downstream calls in silent `try/except` or `if (val != null)` patches.
