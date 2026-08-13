---
applyTo: "**/*.py"
---

# Python Development Guidelines for Heretek Swarm

## Type Hints
- ALL public functions and methods MUST have type hints
- Use `from __future__ import annotations` for forward references
- Prefer `pathlib.Path` over `os.path`
- Use `collections.abc` for abstract types (e.g., `Sequence`, `Mapping`)

## Async/Await
- All I/O-bound operations MUST use `async/await`
- Use `httpx.AsyncClient` for HTTP requests
- Use `asyncpg` for PostgreSQL queries
- Never use `time.sleep()` — use `asyncio.sleep()` instead

## Error Handling
- Never use bare `except:` — always specify exception types
- Use `tenacity` for retry logic with exponential backoff
- Log errors with `structlog` — never `print()`
- Circuit breakers required for external service calls

## Security
- Validate ALL inputs in agent message handlers
- Never use `eval()`, `exec()`, or `__import__()` dynamically
- Sanitize file paths with `pathlib.Path.resolve()` and whitelist checking
- API keys via `Authorization: Bearer` header only
- Secrets in `secrets/encrypted.env` with SOPS — never plaintext

## Testing
- Every new module needs tests in `tests/`
- Use `pytest.mark.unit` for fast isolated tests
- Use `pytest.mark.integration` for tests requiring services
- Mock external dependencies — never call real APIs in unit tests
