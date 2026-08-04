# skills-pack

> heretek marketplace — first-party plugin

## What

Generic skills pack. Ships two vetted skills that improve every Claude Code session regardless of stack:

- **caveman** — terse token-saving replies (drop articles, filler, hedging, tool-call narration). Vendored from [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (95,783★, MIT).
- **superpowers** — process discipline: invoke the relevant skill BEFORE any response. Vendored from [obra/superpowers](https://github.com/obra/superpowers) (266,415★, MIT).

## Install

```bash
/plugin install skills-pack@heretek
```

## Components

- `skills/` — auto-discovered by Claude Code via the `skills: "./skills/"` declaration in `.claude-plugin/plugin.json`.
  - `skills/caveman/SKILL.md`
  - `skills/superpowers/SKILL.md`

## Vendoring scope (v1)

Each skill ships a minimal stub `SKILL.md` whose `description:` frontmatter advertises the skill to Claude Code's auto-discovery and whose body is a one-paragraph usage pointer. Vendoring the full upstream `SKILL.md` content is beyond v1 scope. For the full superpowers methodology (14 first-party skills), users can additionally run upstream `install.sh` from `obra/superpowers`; the stub keeps the entry-point skill name discoverable.

## D7 vetting

Every item in `items[]` passed the D7 bar with a documented ADR:

| skill | upstream | stars | license | ADR |
|-------|----------|-------|---------|-----|
| caveman | JuliusBrussee/caveman | 95,783 | MIT | [reviews/skills-pack-caveman.md](../../catalog/reviews/skills-pack-caveman.md) |
| superpowers | obra/superpowers | 266,415 | MIT | [reviews/skills-pack-superpowers.md](../../catalog/reviews/skills-pack-superpowers.md) |

Tier-2 candidates `find-skills` and `review-work` were investigated and rejected — see [catalog/rejected.md](../../catalog/rejected.md) and the respective ADRs.

## License

MIT — see [LICENSE](../../LICENSE).
