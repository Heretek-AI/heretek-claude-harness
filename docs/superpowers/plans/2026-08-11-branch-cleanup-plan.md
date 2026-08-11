# Branch Cleanup Implementation Plan

> **For agentic workers:** Single-session autonomous execution; bypasses user gates per user instruction. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete merged branches from local + remote; preserve `main`, `sprint/*`, worktree-checked-out, and unmerged branches.

**Architecture:** Detection via `git cherry main <branch>` (empty = merged). Local deletes via `git branch -d`, remote via `git push origin --delete`. Verification via branch counts + main SHA integrity check.

**Tech Stack:** git CLI, gh CLI (for cross-check).

## Global Constraints

- Pre-commit hooks NOT invoked for this cleanup (no code changes)
- `main` MUST remain at SHA `a6088f1` (current HEAD) — verify before + after
- `sprint/v3.5-observability-2026-08-11` MUST be preserved
- `backup/main-before-origin-reset` MUST be preserved (manual backup)
- Branches currently checked out in worktrees MUST be skipped (~6 branches in `/home/john/.paseo/worktrees/*`)

---

### Task 1: Dry-run detection

- [ ] **Step 1: List local branches in worktrees**

```bash
git worktree list --porcelain | grep '^worktree ' | awk '{print $2}'
```

Note: these are the working-dir paths of worktrees; we'll use a different command to identify branches-by-worktree.

- [ ] **Step 2: Identify worktree-checked-out branches**

```bash
git worktree list --porcelain | grep -A1 '^worktree ' | grep '^branch ' | awk '{print $2}' | sed 's|refs/heads/||'
```

Captures the branch names checked out in each worktree.

- [ ] **Step 3: Detect merged local branches**

```bash
git branch --format='%(refname:short)' \
  | grep -v '^main$' \
  | grep -v '^sprint/' \
  | grep -v '^backup/' \
  | while read -r b; do
      # Check if branch is checked out in any worktree
      if git worktree list --porcelain | grep -q "refs/heads/$b"; then
        echo "SKIP (worktree): $b"
        continue
      fi
      # Check if all commits are in main
      if [ -z "$(git cherry main "$b" 2>/dev/null)" ]; then
        echo "MERGED: $b"
      else
        echo "KEEP: $b"
      fi
    done
```

- [ ] **Step 4: Detect merged remote branches**

```bash
git branch -r --format='%(refname:short)' \
  | grep '^origin/' \
  | grep -v 'origin/main$' \
  | grep -v 'origin/sprint/' \
  | grep -v 'origin/backup/' \
  | grep -v 'origin/HEAD' \
  | while read -r r; do
      branch="${r#origin/}"
      if [ -z "$(git cherry main "$r" 2>/dev/null)" ]; then
        echo "MERGED-REMOTE: $r"
      else
        echo "KEEP-REMOTE: $r"
      fi
    done
```

- [ ] **Step 5: Save dry-run report**

```bash
# Capture both reports into one file
{ echo "# Branch cleanup dry-run report"; echo "# Generated $(date -u +%FT%TZ)"; echo;
  echo "## Local"; <step-3-output>; echo;
  echo "## Remote"; <step-4-output>;
} > docs/superpowers/specs/2026-08-11-branch-cleanup-report.txt
```

### Task 2: Execute deletions

- [ ] **Step 1: Confirm main HEAD unchanged**

```bash
git log main --oneline -1
```

Expected: `a6088f1 sprint: v3.5 observability ...`. Abort if different.

- [ ] **Step 2: Delete merged local branches**

For each branch marked MERGED in the dry-run:
```bash
git branch -d <branch>
```

Refuses if unmerged (safety net). If refuses, mark KEEP and skip.

- [ ] **Step 3: Delete merged remote branches**

For each ref marked MERGED-REMOTE in the dry-run:
```bash
git push origin --delete <branch>
```

Skips silently if already deleted (race-safe).

- [ ] **Step 4: Prune orphaned tracking refs**

```bash
git remote prune origin
```

### Task 3: Verify

- [ ] **Step 1: Confirm main HEAD unchanged**

```bash
git log main --oneline -1
```

Expected: `a6088f1 ...`. ABORT if different.

- [ ] **Step 2: Confirm protected branches preserved**

```bash
git branch | grep -E '^(main|sprint/v3.5-observability-2026-08-11|backup/main-before-origin-reset)$'
```

Expected: 3 lines (main, sprint branch, backup). ABORT if any missing.

- [ ] **Step 3: Confirm worktree branches still present**

```bash
git branch | grep -E "^(fix/v1.x-test-unblockers|heretek-maintenance-skills|issue-loop-sdd|plan-next-sprint|relieved-gorilla|repo-state-issues-review|review/codebase-and-issues|review/codebase-and-open-issues|sync-branch-review-open-issues|repo-state-issues-review)$"
```

Expected: each worktree-checked-out branch present. ABORT if any missing.

- [ ] **Step 4: Branch counts**

```bash
echo "Local: $(git branch | wc -l)  (was: 30)"
echo "Remote: $(git branch -r | grep -v HEAD | wc -l)  (was: 70)"
```

Expected: significant drops; protected branches + worktree-checked-out branches preserved.

- [ ] **Step 5: Cross-check via gh CLI**

```bash
gh pr list --state closed --limit 20 --json number,headRefName,title
```

For each PR, verify the headRefName either no longer exists (intentional cleanup) or was preserved because worktree-checked-out / still-needed.
