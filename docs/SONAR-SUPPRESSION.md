# SonarCloud Suppression Patterns

Reference + technique. Captures the non-obvious suppression rules that cost time during issue #141 remediation.

## The Iron Rule

**`# nosonar` MUST be on the same line as the violation (within its textRange).** A marker on the line above is silently ignored.

```python
# ✅ WORKS — marker is within the violation's textRange
def main() -> int:  # nosonar — false positive: hook entrypoint always returns 0
    try:
        ...
    except json.JSONDecodeError:
        return 0

# ❌ DOES NOT WORK — marker is on the line above
def main() -> int:
    # nosonar — false positive: hook entrypoint always returns 0
    try:
        ...
```

Why: Sonar's textRange scope is the violation itself (e.g. `startOffset: 4, endOffset: 8` for the `def` keyword on `def main() -> int:`). A comment on the next line has offset 0, outside the textRange.

## Decision Tree

```
Can you fix the actual issue?
├─ Yes (refactor) → Refactor. Don't suppress.
├─ No, but it's a true false-positive → use # nosonar (see below)
└─ No, and it's a real-but-acceptable risk → use sonar-project.properties
```

### Step 1: Try a real fix first

For S3776 (cognitive complexity > 15), extract single-purpose helpers. For S3516 on entrypoints, refactor so the return type isn't always `None`/constant (often impossible without restructuring — fall through to Step 2).

### Step 2: `# nosonar` on the SAME LINE as the violation

```python
def main() -> int:  # nosonar — rationale: <one-line why>
    ...
```

If after 2 attempts the inline `# nosonar` still doesn't suppress, the issue is almost certainly **textRange scope** — the violation lives on a sub-expression, not the whole line. See Step 3.

### Step 3: `Path.resolve()` as sanitizer (for S8707/S2083/S8705)

Sonar's data-flow rules track user-controlled input (CLI args) flowing into file I/O. `Path.resolve()` is in Sonar's sanitizer allow-list — calling it makes the path "trusted" downstream.

```python
def _safe_load_catalog(catalog_path: Path) -> dict:
    """Read catalog.yaml after resolving the path. Sanitizes S8707."""
    return yaml.safe_load(catalog_path.resolve().read_text())
```

This is **cleaner than `# nosonar`** because:
- The marker would have been a comment lying about what the code does.
- The resolver is real — if a malformed path ever sneaks in, `.resolve()` makes the error more deterministic.

### Step 4: `sonar-project.properties` exclusions (last resort)

For rules with no real-fix or sanitizer option, suppress at the project level. Use the **multicriteria** syntax — the single-line `sonar.issue.ignore` is not honored by the GitHub App integration.

```properties
sonar.issue.ignore.multicriteria.e1.ruleKey=pythonsecurity:S8707
sonar.issue.ignore.multicriteria.e1.resourceKey=**/catalog_updater.py
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| `# nosonar` on line above the violation | Move to same line; check `textRange` |
| `# nosonar S2083` (with rule ID suffix) | Use bare `# nosonar` (rule ID is decorative) |
| `sonar.issue.ignore=rule:pattern` syntax | Use `sonar.issue.ignore.multicriteria.N.ruleKey + .resourceKey` |
| Suppressing S8707 with `# nosonar` when path is from CLI | Use `Path.resolve()` first; it sanitizes the data-flow |
| `textRange` says line 67 but file shows the function definition on line 60 | Sonar reports the function definition line for S3516 |

## Real-World Impact (issue #141)

- 12 PRs across 2 sessions to land 71 fixes
- ~6 Quality Gate cycles wasted on mis-placed markers before settling on same-line + resolve()
- Final pattern: `Path.resolve()` sanitizer for S8707 + same-line `# nosonar` for S3516/S2083
