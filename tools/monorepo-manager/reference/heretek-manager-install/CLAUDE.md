# heretek-manager

This repository is governed by `AGENTS.md` (read it first). This file
adds Claude-specific guidance.

## Skills to use
- `superpowers:brainstorming` — required for any non-trivial change.
- `superpowers:writing-plans` — required after brainstorming, before code.
- `superpowers:test-driven-development` — required when implementing.
- `superpowers:verification-before-completion` — required before claiming done.
- `superpowers:systematic-debugging` — required for any bug report.

## Model tiers
- Default: `sonnet`.
- For large refactors across the codebase: `opus`.
- For narrow bug fixes or doc edits: `haiku`.

## Hook expectations
- `PreToolUse` Bash hook blocks `rm -rf`, `git push --force`, and
  `git reset --hard` against protected branches.
- `Stop` hook runs lint-only verification before allowing the turn to end.
- A `.claude/hooks/.lockfile` hash mismatch refuses to load this manifest;
  run `scripts/init-harness.sh --refresh-hooks` to remediate.
