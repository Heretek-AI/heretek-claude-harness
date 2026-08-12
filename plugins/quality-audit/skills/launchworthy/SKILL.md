---
name: launchworthy
description: Audit AI-generated codebases across 5 production readiness domains (Auth, Data, Frontend, Infra, Ops) before deployment.
---

# launchworthy

Rigorous production-readiness audit skill inspired by Wunderlandmedia/launchworthy.

## The 5 Audit Domains

Audit target project across these 5 domains:

1. **Auth & Security**:
   - Are API keys/secrets exposed in client bundles or public git files?
   - Is Row-Level Security (RLS) or authorization check enforced on every database query?
   - Are CORS origins restricted to allowed production domains?
2. **Backend & Data**:
   - Are database queries indexed and protected against SQL injection?
   - Is connection pooling configured to prevent DB starvation?
   - Are rate-limiting headers and middleware active on public endpoints?
3. **Frontend & UX**:
   - Are loading states, error boundaries, and fallback UI present?
   - Is the application accessible (WCAG AA color contrast, ARIA labels, keyboard nav)?
   - Are responsive layouts dynamic without horizontal scroll overflow?
4. **Infrastructure & Environment**:
   - Are environment variables validated at startup (e.g. via Zod or Pydantic)?
   - Is HTTPS enforced and headers configured (`HSTS`, `Content-Security-Policy`)?
5. **Operations & Observability**:
   - Is structured JSON logging enabled?
   - Are health-check endpoints (`/healthz`, `/livez`) responding cleanly?

## Verification Evidence Protocol

Demand empirical proof (DevTools network responses, CLI tool output, curl output) before marking any check as passed. Reject rationalizations like "It's just an MVP".
