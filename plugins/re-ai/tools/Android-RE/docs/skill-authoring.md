# Skill Authoring

A Claude Code skill is a folder containing a `SKILL.md` and optional
`references/`, `scripts/`, and `templates/` subdirectories. The skill is
discovered by Claude Code when the folder is symlinked into
`~/.claude/skills/<name>/`.

## Minimal SKILL.md

```markdown
---
name: android-re-my-skill
description: |
  Use when the user wants to do X, Y, or Z. Trigger phrases include
  "do X", "give me Y", "analyze Z". Do NOT use for unrelated tasks.
---

# Title

One-paragraph summary of what this skill does and when to use it.

## Inputs

List the inputs the user must provide. For destructive actions, declare
`confirm: bool` in the input schema.

## Workflow

1. Step one: call `mcp__android-re-static__open_project` with `apk_path`.
2. Step two: call `mcp__android-re-static__read_manifest` with `project_id`.
3. ...

## Output

Describe the report or artifact this skill produces.

## Examples

### Example 1: simple triage
> User: Triage this APK.
> Skill: opens project, reads manifest, lists components, returns report.

### Example 2: decompile a method
> User: Show me the implementation of `MainActivity.onCreate`.
> Skill: finds class, decompiles method, returns source.
```

## Effect envelope

Declare the skill's effect envelope in the frontmatter so an agent can show
the user what the workflow will do:

```yaml
---
name: android-re-sslpinning-bypass
effect:
  - network: outbound (loads Frida scripts onto a connected device)
  - filesystem: writes a patched APK to ./dist/
  - device: installs and launches the patched APK
requires:
  - device: rooted Android
  - mcp: android-re-dynamic
---
```

## Referencing MCP tools

Always reference MCP tools by their **fully-qualified name**:

```
mcp__<server>__<tool_name>
```

For example: `mcp__android-re-static__decompile_method`. This avoids
ambiguity when multiple MCP servers are loaded.

## Long-form material

Keep the main `SKILL.md` under ~200 lines. Put long-form material in:

- `references/` — additional context (MASVS controls, dangerous permissions,
  Frida API recipes, etc.)
- `scripts/` — reusable code (Frida JS templates, proxy bootstrap shell
  scripts, etc.)
- `templates/` — Jinja2 templates (`.md.j2`) for reports

Reference them from the main file:

```markdown
For the full MASTG v2 control list, see
[`references/masvs-v2.md`](references/masvs-v2.md).
```
