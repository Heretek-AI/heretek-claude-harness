# heretek-manager

## Project summary
Local NPM CLI + WebUI for the Heretek AI runtime.

## Stack & runtime targets
- Languages: TypeScript 5 + Node 20
- Package managers: npm
- OS/arch: Linux x86_64
- Outputs: pre-compiled distributed bundles and/or a local CLI runtime.

## Build, test, lint, run commands
- Build: `npm run build`
- Test: `npm test`
- Lint: `npx eslint .`
- Run: `npx heretek-manager --help`

## Project structure
```
heretek-manager/
├── .github/
│   ├── workflows/
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── .claude/
│   ├── skills/
│   ├── settings.json
│   └── hooks/
├── .mcp.json
├── AGENTS.md
├── CLAUDE.md
├── sonar-project.properties
├── .pre-commit-config.yaml
└── README.md
```

## Conventions
- Code style: enforced by pre-commit + super-linter.
- Branch naming: `feat/<scope>`, `fix/<scope>`, `chore/<scope>`.
- Commit messages: Conventional Commits.
- PRs require a linked GitHub Issue (`Closes #<id>` or `Issue: #<id>`).

## Do / Don't list
- DO validate build outputs against the manifest schema.
- DO run the four required CI checks locally before pushing.
- DON'T push directly to `main`; PRs only.
- DON'T commit build artifacts or `.env` files.

## Pointer block
- GitHub Project: https://github.com/orgs/Heretek-AI/projects/2
- SonarCloud project: https://sonarcloud.io/project/overview?id=Heretek-AI_heretek-manager
- Super-linter config: .github/linters/
- Skills index: `.claude/skills/manifest.json`
- Issue templates: `.github/ISSUE_TEMPLATE/`
- Spec doc: `docs/superpowers/specs/`
- Backlog seed: https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/heretek-manager.yaml
