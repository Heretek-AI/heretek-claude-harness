# probe.sh usage

The `probe.sh` helper appends one JSONL line to a hook's log file. It does NOT actually invoke the Claude Code hook machinery — that's what manual trigger means (Q6). You trigger the real hook separately (e.g., run a Bash command if auditing a `PreToolUse` on Bash), then use `probe.sh` to record what you observed.

## Examples

```bash
# Record a PreToolUse hook firing on a Bash command
HOOK_EVENT=PreToolUse PROBE_TOOL=Bash PROBE_ARGS='{"command":"git status"}' \
  PROBE_DECISION=allow PROBE_NOTE="PreToolUse hook fired; allowed" \
  ./.claude/hooks/probe.sh pre-bash-block-dangerous

# Record a SessionStart observation
HOOK_EVENT=SessionStart PROBE_NOTE="Session restarted; session-start hook observed" \
  ./.claude/hooks/probe.sh session-start
```
