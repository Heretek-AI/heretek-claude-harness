# agents

> heretek marketplace — first-party plugin

## What

Reusable sub-agent definitions for common review and testing tasks. Each sub-agent is a focused system prompt that can be invoked via Claude Code's `Task` tool.

## Install

```bash
/plugin install agents@heretek
```

## Components

- `agents/` — auto-discovered by Claude Code via the `agents: "./agents/"` declaration in `.claude-plugin/plugin.json`.
  - `agents/code-reviewer.md` — reviews diffs for correctness, style, and convention adherence.
  - `agents/security-reviewer.md` — reviews diffs for input validation, authn/z, secrets, and crypto.
  - `agents/test-engineer.md` — writes or updates tests for changed code.

## Usage

Invoke a sub-agent by name via the `Task` tool:

- **code-reviewer**: ask the agent to "review this diff for correctness and style".
- **security-reviewer**: ask the agent to "do a security review of this diff" or "check for input-validation gaps". Pair with the `audit-checklist` skill in the security plugin for a full audit.
- **test-engineer**: ask the agent to "write tests for this change" or "add regression tests for the bug we just fixed".

## License

MIT — see [LICENSE](../../LICENSE).
