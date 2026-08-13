# GitHub Copilot Instructions for Heretek Swarm

## Project Context

This is a distributed multi-agent swarm intelligence system. You are working with 23 specialized agents across 6 tiers. The codebase uses Python 3.11+ with FastAPI, NATS, PostgreSQL, Redis, and Qdrant.

## Code Style

### Python
- Use type hints on ALL public functions and methods
- Prefer `async/await` for I/O-bound operations
- Use `pathlib.Path` instead of `os.path`
- Docstrings in Google style with Args/Returns/Raises
- Maximum line length: 120 characters
- Use `ruff` for linting — run `ruff check .` before committing

### TypeScript/React
- Use functional components with hooks
- Prefer `useCallback` for memoized callbacks passed as props
- API calls through `fetch` with proper error handling
- Environment variables prefixed with `VITE_`
- Use `const` assertions for literal types

## Testing Requirements

- Every new feature needs tests in `tests/`
- Run `pytest tests/ -v` before pushing
- Frontend: `cd swarm-dashboard && npm test`
- E2E: `cd swarm-dashboard && npx playwright test`
- Target 80%+ coverage on new code

## Security Rules

- NEVER commit secrets, API keys, or credentials
- Use `secrets/encrypted.env` with SOPS for sensitive config
- All NATS communication must use mTLS
- Validate ALL inputs in agent message handlers
- Follow Zero-Trust architecture: authenticate every inter-agent message
- No `eval()`, `exec()`, or dynamic code execution
- No unsanitized path traversal in file operations

## Architecture Conventions

- Agents extend `AgentActor` from `backend/heretek_swarm/actors/base/core.py`
- Use mixin composition for shared behaviors (message handling, state management)
- Follow the three-tier fallback pattern: Event mesh → Direct registry → Queue
- HeavySwarm workflows follow: Research → Analysis → Alternatives → Verification → Decision

## Commit Conventions

Use conventional commits:
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation
- `refactor:` — code restructuring
- `test:` — adding/updating tests
- `chore:` — maintenance tasks
- `security:` — security fixes

## graphify

For any question about this repo's architecture, structure, components, or how to add/modify/find
code, your first action should be `graphify query "<question>"` when `graphify-out/graph.json`
exists. Use `graphify path "<A>" "<B>"` for relationship questions and `graphify explain "<concept>"`
for focused-concept questions. These return a scoped subgraph, usually much smaller than the full
report or raw grep output.

Triggers: "how do I…", "where is…", "what does … do", "add/modify a <component>",
"explain the architecture", or anything that depends on how files or classes relate.

If `graphify-out/wiki/index.md` exists, use it for broad navigation. Read `graphify-out/GRAPH_REPORT.md`
only for broad architecture review or when query/path/explain do not surface enough context. Only read
source files when (a) modifying/debugging specific code, (b) the graph lacks the needed detail, or
(c) the graph is missing or stale.

Type `/graphify` in Copilot Chat to build or update the graph.
