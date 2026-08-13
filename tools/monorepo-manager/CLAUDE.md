# monorepo-manager

Governed by `AGENTS.md` (read it first).

## Skills to use
- `superpowers:brainstorming` — required for any non-trivial change.
- `superpowers:writing-plans` — required after brainstorming, before code.
- `superpowers:test-driven-development` — required when implementing.
- `superpowers:verification-before-completion` — required before claiming done.

## Model tiers
- Default: `sonnet`.
- Plan/explore: `opus`.
- Narrow edits: `haiku`.

## Hook expectations
- `.claude/hooks/PreToolUse/deny-destructive.sh` refuses `rm -rf`, `git push --force`, etc.
- `.claude/hooks/PostToolUse/run-pre-commit.sh` runs `pre-commit run --files <changed>`.
- `.claude/hooks/Stop/verify-lint.sh` runs `ruff check .` before allowing the turn to end.
