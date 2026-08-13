# llama-builds

## Project summary
CI/CD registry for llama.cpp family builds.

## Stack & runtime targets
- Languages: Python 3.11+
- Package managers: pip, setuptools
- OS/arch: Linux x86_64
- Outputs: pre-compiled distributed bundles and/or a local CLI runtime.

## Build, test, lint, run commands
- Build: `python -m build`
- Test: `pytest`
- Lint: `ruff check .`
- Run: `python -m heretek_builds --help`

## Project structure
```
llama-builds/
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
- GitHub Project: https://github.com/orgs/Heretek-AI/projects/1
- SonarCloud project: https://sonarcloud.io/project/overview?id=Heretek-AI_llama-builds
- Super-linter config: .github/linters/
- Skills index: `.claude/skills/manifest.json`
- Issue templates: `.github/ISSUE_TEMPLATE/`
- Spec doc: `docs/superpowers/specs/`
- Backlog seed: https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/llama-builds.yaml
