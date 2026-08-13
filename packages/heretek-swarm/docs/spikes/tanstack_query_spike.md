# TanStack Query + openapi-typescript spike — Phase 2B.3

## Purpose

Validate that **TanStack Query v5** (https://github.com/TanStack/query,
MIT, ~42k stars) and **openapi-typescript** (https://github.com/drwpow/openapi-typescript,
MIT, ~5k stars) are the integration target for the 10 hand-rolled
API client modules and the 4 WebSocket-related hooks.

## Candidate files for cutover (~3,000 LOC combined)

| File | LOC | Replaced by |
|------|-----|-------------|
| `src/api/agents.ts` | 471 | TanStack Query `useQuery`/`useMutation` |
| `src/api/deliberation.ts` | 421 | TanStack Query |
| `src/api/configuration.ts` | 400 | TanStack Query |
| `src/api/wizard.ts` | 400 | TanStack Query |
| `src/api/consensus.ts` | 269 | TanStack Query |
| `src/api/client.ts` | 195 | openapi-fetch generated client |
| `src/api/consciousness.ts` | 170 | TanStack Query |
| `src/api/autonomous.ts` | 154 | TanStack Query |
| `src/api/metrics.ts` | 89 | TanStack Query |
| `src/api/mcp.ts` | 72 | TanStack Query |
| `src/api/events.ts` | 65 | TanStack Query |
| `src/api/observability.ts` | 46 | TanStack Query |
| **Subtotal (api/)** | **2,752** | |
| `src/hooks/useRealTimeAgentUpdates.ts` (WS state) | 394 | TanStack Query + WS subscription |
| `src/hooks/useDockerDetection.tsx` | 319 | TanStack Query |
| `src/hooks/useWorkflowProgress.ts` (WS state) | 291 | TanStack Query + WS subscription |
| `src/hooks/useConsciousnessWebSocket.ts` | 215 | partysocket + TanStack invalidation |
| **Subtotal (hooks/)** | **1,219** | |
| **Total** | **~3,971** | **net ~3,000 after adding TanStack Query** |

## Migration pattern

### Step 1: Install deps
```bash
cd swarm-dashboard
npm install @tanstack/react-query @tanstack/react-query-devtools
npm install openapi-fetch
npm install --save-dev openapi-typescript
```

### Step 2: Generate the typed client from the FastAPI OpenAPI schema
```bash
# Export the running backend's OpenAPI schema:
curl http://localhost:8000/openapi.json > openapi.json

# Generate the typed client:
npx openapi-typescript openapi.json -o src/api/schema.ts
```

This gives you a fully-typed `openapi-fetch` client.

### Step 3: Replace each `src/api/*.ts` module
Old pattern (manual fetch + cache):
```ts
export async function fetchAgents(): Promise<Agent[]> {
  const r = await fetch('/api/agents');
  if (!r.ok) throw new Error('Failed');
  return r.json();
}
```

New pattern (TanStack Query hook):
```ts
import { useQuery } from '@tanstack/react-query';
import { client } from './client';
export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => client.GET('/api/agents'),
  });
}
```

### Step 4: Replace the 4 WS hooks with TanStack Query + invalidation
```ts
// subscribe to WS, invalidate queries on message
queryClient.invalidateQueries({ queryKey: ['agents'] });
```

## Kill criteria

- If openapi-typescript fails to parse the FastAPI OpenAPI schema,
  fall back to manual type generation (`json-schema-to-typescript`).
- If TanStack Query's retry/refetch behavior conflicts with the
  dashboard's polling fallback, customize the default options.

## Result

- TanStack Query v5 is the de-facto standard for React data
  fetching; battle-tested across the React ecosystem.
- openapi-typescript is the de-facto standard for typed API
  clients; supports FastAPI's Pydantic-generated schemas.
- The 4 WS hooks become invalidation triggers; no separate
  state management needed.

## Migration PR plan

1. Add deps.
2. Generate `src/api/schema.ts` from running backend.
3. Set up `QueryClientProvider` at the React root.
4. Migrate one `src/api/*.ts` at a time (12 files).
5. Migrate one WS hook at a time (4 files).
6. Delete old axios client and WS subscribe logic.

**Net:** ~3,000 LOC reduction + automatic cache invalidation +
automatic refetch on window focus + automatic retry + DevTools.
