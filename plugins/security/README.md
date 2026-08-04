# security

> heretek marketplace — first-party plugin

## What

Security cross-cutting plugin: ships first-party security-research and audit-checklist skills that any stack can use. Auditing checklists help catch security-sensitive regressions before they ship.

## Install

```bash
/plugin install security@heretek
```

## Components

- `skills/` — auto-discovered by Claude Code via the `skills: "./skills/"` declaration in `.claude-plugin/plugin.json`.
  - `skills/security-research/SKILL.md`
  - `skills/audit-checklist/SKILL.md`

## Usage

The skills are auto-loaded by Claude Code when relevant. To invoke explicitly:

- **security-research**: ask the agent to "do a security research pass" or "model threats for X". Useful for security audit prep or incident triage.
- **audit-checklist**: ask the agent to "run the pre-deploy audit checklist" before merging a security-sensitive change. Skip categories that don't apply.

## D15 conflict policy (NO hooks)

The `security` plugin ships **only first-party skills**. Per decision D15, only the `hooks` plugin owns hook files. This deliberate separation keeps the hooks flagship (fast blocking <100ms / slow on-demand / git pre-commit) the single integration point for cross-cutting quality gates, and lets the security plugin focus on skills + (future) audit commands without competing for hook ownership.

If you need a hook to enforce a security check, add it to the `hooks` plugin instead.

## License

MIT — see [LICENSE](../../LICENSE).
