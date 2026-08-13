# Contributing to Heretek Swarm

## Development Setup

```bash
# Clone and set up
git clone https://github.com/Heretek-AI/heretek-swarm.git
cd heretek-swarm
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e backend/
pip install -e "backend/[dev]"

# Frontend
cd swarm-dashboard
npm install
```

## Development Workflow

1. **Create a branch**: `git checkout -b feature/your-feature` or `fix/your-fix`
2. **Make changes**: Follow code conventions in `AGENTS.md`
3. **Run tests**: `pytest tests/ -v` and `cd swarm-dashboard && npm test`
4. **Run linters**: `ruff check backend/` and `cd swarm-dashboard && npm run lint`
5. **Commit**: Use conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
6. **Push and create PR**: Describe what changed and why

## Pull Request Requirements

- [ ] All tests pass
- [ ] Linting passes (ruff + eslint)
- [ ] Type checking passes (mypy + tsc)
- [ ] No new security vulnerabilities introduced
- [ ] Relevant documentation updated
- [ ] PR description explains the change

## Code Review

All PRs require at least one review from a maintainer. AI-generated PRs should be clearly labeled.

## Testing

- **Unit tests**: `tests/` directory, run with `pytest`
- **Integration tests**: Files prefixed with `test_full_` or `test_e2e_`
- **Frontend tests**: `swarm-dashboard/` with Playwright
- **Coverage target**: 80%+ on critical paths

## Questions?

Open a Discussion on GitHub or contact the team on Discord.
