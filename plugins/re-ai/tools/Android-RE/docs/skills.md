# Skills

Claude Code skills are markdown recipes that compose MCP tools. Each skill
lives in `skills/<name>/SKILL.md` and is symlinked into
`~/.claude/skills/<name>/` by `bin/install.sh`.

## Trigger phrases

Each `SKILL.md` declares trigger phrases in its frontmatter `description`.
Examples:

> "Use when the user wants to triage an APK, perform a static analysis
> overview, or generate a MASVS-aligned report."

The agent uses these triggers to decide which skill to load. A skill
typically asks the user one or two clarifying questions, then walks through
the workflow.

## Phase 1 skills

- **`android-re-static-triage`** — 5-minute static overview.
- **`android-re-decompile`** — Pull pseudocode/smali for specific methods.
- **`android-re-masvs-report`** — Single MASVS-aligned report (stub in Phase 1).

## Phase 2 skills

- **`android-re-native-triage`** — Assess native library hardening.
- **`android-re-secrets-scan`** — Deep secrets & risk findings.
- **`android-re-repackage`** — Modify + repackage APK for testing.
- **`android-re-gradle-rebuild`** — Turn an APK into a buildable Gradle project
  (uses `jadx_cleanup_workdir` and `create_gradle_project` to apply the
  post-decompile cleanup pipeline to large modern Kotlin/Compose APKs).

## Phase 3 skills

- **`android-re-dynamic-hook`** — Hook a method, observe behavior.
- **`android-re-sslpinning-bypass`** — Bypass SSL pinning on a target app.
- **`android-re-frida-script-author`** — Generate Frida scripts with helper
  templates.

## Phase 4 skills

- **`android-re-triage-orchestrator`** — Master skill: drop in APK → MASVS
  report.
- **`android-re-network-intercept`** — Capture HTTPS from app.

## Authoring a new skill

See [Skill Authoring](skill-authoring.md). The minimum is a `SKILL.md` with:

```yaml
---
name: <skill-name>
description: <trigger phrases>
---

# Title

## When to use
## Inputs (with confirm gates)
## Workflow
## Output
## Examples
```

`references/` and `scripts/` subdirectories may be added to keep long-form
material out of the main file.
