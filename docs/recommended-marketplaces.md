# Recommended marketplaces

The heretek marketplace focuses on **first-party plugins** vetted to the D7 bar. Some users will also want to add other Claude Code marketplaces for broader coverage.

**These marketplaces are NOT vendored by heretek.** To use them, add them alongside heretek with a separate `/plugin marketplace add` command. Each one has its own vetting process — heretek does not warrant their content.

## Recommended

| Marketplace | Description | Add via |
|---|---|---|
| [Anthropic official](https://github.com/anthropics/claude-code/tree/main/plugins) | First-party Claude Code plugins (`document-skills`, `feature-dev`, etc.) | `/plugin marketplace add anthropic https://github.com/anthropics/claude-code` |
| [claudepluginhub.com](https://www.claudepluginhub.com) | Community-indexed Claude Code plugins with reviews and tags | Browse at https://www.claudepluginhub.com |
| [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | Curated collection of settings, hooks, agents, and skills | `/plugin marketplace add davila7 https://github.com/davila7/claude-code-templates` |

## Not recommended (D7 fail)

| Source | Reason | D7 criterion failed |
|---|---|---|
| `aitmpl.com/*` | Hub, not upstream; items lack verifiable SHA-pinning; several hooks shells out to external subprocesses (D7 source-audit fail) | stars < 500 OR no canonical upstream OR source-audit fail |
| `JanDeMit/pyrus-mcp` | Personal project, low stars | stars < 500 |
| `ComposioHQ/awesome-claude-skills` | Index-only; items not individually vetted | N/A — index |
| Storybook MCP servers | Personal projects, low stars | stars < 500 |

## How to add a marketplace

```bash
/plugin marketplace add <owner/repo>
```

Then install plugins from it:

```bash
/plugin install <name>@<marketplace-name>
```

heretek's `hooks` plugin will run alongside other marketplaces' hooks. Per D15 strict, heretek's hooks take precedence when there are conflicts.

## Adding to this list

If you'd like to recommend a marketplace, open a PR adding a row to the "Recommended" table. The marketplace must:

1. Be open-source (so users can audit what they're installing)
2. Have a clear owner / contact
3. Have at least some vetting process (even if informal)
4. Not duplicate anything already in heretek
