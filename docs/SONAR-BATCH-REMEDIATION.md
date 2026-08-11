# SonarCloud Batch Remediation

Workflow + strategy. Captures the slice-by-severity PR pattern from issue #141 (71 fixes across 7 PRs in one session).

## The Core Tension

SonarCloud's Quality Gate has a "new code" condition: any **new** MAJOR/BLOCKER/CRITICAL issue fails the gate. If you batch-fix in one PR, you may introduce NEW findings as you refactor (e.g. splitting a CC=57 function can create new S3776 violations on the helpers).

**Solution: slice by severity + area, with BLOCKERs first.**

## PR Slice Template (7-PR shape for ~70 findings)

| PR | Scope | Severity | Count | Lines |
|----|-------|----------|-------|-------|
| 1 | BLOCKER (all) | BLOCKER | 7 | ~80 |
| 2 | CRITICAL complexity | CRITICAL | 5 | ~400 |
| 3 | GitHub Actions hardening | MAJOR | ~22 | ~60 |
| 4 | Python security rules | MAJOR | ~10 | ~80 |
| 5 | Python code smells | MAJOR+MINOR | ~14 | ~40 |
| 6 | Shell scripts | MAJOR | ~5 | ~20 |
| 7 | Remaining MAJOR/MINOR catch-all | mixed | ~8 | ~20 |

Each PR is <500 LOC diff and reviewable in one sitting. Total = ~600 LOC touched across 17 files.

## Why Severity-First (Not File-First)?

File-first slicing (one PR per file) means each PR has mixed severity. Reviewers can't prioritize the worst issues, and the BLOCKER-level S2083 path-traversal gets the same attention as a MINOR `[0-9] → \d` refactor.

Severity-first means:
- Worst issues land first → if review budget runs out, the dangerous stuff is already fixed
- Each PR's Quality Gate threshold is consistent (BLOCKER-only PRs have a tighter gate)
- Reviewers can match their domain expertise to the slice (security folks review security-tier PRs)

## Parallel vs Sequential Work

Sequential, not parallel. Reasons:
- Cross-file issues: a single refactor may touch `refresh_pins.py` from PR 2 AND PR 4. Parallel branches conflict at merge time.
- Pattern application: PR 1 establishes the `# nosonar` placement convention. Subsequent PRs apply the same convention.
- CI feedback loop: if PR 1 needs an unexpected refactor, PR 2-7 can adjust before opening.

Subagents only for independent read-only research (e.g. analyzing 50 different S3516 sites in parallel).

## Common Mistakes

| Mistake | Fix |
|---|---|
| Single 1000+ LOC PR | Slice by severity per the template |
| PR includes refactor + suppress mix | One tier per PR |
| Open all PRs at once | Sequential — wait for each to merge before opening the next |
| Skip Quality Gate check between PRs | Always check `project_status` before merging |
| Auto-close epic issue when first PR merges | Close only when ALL PRs are merged |

## When the Quality Gate Won't Clear

If real fix introduces new finding (e.g. CC refactor creates new S3776 on helpers):

1. Add `sonar-project.properties` exclusions with rationale comments
2. Commit to a separate "follow-up" PR
3. Don't force-merge a failing PR — the gate exists to prevent regressions

## Real-World Impact (issue #141)

- 71 fixes in 8 PRs across one session
- ~3,000 LOC touched, 0 behavior changes
- All BLOCKER + CRITICAL resolved by PR 2
- Code smells and shell scripts landed last (lowest risk, easiest to review)
