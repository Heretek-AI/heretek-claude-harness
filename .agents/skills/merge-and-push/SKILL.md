---
description: Post-SDD merge dance — fast-forward feature branch to main, run tests on merged result, push to origin, clean up worktree + branch.
---

# heretek:merge-and-push

Wraps the post-SDD finish-a-development-branch dance: checkout main, fast-forward merge the feature branch, run tests, push, clean up.

## When to use

After a sub-project implementation (SP1-SP4 pattern) is complete and the final whole-branch review returned "Ready to merge" (or with fixable findings that have been resolved). NOT for ad-hoc commits — use plain git for those.

## Pre-flight checks (fail fast)

Before doing anything, verify:

1. **Clean working tree**: `git status --porcelain` returns empty. If dirty, refuse — uncommitted changes must be stashed or committed first.
2. **Named branch**: `git rev-parse --abbrev-ref HEAD` returns a branch name (not `HEAD`). If detached, refuse — can't push a detached HEAD without first naming a branch.
3. **Source branch exists**: the user-provided branch (or auto-detected from `git rev-parse --abbrev-ref HEAD`) must exist on origin: `git ls-remote origin <branch>` returns a SHA.
4. **Fast-forwardable**: `git merge-base --is-ancestor <source> <target>` confirms the source branch is an ancestor of the target (so `git merge --ff-only` will succeed without conflicts).

If any of these fail, report the failure to the user and stop. Do NOT proceed.

## Steps

### Step 1: Confirm with user

Print a one-line confirmation prompt:

```
About to merge: <source-branch> → <target-branch>
After: tests will run on merged result. Then push to origin and clean up worktree + branch.
Proceed? (yes/no)
```

Wait for explicit confirmation. If the user says no, stop.

### Step 2: Fast-forward merge

```bash
git checkout <target-branch>          # default: main
git pull --ff-only                      # skip if no upstream (origin gone); warn user
git merge <source-branch> --ff-only    # refuses if not fast-forwardable
```

If `git pull` fails because origin/main has moved, warn the user — the local main is stale, the merge may have conflicts. Suggest they pull manually first.

If `git merge --ff-only` refuses (not fast-forwardable), the source branch has diverged from target. Stop and ask the user whether to rebase source → target first, or whether they meant a different source.

### Step 3: Run tests on merged result

```bash
. .venv/bin/activate
pip install -q -r requirements-dev.txt
pytest -q
python scripts/validate.py
python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json
bash tests/smoke/fast_gate_smoke.sh
```

**If any of these fail, STOP.** Do NOT push, do NOT clean up. Report the failure to the user with the test output.

### Step 4: Push to origin

```bash
git push -u origin <target-branch>
```

If push fails (e.g., rejected because origin has moved), stop and report. Do NOT clean up — the user may need to pull + rebase + retry.

If the push is rejected because the local branch is behind origin, do NOT force-push. Report and stop.

### Step 5: Clean up

Only after push succeeds:

```bash
# Remove worktree (only if the merge was done in a worktree)
WORKTREE_PATH=$(git worktree list | grep -F "<source-branch>" | awk '{print $1}')
if [ -n "$WORKTREE_PATH" ] && [ "$WORKTREE_PATH" != "$(git rev-parse --show-toplevel)" ]; then
  git worktree remove --force "$WORKTREE_PATH"
  git worktree prune
fi

# Delete the feature branch (locally + remote)
git branch -d <source-branch>                              # local
git push origin --delete <source-branch> 2>/dev/null || true   # remote, best-effort
```

If `git worktree remove` fails (e.g., worktree has uncommitted changes), warn the user — they may need to clean up manually. Do NOT fail the whole skill on this.

### Step 6: Report final state

```
✓ Merged <source-branch> → <target-branch>
✓ Tests pass on merged result (67 passed, 1 skipped)
✓ Pushed to origin/<target-branch>: <remote-sha>
✓ Cleaned up local branch <source-branch> + worktree
✓ Local HEAD: <local-sha>
```

## Acceptance criteria

- [ ] Pre-flight checks all pass before any state mutation
- [ ] User explicitly confirmed the merge before proceeding
- [ ] Tests all pass on merged result
- [ ] Push succeeds
- [ ] Worktree removed (if applicable)
- [ ] Feature branch deleted locally + remote (best-effort)
- [ ] Final state reported to user

## Error handling

| Failure | Action |
|---|---|
| Dirty working tree | Refuse; tell user to stash or commit |
| Detached HEAD | Refuse; tell user to checkout a branch |
| Source branch not on origin | Refuse; tell user to push source first |
| Not fast-forwardable | Refuse; tell user to rebase source → target |
| Any test fails | STOP; do NOT push, do NOT clean up; report |
| Push rejected | STOP; do NOT clean up; tell user to pull + retry |
| `git worktree remove` fails | Warn; do NOT fail the whole skill |

## Out of scope

- Creating PRs (this skill pushes directly; PR creation is a separate concern)
- Cross-repository work (heretek has one repo)
- Squashing or rebasing (preserve the feature branch's commit history as-is)
- Tagging releases (separate concern; see Issue #16 for the v1.0 announcement workflow)
