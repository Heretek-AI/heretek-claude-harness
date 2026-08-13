# Heretek Swarm — AI Agent Instructions

## What this is

A self-governing 23-agent swarm across 6 tiers. Backend is Python 3.11+ on FastAPI; messaging is NATS with mTLS; state is PostgreSQL + Redis + Qdrant (vector). Frontend is a React 19 / Vite 8 / TypeScript dashboard. The whole thing is meant to run 24/7 and reach consensus via the Triad (Alpha/Beta/Charlie) → Steward flow.

## Install & run (verified commands)

Repo root holds the Python build config (`pyproject.toml`, `uv.lock`) — **not** `backend/`.

```bash
# Backend (preferred — uses uv like the Dockerfile does)
uv sync                                 # creates .venv, installs all deps

# Backend (fallback)
pip install -e .

# Frontend (Node 22, per .nvmrc)
cd swarm-dashboard && npm install
```

## Verify (in this order — lint is cheap, tests are slow)

```bash
# Python lint (target-version py311, line-length 120; see ruff.toml)
ruff check .

# Python type check
mypy backend/heretek_swarm/

# Python tests — repo-root `tests/`, not `backend/tests/`
pytest tests/ -v
pytest tests/test_auth.py -v          # single file

# Frontend (uses vitest, NOT jest — root package.json's jest is a stale relic)
cd swarm-dashboard
npm run lint                           # eslint with --max-warnings 0 — strict
npm test                               # vitest run (one-shot)
npm run test:watch                     # vitest watch
npm run build                          # tsc && vite build (full type check)

# Full stack
docker compose up                      # from repo root; 6 services incl. NATS/Postgres/Redis/Qdrant
heretek-swarm status --json            # health check
heretek-swarm run --no-infra --prompt "Hello"   # in-memory mode, no Docker needed
```

## Architecture — facts an agent should know

- **23 agent classes** under `backend/heretek_swarm/actors/<name>/`. Real names differ from the README's marketing list — actual: `arbiter`, `catalyst`, `chronos`, `coder`, `coordinator`, `dreamer`, `echo`, `empath`, `examiner`, `explorer`, `habit_forge`, `historian`, `metis`, `nexus`, `perceiver`, `perceiver_plus`, `prism`, `sentinel`, `sentinel_prime`.
- **Base class** `AgentActor` lives in `backend/heretek_swarm/actors/base/core.py`. Built on `swarms.Agent` (Langroid adapter also present in same dir — pick the right base for new agents).
- **Mixins** in `actors/mixins/`: `audit`, `deliberation`, `health_reporting`, `learning`, `memory`, `memory_access`, `pattern`, `pattern_consumer`, `tribunal`, `validation`. Compose, don't subclass.
- **47 subpackages** under `backend/heretek_swarm/`. Key ones: `actors/`, `api/` (27 FastAPI routers, 175+ endpoints), `consensus/`, `gateway/` (NATS JetStream + A2A), `memory/` (dual-tier: PG + Qdrant), `llm/`, `mcp/`, `orchestration/`, `plugins/`, `state/`.
- **Three-tier fallback** for inter-agent comms: Event mesh → Direct registry → Queue.
- **HeavySwarm workflow**: Research → Analysis → Alternatives → Verification → Decision.

## Conventions (project-specific, not language defaults)

- **Python:** type hints required on all public APIs; `async/await` for I/O; `pathlib.Path`; Google-style docstrings; max 120 chars. Ruff ignores `N801` inside `actors/` (class names like `AgentActor` allowed) and `S101` inside `tests/`.
- **TypeScript:** functional components, `useCallback` for memoized callbacks passed down, env vars prefixed `VITE_`, `const` assertions for literal types, API calls through `fetch` with explicit error handling.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `security:`). One logical change per commit.
- **Coverage:** target 80%+ on new code.

## Operational gotchas

- **Container entrypoint runs migrations first** (`backend/entrypoint.sh` → `scripts/run_migrations.py`). If you change `migrations/`, rebuild the image, or run the script manually before the API.
- **NATS uses mTLS** with certs from `certs/` (gitignored, generated via scripts in the same dir). Certs must be regenerated when the docker network changes.
- **No `claude` or `claude.md`** in the project root despite the README mentioning one — the docs are stale on that. Real agent instructions live in `AGENTS.md` and `.github/copilot-instructions.md`.
- **Docker Compose is the dev orchestrator** — no Kubernetes, no Helm. `docker-compose.yml` is at repo root, not in `backend/`.

## Security (read these before touching auth/secrets/NATS)

- Never commit secrets. SOPS-encrypted files live in `secrets/encrypted.env` (gitignored locally, never pushed).
- `secrets/encrypted.env` is the canonical place for `OPENAI_API_KEY`, `HERETEK_API_KEY`, DB creds, etc.
- All NATS traffic is mTLS; all inter-agent messages are authenticated (zero-trust).
- Input validation mandatory on every agent message handler (`heretek_swarm.security.zero_trust`).
- **No `eval()`, `exec()`, or dynamic code execution** anywhere. No unsanitized path traversal.
- See `.github/instructions/agent_safety.instructions.md` for the auto-applied tool-allowlist / audit-trail rules.

## Auto-applied rules in this repo

Two files under `.github/instructions/` are loaded automatically by every tool call (glob `**/*`):

- `agent_safety.instructions.md` — tool allowlisting, audit trails, rate limits, zero-trust
- `sonarqube_mcp.instructions.md` — SonarQube workflow (`toggle_automatic_analysis` off → edit → `analyze_file_list` → re-enable)

Respect them; don't fight them.

## OpenCode config for this workspace

- MCP servers (in `opencode.jsonc`): `context7` (library docs lookup) and `openwork-ui` (OpenWork app bridge — keep enabled).
- Plugins: `opencode-chrome-devtools` (root), `graphify` (project-scope, `.opencode/opencode.json`).
- Default agent: `openwork` — defined at `.opencode/agents/openwork.md`. Do not delete that file.
- A prebuilt knowledge graph may exist at `graphify-out/`. If it does, the `graphify` plugin injects a reminder before bash commands — use `graphify query "..."` for focused questions instead of `grep`-ing raw files.

## Where to look first

- High-level architecture: `docs/ARCHITECTURE.md` (~900 lines, 11 sections)
- Agent reference: `docs/AGENTS.md`, `docs/AGENT_REFERENCE.md`
- Protocol: `docs/PROTOCOL_SPEC.md` (A2A + consensus)
- API surface: `docs/API_ENDPOINTS.md`
- Memory system: `docs/MEMORY_SYSTEM.md`
- Monitoring: `docs/MONITORING.md`
- OpenAPI/Redoc live at `http://localhost:8000/docs` when the API is running.
