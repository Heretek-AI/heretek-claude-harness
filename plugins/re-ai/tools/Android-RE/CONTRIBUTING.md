# Contributing

Thanks for your interest in contributing to Android-RE. This project follows
standard open-source development practices.

## Development Setup

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install pre-commit hooks
uv tool install pre-commit
pre-commit install

# Sync all Python packages in the workspace
uv sync --all-packages

# Install the Node bridge
pnpm install

# Run the test suite
uv run pytest
pnpm test
```

## Conventions

- **Python:** Python 3.12+, formatted with `ruff format`, linted with `ruff`,
  type-checked with `mypy --strict`. Pinned dependencies where API churn
  matters (androguard, LIEF, frida).
- **TypeScript:** Node 24+, formatted with `prettier`, linted with `eslint`,
  type-checked with `tsc`. Pinned `@modelcontextprotocol/sdk`.
- **Commits:** Conventional Commits (enforced by `pre-commit`).
  Examples: `feat(static): add decompile_class tool`,
  `fix(frida): handle server version mismatch`,
  `docs(skills): add android-re-secrets-scan recipe`.
- **Branches:** `feat/<scope>`, `fix/<scope>`, `docs/<scope>`, `chore/<scope>`.
  PR target: `main`.

## Adding a New MCP Tool

1. Identify which MCP server owns the tool (static, native, dynamic, triage, bridge).
2. Implement the tool function in `mcp_servers/<server>/src/.../tools/<topic>.py`.
3. Register the tool in `mcp_servers/<server>/src/.../server.py`.
4. Add an in-memory `mcp.Client` test in `tests/test_mcp_<server>.py`.
5. Update `docs/mcp-tool-reference.md` with the new tool's schema and example.

## Adding a New Skill

1. Create `skills/<name>/SKILL.md` with the standard frontmatter
   (`name`, `description` with trigger phrases).
2. Reference MCP tools by their fully-qualified name
   (`mcp__android-re-static__open_project`).
3. Add example recipes or templates in `skills/<name>/references/` or
   `skills/<name>/scripts/` as needed.
4. Run `./bin/install.sh --skills-only` to symlink it locally for testing.

## Pull Request Process

1. Open a PR against `main` with a clear description of the change and its
   motivation.
2. Ensure all CI checks pass (ruff, mypy, pytest, vitest, emulator matrix
   for device-touching changes).
3. Request review from a maintainer.
4. Squash-merge with the PR title as the commit message (it must follow
   Conventional Commits).

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
