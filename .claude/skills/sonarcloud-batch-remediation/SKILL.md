---
name: sonarcloud-batch-remediation
description: Use when remediating a batch of 10+ SonarCloud findings on this repository and need to decide PR count, slicing strategy, and sequencing. Trigger when a SonarCloud sweep produces a multi-dozen issue list that needs to be closed in a single session or across a few sessions.
---

# SonarCloud Batch Remediation

Workflow + strategy. Captures the slice-by-severity PR pattern from issue #141 (71 fixes across 7 PRs in one session).

## When to Use

You have a SonarCloud issue snapshot showing **10+ open findings** on this repo and want to close them efficiently without:
- Creating a 1000+ LOC PR that's unreviewable
- Running the Quality Gate into a wall because PRs grow faster than suppressions can keep up
- Spending hours debugging why `# nosonar` markers silently don't work

If you're fixing 1-3 findings, this skill is overkill — just use [sonarcloud-suppression](.) and ship a single PR.

## The Core Tension

SonarCloud's Quality Gate has a "new code" condition: any **new** MAJOR/BLOCKER/CRITICAL issue fails the gate. If you batch-fix in one PR, you may introduce NEW findings as you refactor (e.g. splitting a CC=57 function can create new S3776 violations on the helpers). One giant PR can fail because the new helper functions introduced their own issues.

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

## Step-by-Step Workflow

### Step 1: Snapshot the issues

```bash
curl -sS -L "https://sonarcloud.io/api/issues/search?componentKeys=Heretek-AI_heretek-claude-harness&statuses=OPEN,CONFIRMED&ps=80" \
  -H "User-Agent: Mozilla/5.0" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(i['severity'], i['component'].split(':')[-1], i['line'], i['rule']) for i in d['issues']]"
```

Group by severity + rule. The top-3 rules usually cover ~50% of issues.

### Step 2: Plan the slices

Open an epic GitHub issue documenting:
- The 7-PR slice with rationale
- The canonical issue list (file:line + rule)
- The approach for each tier (refactor vs suppress)
- The verification commands (`pytest -q`, `python scripts/validate.py`)

The PRs reference the epic via `Part of #N` in their body. The epic issue stays open until all PRs merge.

### Step 3: Open PRs sequentially

For each PR:
1. Branch from main (`fix/<topic>`)
2. Make changes
3. Run local CI: `pytest -q && python scripts/validate.py && python scripts/generate_marketplace.py`
4. Push + open PR
5. Wait for CI; check Quality Gate status:
   ```bash
   curl -sS -L "https://sonarcloud.io/api/qualitygates/project_status?projectKey=Heretek-AI_heretek-claude-harness&pullRequest=<N>" -H "User-Agent: Mozilla/5.0"
   ```
6. If Quality Gate fails → read [sonarcloud-suppression](.) for the patterns
7. If Quality Gate OK → merge via squash
8. Move to next PR

The sequential model lets you apply uniform fix patterns (e.g. one suppression style across all S3516s) and learn from CI failures (the BLOCKER-suppression pattern from PR 1 applies directly to PR 5).

### Step 4: Update the epic

After each merge, post a comment to the epic with the PR link and a one-line summary. Don't auto-close — the epic closes only after the last PR merges.

## Why Severity-First (Not File-First)?

File-first slicing (one PR per file) means each PR has mixed severity. Reviewers can't prioritize the worst issues, and the BLOCKER-level S2083 path-traversal gets the same attention as a MINOR `[0-9] → \d` refactor.

Severity-first means:
- Worst issues land first → if review budget runs out, the dangerous stuff is already fixed
- Each PR's Quality Gate threshold is consistent (BLOCKER-only PRs have a tighter gate than MAJOR-only ones)
- Reviewers can match their domain expertise to the slice (security folks review security-tier PRs)

## Parallel vs Sequential Work

Sequential, not parallel. Reasons:
- Cross-file issues: a single refactor may touch `refresh_pins.py` from PR 2 (cognitive complexity) AND PR 4 (security rules). Parallel branches conflict at merge time.
- Pattern application: PR 1 establishes the `# nosonar` placement convention. Subsequent PRs apply the same convention, not a new one.
- CI feedback loop: if PR 1 needs an unexpected refactor, PR 2-7 can adjust before opening.

Subagents only for independent read-only research (e.g. analyzing 50 different S3516 sites in parallel — no file mutation).

## Common Mistakes

| Mistake | Fix |
|---|---|
| Single 1000+ LOC PR | Slice by severity per the template above |
| PR includes refactor + suppress mix | One tier per PR; reviewers know what to expect |
| Open all PRs at once | Sequential — wait for each to merge before opening the next |
| Skip Quality Gate check between PRs | Always check `project_status` before merging |
| Auto-close epic issue when first PR merges | Close only when ALL PRs are merged |

## When the Quality Gate Won't Clear

Sometimes a real fix introduces a new finding (e.g. CC refactor creates new S3776 on the helpers). If you've tried [sonarcloud-suppression](.) patterns and the gate still fails:

1. Add `sonar-project.properties` exclusions with rationale comments
2. Commit to a separate "follow-up" PR (e.g. PR #149 in #141 was a single-line marker relocation)
3. Don't force-merge a failing PR — the gate exists to prevent regressions

## Real-World Impact (issue #141)

- 71 fixes in 8 PRs across one session
- ~3,000 LOC touched, 0 behavior changes
- All BLOCKER + CRITICAL resolved by PR 2
- Code smells and shell scripts landed last (lowest risk, easiest to review)
- Epic issue closed once last PR (#149) merged

## Related Skills

- [sonarcloud-suppression](.) — when you need to suppress or work around a specific finding
- `merge-and-push` (this repo) — for the post-merge cleanup after each PR
- `superpowers:writing-plans` — for the underlying multi-PR planning methodology
