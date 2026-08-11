# Branch Cleanup Design

**Date:** 2026-08-11
**Status:** Approved
**Owner:** user (autonomous execution)

## Goal

Delete branches whose tip is an ancestor of `main` (already merged via
PR/squash). Apply to both local and remote. Skip branches currently checked
out in worktrees, branches with unmerged commits, `main` itself, and
`sprint/*` integration branches (preserve as historical record).

## Scope

**In:**
- Local branches whose tip is in main's history (`git cherry main <branch>` empty)
- Remote branches (origin/*) matching the same criterion
- Remote-tracking refs (`origin/<branch>`) orphaned by remote deletion

**Out:**
- `main`
- `sprint/*` integration branches (preserve as historical record until next sprint)
- Branches currently checked out in worktrees (`git worktree list` reports them)
- Branches with unmerged commits (kept for manual triage)
- `backup/main-before-origin-reset` (intentional manual backup)

## Detection Algorithm

For each candidate branch (excluding `main`, `sprint/*`, worktree-checked-out):

```bash
# Empty output = all commits in main = merged
git cherry main <branch>
```

This is more robust than `git branch --merged` when multiple merge bases exist.

For remote-tracking refs (`origin/<branch>`):

```bash
git cherry main origin/<branch>
```

## Safety Net

Three layers:

1. **Dry-run report**: print all candidates BEFORE any deletion. Save to
   `docs/superpowers/specs/2026-08-11-branch-cleanup-report.txt`.
2. **Manual gate** (skipped per user: "execute autonomously, bypass human gate").
3. **Verification**: re-run `git branch` + `git branch -r` post-deletion;
   confirm `main` SHA unchanged; confirm `sprint/v3.5-observability-2026-08-11`
   still present.

For deletion:
- Local: `git branch -d <branch>` (refuses if unmerged)
- Remote: `git push origin --delete <branch>` (one-way; safety = dry-run only)
- Tracking ref: `git remote prune origin` (removes orphaned refs)

## Verification

- Branch counts drop
- No protected branches deleted
- `git log main --oneline -1` unchanged
- Sprint branch preserved
- `gh pr list --state closed --state all --limit 50` shows no PRs whose head ref was deleted out from under them
