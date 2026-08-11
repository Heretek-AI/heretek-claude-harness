---
name: issue-loop
description: Use when the user asks to drain a queue of GitHub issues autonomously. Activates OMC autopilot mode against `scripts/issue_loop/cli.py`.
---

# Issue Loop (Autopilot)

Drain the GitHub issue queue end-to-end with no human gating inside the session.

## When to use

User says any of: "drain the issue queue", "run the issue loop",
"process the security-scan issues", "auto-fix #158 onward", "autopilot the
issue loop".

## Activation

The skill is activated by user invocation. There is no cron/webhook trigger.
The user runs `/issue-loop` (or invokes via slash command) when ready.

## Flow

1. **Pre-flight:** `python -m scripts.issue_loop.cli status` to confirm ledger
   state.
2. **Tick loop:** repeat until `select-next` returns `{}`:
   1. `python -m scripts.issue_loop.cli select-next` → `IssueRef | {}`
   2. If `{}`: emit periodic summary, then halt cleanly.
   3. `python -m scripts.issue_loop.cli mark-attempt <N>`
   4. `python -m scripts.issue_loop.cli classify <N>` → `fix|investigate|spec|break-down|skip`
   5. Dispatch path-specific subagent(s) via the `Agent` tool:
      - **fix**: explore → planner → executor → test-engineer → verifier (existing)
      - **investigate**: read `scripts/issue_loop/prompts/investigator.md`
      - **spec**: read `scripts/issue_loop/prompts/spec_writer.md` then
        `scripts/issue_loop/prompts/critic.md` (for spec verdict), then
        implementation flow
      - **break-down**: read `scripts/issue_loop/prompts/breakdowner.md`
      - **skip**: log-event + comment + mark-skipped
   6. Poll gate (CI + Copilot + SonarCloud) via GitHub MCP.
   7. Finalize:
      - `fix` green → squash-merge → `mark-merged`
      - `fix` red → leave PR open + log-event "needs-human"
      - `investigate` pivot → goto fix path
      - `investigate` no-fix → log-event + comment + `mark-investigated`
      - `spec` impl green → squash-merge + comment "spec: <path>"
      - `spec` impl red → leave PR open
      - `break-down` → `register-sub-issue` per child
      - `skip` → log-event + `mark-skipped`
3. **Halt conditions:** GitHub rate limit, infra failure, Anthropic error.
   NOT halt: cross-issue verifier rejects, quality gate failures,
   SonarCloud blocks, token/wall-clock limits (per user choice).

## Periodic summary

Every `periodic_summary_minutes` (default 30): emit a throughput summary
(issues processed by path+outcome since last summary, current issue in
flight, ETA, halt-condition warnings).

## Don't

- Don't auto-close issues on GitHub. They stay open with comments.
- Don't lower the verifier `Model='opus'` requirement.
- Don't change `halt_after_cross_issue_rejects: 5` — the autopilot skill
  overrides it in-memory; the config value remains for non-autopilot runs.
- Don't widen the issue filter without updating the spec.
