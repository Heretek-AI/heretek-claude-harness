---
name: superpowers
description: Process discipline for Claude Code — invoke the relevant skill BEFORE any response (including clarifying questions). Use when starting any non-trivial task.
---

If a skill applies to what you are doing, you MUST invoke it. If you think there is even a 1% chance a skill might apply, you ABSOLUTELY MUST invoke it.

Invoke relevant or requested skills BEFORE any response or action — including clarifying questions, exploring the codebase, or checking files.

Then announce "Using [skill] to [purpose]" and follow the skill exactly. If it has a checklist, create a todo per item.

Skill priority: process skills (brainstorming, systematic-debugging, writing-plans, etc.) come first — they set the approach; implementation skills carry it out. "Let's build X" → superpowers:brainstorming first. "Fix this bug" → superpowers:systematic-debugging first.

User instructions (CLAUDE.md, AGENTS.md, GEMINI.md, direct requests) take precedence over skills. Only skip skill workflows when your human partner has explicitly told you to.

If you were dispatched as a subagent to execute a specific task, ignore this skill.

Full methodology vendored from upstream at `obra/superpowers` (SHA `44c9b2d6e889982ac18c27d05a19fefe335194e1`); this is the v1 stub pointing to the entry-point `using-superpowers` skill. To install the full skill tree, run upstream `install.sh` from https://github.com/obra/superpowers.
