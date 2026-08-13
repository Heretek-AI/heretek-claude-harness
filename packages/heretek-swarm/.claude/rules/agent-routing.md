# Agent Routing — Peace-History

Routing guide for subagents and skills. Avoid wrong-stack agents — every routing to a non-applicable agent wastes a retry cycle.

## Use these (project-fit)

| Surface | Primary agent | Reviewer |
|---|---|---|
| **3D globe (react-globe.gl)** | `ork:frontend-ui-developer` | `ecc:performance-optimizer` |
| **MapLibre map (781 polygons)** | `ork:frontend-ui-developer` | `ork:frontend-performance-engineer` |
| **Drizzle schema / SQLite** | `ork:database-engineer` | `ecc:database-reviewer` |
| **Fastify 5 routes** | `ork:backend-system-architect` | `ecc:code-reviewer` |
| **Next.js 15 App Router / RSC** | `ork:react-server-components-framework` | `ecc:react-reviewer` |
| **React 19 components** | `ork:frontend-ui-developer` | `ecc:react-reviewer` |
| **Zustand stores** | `ork:zustand-patterns` | `ecc:code-reviewer` |
| **AI proxy (BYOK)** | `ork:llm-integrator` | `ecc:security-reviewer` |
| **Tests (vitest 4, 551 specs)** | `superpowers:test-driven-development` | — |
| **E2E (Playwright)** | `ecc:e2e-runner` | — |
| **Build/typecheck errors** | `ecc:build-error-resolver` | — |
| **Accessibility** | `ecc:a11y-architect` | — |
| **DB query perf** | `ecc:database-reviewer` | — |
| **Codebase exploration** | `Explore` (built-in) | — |
| **Deep architecture analysis** | `ecc:code-explorer` or `feature-dev:code-explorer` | — |

## Always-on review gates

- After every non-trivial Write: `ecc:code-reviewer`
- After error-handling code: `ecc:silent-failure-hunter`
- Before PR: `pr-review-toolkit:code-reviewer`
- Before commit: `ork:commit`

## Do NOT use (wrong stack)

These agents target languages/frameworks Peace-History does **not** use. Do not route to them.

- **Wrong language agents**: `cpp-*`, `kotlin-*`, `go-*`, `django-*`, `fastapi-*` (note: not Fastify), `fsharp-*`, `csharp-*`, `harmonyos-*`, `dart-*`, `flutter-*`, `rust-*`, `java-*`, `php-*`, `python-*`, `pytorch-*`
- **Domain-specific (no project fit)**: `healthcare-*`, `homelab-*`, `network-*`
- **Generic marketing/PRM tools**: `marketing-agent`, `chief-of-staff`, `market-intelligence`, `product-strategist`
- **Cloud providers not in stack**: `infrastructure-architect` (no AWS/GCP), `monitoring-engineer` (no Prometheus), `ci-cd-engineer` (no GitHub Actions yet)
- **No production LLM exposure yet**: `ai-safety-auditor`, `security-layer-auditor`
- **Specialty toolchains**: `mle-reviewer`, `ml-adoption-playbook`

## Antipatterns (enforced via .claude/rules/antipatterns.md)

- offset pagination → cursor-based
- manual JWT → PyJWT / jsonwebtoken
- plaintext passwords → bcrypt / argon2 / scrypt
- global state → DI
- sync file I/O → async
- n+1 queries → eager load / batch
- polling for real-time → SSE / WebSocket

## Output style

`caveman` is active globally. Drop articles/filler/pleasantries/hedging. Code/commits/security warnings stay normal.