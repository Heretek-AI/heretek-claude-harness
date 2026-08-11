---
description: Post-SDD merge dance — fast-forward feature branch to main, run tests on merged result, push to origin, clean up worktree + branch.
---

# heretek:merge-and-push

Wraps the post-SDD finish-a-development-branch dance. The skill is a thin
pointer to `scripts/merge_and_push.py` (a planned implementation). Until
that script lands, the steps below are the manual fallback.

## Run

```bash
git checkout main                                  # default target
git pull --ff-only
git merge <source-branch> --ff-only               # refuses if not fast-forwardable
pytest -q                                          # 1 minute
python scripts/validate.py
python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json
bash scripts/ci.sh                                 # full local CI
git push -u origin main
git worktree remove --force <worktree-path>        # if applicable
git branch -d <source-branch>
git push origin --delete <source-branch> 2>/dev/null || true
```

## Pre-flight (fail fast)

- `git status --porcelain` empty (no dirty working tree)
- `git rev-parse --abbrev-ref HEAD` ≠ `HEAD` (named branch)
- `git ls-remote origin <branch>` returns a SHA
- `git merge-base --is-ancestor <source> <target>` (fast-forwardable)

If any fails, stop and report.

## On any failure

Stop. Don't push, don't clean up. Report the test output to the user.

## Don't

- Force-push (rejected locally + remotely).
- Squash or rebase (preserve the feature branch's history).
- Create PRs (separate concern).
- Tag releases (separate workflow).
