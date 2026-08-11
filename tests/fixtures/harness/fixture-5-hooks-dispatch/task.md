# Add PostToolUse handler that echoes the tool name

The repo has a working dispatcher at `plugins/hooks/scripts/dispatch.py`
that currently logs only `SessionStart` events. Add a `PostToolUse`
handler that:

- Matches `tool_name == "Bash"`
- Logs `event: PostToolUse` and `tool: <tool_name>` to the dispatcher
  stdout (so the existing instrumentation picks it up).

Constraints:
- Do not modify any other files.
- Keep the handler minimal — just one `print` line per event.
