---
name: issue-loop
description: Use when the user asks to drain a queue of GitHub issues autonomously. Activates OMC ralph mode against `scripts/issue_loop/driver.py`.
---

# Issue Loop

Drain the `security-scan`/`tech-debt` issue queue end-to-end with no human
in the inner loop.

## When to use this skill

User says any of:
- "drain the issue queue"
- "run the issue loop"
- "process the security-scan issues"
- "auto-fix #158 onward"

## Activation

```bash
# Pre-flight (dry-run on issue #158 only, no PR)
python -m scripts.issue_loop.driver --dry-run --issue 158

# Full loop
python -m scripts.issue_loop.driver --run-until-empty
```

## What the skill does

1. Reads the ledger at `.omc/state/issue-loop/ledger.json`.
2. Picks the lowest-numbered unprocessed issue matching
   `security-scan`/`tech-debt`.
3. Creates branch `auto/<num>-<slug>`.
4. Spawns 5 subagents (explore, planner, executor, test-engineer, verifier)
   in an isolated worktree.
5. Opens a PR via the GitHub MCP server.
6. Waits for CI + Copilot + code-reviewer + SonarCloud.
7. Squash-merges on green; marks `skipped` after 3 verifier rejections.
8. Halts after 5 cross-issue verifier rejections.

## Stop / resume

- The ledger survives compaction and process restarts. Re-running the skill
  resumes from the last pending entry.
- To halt cleanly: send `stop` to the terminal.
- To reset a single issue: edit the ledger JSON (status back to `pending`,
  attempts to 0).

## Don't

- Don't lower the verifier model from `opus`. Security findings need the
  best model we have.
- Don't widen the issue filter without updating `.heretek/issue-loop-config.json`
  AND the spec — they're coupled.
- Don't open PRs to `main` directly; all work happens on `auto/*` branches.
