---
name: issue-loop
description: Use when the user asks to drain a queue of GitHub issues autonomously. Invokes the OMC autopilot via `scripts/issue_loop/cli.py`.
---

# Issue Loop

Drain the GitHub issue queue end-to-end with no human gating inside the session.

## Run

```bash
python -m scripts.issue_loop.cli status          # confirm ledger state
python -m scripts.issue_loop.cli select-next     # get next issue
# Then dispatch fix/investigate/spec/break-down/skip per path
```

The autopilot (`scripts/issue_loop.py`) runs the loop until `select-next` returns `{}`. Path-specific subagents are dispatched via the `Agent` tool.

## Paths

- `fix` — explore → planner → executor → test-engineer → verifier
- `investigate` — read `prompts/investigator.md`
- `spec` — `prompts/spec_writer.md` + `prompts/critic.md` (verdict)
- `break-down` — `prompts/breakdowner.md`
- `skip` — log-event + comment + mark-skipped

## Halt conditions

- GitHub rate limit
- Anthropic API error
- Infrastructure failure

NOT halt: cross-issue verifier rejects, quality gate failures, SonarCloud blocks, token/wall-clock limits.

## Don't

- Don't auto-close issues. They stay open with comments.
- Don't lower the verifier `Model='opus'` requirement.
- Don't change `halt_after_cross_issue_rejects: 5`.
- Don't widen the issue filter without updating the spec.
