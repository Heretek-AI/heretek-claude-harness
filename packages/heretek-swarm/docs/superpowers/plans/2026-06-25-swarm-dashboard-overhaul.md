# Swarm Dashboard Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify routing, consolidate API clients, remove legacy deliberation system, expand test coverage to 80%, and remove duplicate dependencies in the swarm-dashboard.

**Architecture:** React 19 + TypeScript 6 + Vite 8 + Tailwind 4 + Zustand 5 frontend. The overhaul replaces the dual routing system (useState view switcher + pathname routing) with unified react-router-dom Routes, consolidates 5 rogue API modules to use the centralized client, removes legacy deliberation code, adds unit tests for stores/components, adds Playwright E2E tests, and removes the duplicate reactflow dependency.

**Tech Stack:** React 19, react-router-dom 6, Zustand 5, TypeScript 6, Vite 8, vitest 4, @testing-library/react 16, Playwright, Tailwind 4

## Global Constraints

- Working directory: `swarm-dashboard/`
- TypeScript strict mode enabled
- vitest with globals: true, jsdom environment
- React 19, react-router-dom 6
- No new features — refactor and test only
- All existing tests (265) must continue passing
- E2E tests use Playwright (already in devDependencies)

---

## Task 1: Remove Legacy Deliberation System

**Files:**
- Delete: `swarm-dashboard/src/api/deliberation.ts`
- Delete: `swarm-dashboard/src/components/Deliberation/DeliberationPage.tsx`
- Delete: `swarm-dashboard/src/components/Deliberation/LiveDeliberationPanel.tsx`
- Delete: `swarm-dashboard/src/components/Deliberation/HistoricalDeliberations.tsx`
- Delete: `swarm-dashboard/src/components/Home/HomePage.tsx`
- Delete: `swarm-dashboard/src/components/Deliberation/__tests__/DeliberationPage.test.tsx`
- Modify: `swarm-dashboard/src/App.tsx` — remove imports of deleted files

**Interfaces:**
- Consumes: none
- Produces: cleaned App.tsx with no references to deleted files

- [ ] **Step 1: Find all imports of legacy files**

```bash
cd swarm-dashboard && grep -rn "from.*components/Deliberation/DeliberationPage\|from.*components/Deliberation/LiveDeliberationPanel\|from.*components/Deliberation/HistoricalDeliberations\|from.*components/Home/HomePage\|from.*api/deliberation" src/
```

Expected: imports in `App.tsx` line 35 (`DeliberationPage`) and line 32 (`HomePage`).

- [ ] **Step 2: Remove imports from App.tsx**

Open `swarm-dashboard/src/App.tsx`. Remove these lines:
- Line 32: `import { HomePage } from './components/Home/HomePage';`
- Line 35: `import { DeliberationPage } from './components/Deliberation/DeliberationPage';`

- [ ] **Step 3: Remove legacy components from renderView**

In `swarm-dashboard/src/App.tsx`, the `renderView()` switch statement at lines 217-249 references `HomePage` (case 'home') and `DeliberationPage` (case 'deliberation'). Remove both cases:

```typescript
// Remove these cases from the switch:
case 'home':
  return <HomePage />;      // REMOVE — HomePage is now in pages/home-page.tsx via Routes
case 'deliberation':
  return <DeliberationPage />;  // REMOVE — DeliberationPage is now in pages/deliberation-page.tsx via Routes
```

The default case should now fall through to `null` or render the NewHomePage:

```typescript
default:
  return <NewHomePage />;
```

- [ ] **Step 4: Delete legacy files**

```bash
cd swarm-dashboard
rm src/api/deliberation.ts
rm src/components/Deliberation/DeliberationPage.tsx
rm src/components/Deliberation/LiveDeliberationPanel.tsx
rm src/components/Deliberation/HistoricalDeliberations.tsx
rm src/components/Home/HomePage.tsx
rm src/components/Deliberation/__tests__/DeliberationPage.test.tsx
```

- [ ] **Step 5: Run existing tests**

```bash
cd swarm-dashboard && npm test
```

Expected: All 265 tests pass (the deleted test file was part of the 265 — count should drop to ~250).

- [ ] **Step 6: Commit**

```bash
cd swarm-dashboard && git add -A && git commit -m "refactor: remove legacy deliberation system (DeliberationPage, LiveDeliberationPanel, HistoricalDeliberations, legacy HomePage)"
```

---

## Task 2: Unify Routing in App.tsx

**Files:**
- Modify: `swarm-dashboard/src/App.tsx`

**Interfaces:**
- Consumes: Task 1 (legacy files removed)
- Produces: App.tsx with unified react-router-dom Routes, no view switcher

- [ ] **Step 1: Rewrite App.tsx routing**

Replace the entire `DashboardContent` component in `swarm-dashboard/src/App.tsx` with a version that uses `<Routes>` instead of the useState view switcher. Here is the complete replacement for lines 83-302:

```tsx
function DashboardContent() {
  const [systemStatus, setSystemStatus] = useState<'healthy' | 'degraded' | 'offline'>('healthy');
  const toast = useToast();

  // Setup store integration
  const { config, setRerunning, resetSetup } = useSetupStore();

  const [showSetup, setShowSetup] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  // Check if setup is needed on mount
  useEffect(() => {
    const checkConfiguration = () => {
      const storedConfigured = localStorage.getItem('swarm_configured') === 'true';
      const storedApiHost = localStorage.getItem('swarm_api_host');

      const envApiKey = import.meta.env.VITE_API_KEY;
      const envApiHost = import.meta.env.VITE_API_HOST;

      if (!storedConfigured || !storedApiHost) {
        if (envApiKey && envApiHost) {
          localStorage.setItem('swarm_api_host', envApiHost);
          localStorage.setItem('swarm_configured', 'true');
          useSetupStore.getState().setConfig({
            apiHost: envApiHost,
            apiKey: envApiKey,
            wsHost: '',
          });
          setShowSetup(false);
        } else {
          setShowSetup(true);
        }
      } else {
        if (!config.apiHost) {
          useSetupStore.getState().setConfig({
            apiHost: storedApiHost,
            apiKey: '',
            wsHost: localStorage.getItem('swarm_ws_host') || '',
          });
        }
        setShowSetup(false);
      }
      setIsInitialized(true);
    };

    checkConfiguration();
  }, []);

  // Set toast instance for API client
  useEffect(() => {
    setToastInstance({
      error: (title, message) => toast.error(title, message),
    });
  }, [toast]);

  // Check system health periodically
  const checkSystemHealth = useCallback(async () => {
    try {
      const apiHost = _safeUrl(
        localStorage.getItem('swarm_api_host') || import.meta.env.VITE_API_HOST || '',
      );
      if (!apiHost) {
        setSystemStatus('offline');
        return;
      }

      const response = await fetch(`${apiHost}/api/health`);
      if (!response.ok) {
        setSystemStatus('offline');
        return;
      }
      const data = await response.json();

      if (data.status === 'healthy') {
        setSystemStatus('healthy');
        return;
      }

      const svc = data.services || {};
      const anyServiceHealthy =
        svc.gateway?.status === 'healthy' ||
        svc.redis?.status === 'healthy' ||
        svc.postgres?.status === 'healthy' ||
        svc.qdrant?.status === 'healthy';

      setSystemStatus(anyServiceHealthy ? 'degraded' : 'offline');
    } catch {
      setSystemStatus('offline');
    }
  }, []);

  useEffect(() => {
    if (!showSetup && isInitialized) {
      checkSystemHealth();
      const interval = setInterval(checkSystemHealth, 30000);
      return () => clearInterval(interval);
    }
  }, [checkSystemHealth, showSetup, isInitialized]);

  const handleSetupComplete = useCallback(() => {
    setShowSetup(false);
    setTimeout(checkSystemHealth, 1000);
  }, [checkSystemHealth]);

  const handleRerunSetup = useCallback(() => {
    resetSetup();
    setRerunning(true);
    setShowSetup(true);
  }, [resetSetup, setRerunning]);

  // Don't render until we've checked configuration
  if (!isInitialized) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      {showSetup ? (
        <SetupWizard onComplete={handleSetupComplete} />
      ) : (
        <Routes>
          <Route element={<DashboardLayoutWrapper systemStatus={systemStatus} onRerunSetup={handleRerunSetup} />}>
            {/* Tier-1 routes */}
            <Route path="/" element={<NewHomePage />} />
            <Route path="/deliberations" element={<NewDeliberationListPage />} />
            <Route path="/deliberations/:id" element={<NewDeliberationPage />} />

            {/* Legacy routes */}
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/consciousness" element={<ConsciousnessPage />} />
            <Route path="/autonomous" element={<AutonomousPage />} />
            <Route path="/observability" element={<ObservabilityPage />} />
            <Route path="/chat" element={<MessageList />} />
            <Route path="/canvas" element={<EnhancedCanvas />} />
            <Route path="/workflows" element={<WorkflowBuilder />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/settings" element={<SettingsPage onRerunSetup={handleRerunSetup} />} />
          </Route>
        </Routes>
      )}
      <CommandPalette
        items={navItems.map<CommandItem>((item) => ({
          id: `nav:${item.id}`,
          label: item.label,
          group: 'Page',
          icon: item.icon,
          keywords: ['navigate', 'go to', item.id],
        }))}
      />
    </>
  );
}
```

- [ ] **Step 2: Create DashboardLayoutWrapper**

The `DashboardLayout` currently takes `activeNav` and `onNavClick` props for the view switcher. Since routes now drive navigation, we need a wrapper that reads the current route and passes it to the layout. Add this helper function before `DashboardContent`:

```tsx
function DashboardLayoutWrapper({ systemStatus, onRerunSetup }: { systemStatus: 'healthy' | 'degraded' | 'offline'; onRerunSetup: () => void }) {
  const location = useLocation();
  const navigate = useNavigate();

  // Map pathname to nav ID
  const pathToNav: Record<string, string> = {
    '/': 'home',
    '/agents': 'agents',
    '/consciousness': 'consciousness',
    '/deliberation': 'deliberation',
    '/autonomous': 'autonomous',
    '/observability': 'observability',
    '/chat': 'chat',
    '/canvas': 'canvas',
    '/workflows': 'workflows',
    '/logs': 'logs',
    '/settings': 'settings',
  };

  const activeNav = pathToNav[location.pathname] || 'home';

  const handleNavClick = useCallback((navId: string) => {
    const path = Object.entries(pathToNav).find(([, id]) => id === navId)?.[0] || '/';
    navigate(path);
  }, [navigate]);

  return (
    <DashboardLayout
      activeNav={activeNav}
      onNavClick={handleNavClick}
      navItems={navItems}
      systemStatus={systemStatus}
    >
      <ErrorBoundary>
        <Outlet />
      </ErrorBoundary>
    </DashboardLayout>
  );
}
```

- [ ] **Step 3: Add Outlet import**

Add `Outlet` to the react-router-dom import at line 15:

```tsx
import { MemoryRouter, Routes, Route, useNavigate, useLocation, Outlet } from 'react-router-dom';
```

Remove the `Navigate` import (no longer needed).

- [ ] **Step 4: Run tests**

```bash
cd swarm-dashboard && npm test
```

Expected: All tests pass. The routing change is internal — existing tests mock API calls, not routing.

- [ ] **Step 5: Verify TypeScript compilation**

```bash
cd swarm-dashboard && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 6: Commit**

```bash
cd swarm-dashboard && git add src/App.tsx && git commit -m "refactor: unify routing with react-router-dom Routes, remove view switcher"
```

---

## Task 3: Consolidate API Clients

**Files:**
- Modify: `swarm-dashboard/src/api/agents.ts`
- Modify: `swarm-dashboard/src/api/consciousness.ts`
- Modify: `swarm-dashboard/src/api/autonomous.ts`
- Modify: `swarm-dashboard/src/api/deliberations.ts`
- Modify: `swarm-dashboard/src/api/wizard.ts`

**Interfaces:**
- Consumes: `swarm-dashboard/src/api/client.ts` (exports `api` helper object with get/post/put/patch/delete methods)
- Produces: All 5 modules use `api` from `./client` instead of their own axios/fetch instances

- [ ] **Step 1: Refactor agents.ts**

Open `swarm-dashboard/src/api/agents.ts`. Replace lines 1-24 (the axios setup) with:

```typescript
/**
 * API Client - Agent Management endpoints
 */

import { api } from './client';
```

Remove lines 1-24 entirely (the local axios instance, API_URL, and interceptor). Keep all type exports and function implementations unchanged — they already use `api.get(...)` etc.

- [ ] **Step 2: Refactor consciousness.ts**

Open `swarm-dashboard/src/api/consciousness.ts`. Replace lines 1-24 (the axios setup) with:

```typescript
/**
 * API Client - Consciousness metrics endpoints
 */

import { api } from './client';
```

Remove lines 1-24 entirely. Keep all type exports and function implementations unchanged.

- [ ] **Step 3: Refactor autonomous.ts**

Open `swarm-dashboard/src/api/autonomous.ts`. Replace lines 1-23 (the axios setup) with:

```typescript
/**
 * API Client - Autonomous runtime endpoints
 */

import { api } from './client';
```

Remove lines 1-23 entirely. Keep all type exports and function implementations unchanged.

- [ ] **Step 4: Refactor deliberations.ts**

Open `swarm-dashboard/src/api/deliberations.ts`. Replace the entire file with:

```typescript
// REST client for /api/deliberations.
import { api } from './client';
import type { DeliberationDetail, DeliberationSummary } from '../types/deliberation';

export async function createDeliberation(problem: string): Promise<string> {
  const r = await api.post<{ id: string; status: string }>('/api/deliberations', { problem });
  return r.data.id;
}

export async function getDeliberation(id: string): Promise<DeliberationDetail> {
  const r = await api.get<DeliberationDetail>(`/api/deliberations/${id}`);
  return r.data;
}

export async function listDeliberations(limit = 20): Promise<DeliberationSummary[]> {
  const r = await api.get<{ items: DeliberationSummary[] }>(`/api/deliberations?limit=${limit}`);
  return r.data.items;
}

export async function interject(id: string, text: string): Promise<void> {
  await api.post(`/api/deliberations/${id}/interject`, { text });
}
```

Note: The old version used `axios.create({ baseURL: '/api' })` with no auth. The new version uses the centralized `api` from client.ts which has auth and retry logic.

- [ ] **Step 5: Refactor wizard.ts**

Open `swarm-dashboard/src/api/wizard.ts`. Replace lines 168-195 (the `fetchJson` helper and `API_URL`) with:

```typescript
import apiClient from './client';

async function fetchJson<T>(url: string, options?: { method?: string; body?: unknown }): Promise<T> {
  const method = options?.method || 'GET';

  let response;
  if (method === 'GET') {
    response = await apiClient.get<T>(url);
  } else if (method === 'POST') {
    response = await apiClient.post<T>(url, options?.body);
  } else if (method === 'PUT') {
    response = await apiClient.put<T>(url, options?.body);
  } else if (method === 'DELETE') {
    response = await apiClient.delete<T>(url);
  } else {
    throw new Error(`Unsupported method: ${method}`);
  }

  return response.data;
}
```

Wait — the existing `fetchJson` calls pass `options` as `RequestInit` (with `method` and `body` as JSON string). We need to keep compatibility. The cleanest approach:

```typescript
import apiClient from './client';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const method = (options?.method || 'GET') as string;
  const body = options?.body ? JSON.parse(options.body as string) : undefined;

  const response = await apiClient.request<T>({
    method,
    url,
    data: body,
  });

  return response.data;
}
```

This works because `apiClient.request` accepts the same config shape as axios. The `URLSearchParams` in `validateCredentials` will need to be handled — but looking at the code, it passes params as a query string in the URL, which axios handles fine.

- [ ] **Step 6: Run tests**

```bash
cd swarm-dashboard && npm test
```

Expected: All tests pass.

- [ ] **Step 7: Verify TypeScript**

```bash
cd swarm-dashboard && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 8: Commit**

```bash
cd swarm-dashboard && git add src/api/agents.ts src/api/consciousness.ts src/api/autonomous.ts src/api/deliberations.ts src/api/wizard.ts && git commit -m "refactor: consolidate API clients to use centralized client.ts"
```

---

## Task 4: Remove Duplicate reactflow Dependency

**Files:**
- Modify: `swarm-dashboard/package.json`
- Scan: `swarm-dashboard/src/` for any `from 'reactflow'` imports

**Interfaces:**
- Consumes: none
- Produces: single `@xyflow/react` dependency, no `reactflow`

- [ ] **Step 1: Find any reactflow imports**

```bash
cd swarm-dashboard && grep -rn "from 'reactflow'" src/
```

Expected: No results (canvasStore already uses `@xyflow/react`). If any are found, replace with `@xyflow/react`.

- [ ] **Step 2: Remove reactflow from package.json**

Open `swarm-dashboard/package.json`. Remove this line from `dependencies`:

```json
"reactflow": "^11.10.0",
```

- [ ] **Step 3: Reinstall dependencies**

```bash
cd swarm-dashboard && npm install
```

- [ ] **Step 4: Run tests**

```bash
cd swarm-dashboard && npm test
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd swarm-dashboard && git add package.json package-lock.json && git commit -m "chore: remove duplicate reactflow dependency, keep @xyflow/react only"
```

---

## Task 5: Add Store Tests

**Files:**
- Create: `swarm-dashboard/tests/stores/canvasStore.test.ts`
- Create: `swarm-dashboard/tests/stores/deliberation-store.test.ts`
- Create: `swarm-dashboard/tests/stores/metricsStore.test.ts`
- Create: `swarm-dashboard/tests/stores/setupStore.test.ts`

**Interfaces:**
- Consumes: `swarm-dashboard/src/stores/canvasStore.ts`, `swarm-dashboard/src/stores/deliberation-store.ts`, `swarm-dashboard/src/stores/metricsStore.ts`, `swarm-dashboard/src/stores/setupStore.ts`
- Produces: 4 test files covering all store actions

- [ ] **Step 1: Create tests/stores directory**

```bash
mkdir -p swarm-dashboard/tests/stores
```

- [ ] **Step 2: Write canvasStore test**

Create `swarm-dashboard/tests/stores/canvasStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useCanvasStore } from '../../src/stores/canvasStore';

describe('canvasStore', () => {
  beforeEach(() => {
    useCanvasStore.setState({
      nodes: [],
      edges: [],
      selectedNode: null,
      selectedEdge: null,
      isExecuting: false,
      executionProgress: 0,
      loading: false,
      error: null,
    });
  });

  it('adds a node', () => {
    const { addNode } = useCanvasStore.getState();
    addNode({ id: 'agent-1', type: 'agentNode', position: { x: 0, y: 0 }, data: { agentId: 'a1', agentType: 'alpha', status: 'idle', consciousnessMetrics: null, lastActivity: null, messageCount: 0 } });
    expect(useCanvasStore.getState().nodes).toHaveLength(1);
    expect(useCanvasStore.getState().nodes[0].id).toBe('agent-1');
  });

  it('removes a node', () => {
    const { addNode, removeNode } = useCanvasStore.getState();
    addNode({ id: 'agent-1', type: 'agentNode', position: { x: 0, y: 0 }, data: { agentId: 'a1', agentType: 'alpha', status: 'idle', consciousnessMetrics: null, lastActivity: null, messageCount: 0 } });
    removeNode('agent-1');
    expect(useCanvasStore.getState().nodes).toHaveLength(0);
  });

  it('sets selected node', () => {
    const { addNode, setSelectedNode } = useCanvasStore.getState();
    addNode({ id: 'agent-1', type: 'agentNode', position: { x: 0, y: 0 }, data: { agentId: 'a1', agentType: 'alpha', status: 'idle', consciousnessMetrics: null, lastActivity: null, messageCount: 0 } });
    setSelectedNode('agent-1');
    expect(useCanvasStore.getState().selectedNode).toBe('agent-1');
  });

  it('updates node metrics', () => {
    const { addNode, updateNodeMetrics } = useCanvasStore.getState();
    addNode({ id: 'agent-1', type: 'agentNode', position: { x: 0, y: 0 }, data: { agentId: 'a1', agentType: 'alpha', status: 'idle', consciousnessMetrics: null, lastActivity: null, messageCount: 0 } });
    updateNodeMetrics('agent-1', { gwt_score: 0.9, phi_value: 0.8, ast_competence: 0.7, free_energy: 0.6 });
    const node = useCanvasStore.getState().nodes.find(n => n.id === 'agent-1');
    expect(node?.data.consciousnessMetrics).toEqual({ gwt_score: 0.9, phi_value: 0.8, ast_competence: 0.7, free_energy: 0.6 });
  });

  it('sets executing state', () => {
    const { setExecuting } = useCanvasStore.getState();
    setExecuting(true);
    expect(useCanvasStore.getState().isExecuting).toBe(true);
    setExecuting(false);
    expect(useCanvasStore.getState().isExecuting).toBe(false);
  });

  it('sets loading and error', () => {
    const { setLoading, setError } = useCanvasStore.getState();
    setLoading(true);
    expect(useCanvasStore.getState().loading).toBe(true);
    setError('test error');
    expect(useCanvasStore.getState().error).toBe('test error');
  });
});
```

- [ ] **Step 3: Write deliberation-store test**

Create `swarm-dashboard/tests/stores/deliberation-store.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useDeliberationStore } from '../../src/stores/deliberation-store';
import type { DeliberationEvent } from '../../src/types/deliberation';

describe('deliberationStore', () => {
  beforeEach(() => {
    useDeliberationStore.getState().reset('test-id', 'test problem');
  });

  it('resets to initial state', () => {
    const state = useDeliberationStore.getState();
    expect(state.id).toBe('test-id');
    expect(state.problem).toBe('test problem');
    expect(state.status).toBe('pending');
    expect(state.events).toEqual([]);
    expect(state.finalVerdict).toBeNull();
  });

  it('hydrates from detail', () => {
    const { hydrate } = useDeliberationStore.getState();
    hydrate({
      id: 'test-id',
      problem: 'test problem',
      status: 'running',
      events: [],
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    } as any);
    expect(useDeliberationStore.getState().status).toBe('running');
  });

  it('applies a verdict event', () => {
    const { applyEvent } = useDeliberationStore.getState();
    const event: DeliberationEvent = {
      kind: 'verdict',
      agent: 'alpha',
      content: JSON.stringify({ position: 'approve', confidence: 0.9, concerns: [], reasoning: 'Looks good' }),
      timestamp: '2025-01-01T00:00:00Z',
    };
    applyEvent(event);
    expect(useDeliberationStore.getState().events).toHaveLength(1);
    expect(useDeliberationStore.getState().events[0].kind).toBe('verdict');
  });

  it('applies a reasoning event', () => {
    const { applyEvent } = useDeliberationStore.getState();
    const event: DeliberationEvent = {
      kind: 'reasoning',
      agent: 'alpha',
      content: 'Analyzing the problem...',
      timestamp: '2025-01-01T00:00:00Z',
    };
    applyEvent(event);
    expect(useDeliberationStore.getState().reasoningByAgent.alpha).toBe('Analyzing the problem...');
  });

  it('sets active agent', () => {
    const { setActiveAgent } = useDeliberationStore.getState();
    setActiveAgent('beta');
    expect(useDeliberationStore.getState().activeAgent).toBe('beta');
  });

  it('sets replay done', () => {
    const { setReplayDone } = useDeliberationStore.getState();
    setReplayDone(5);
    expect(useDeliberationStore.getState().replayDone).toBe(true);
  });

  it('sets error', () => {
    const { setError } = useDeliberationStore.getState();
    setError('something went wrong');
    expect(useDeliberationStore.getState().error).toBe('something went wrong');
  });
});
```

- [ ] **Step 4: Write metricsStore test**

Create `swarm-dashboard/tests/stores/metricsStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useMetricsStore } from '../../src/stores/metricsStore';

describe('metricsStore', () => {
  beforeEach(() => {
    useMetricsStore.getState().reset();
  });

  it('sets collective metrics', () => {
    const { setCollectiveMetrics } = useMetricsStore.getState();
    setCollectiveMetrics({
      average_gwt_score: 0.8,
      average_phi: 0.7,
      average_ast: 0.6,
      average_free_energy: 0.5,
      agent_count: 10,
      timestamp: '2025-01-01T00:00:00Z',
    });
    expect(useMetricsStore.getState().collectiveMetrics).not.toBeNull();
    expect(useMetricsStore.getState().collectiveMetrics!.agent_count).toBe(10);
  });

  it('sets agent metrics', () => {
    const { setAgentMetrics } = useMetricsStore.getState();
    setAgentMetrics('agent-1', {
      agent_id: 'agent-1',
      gwt_score: 0.9,
      phi_value: 0.8,
      ast_competence: 0.7,
      free_energy: 0.6,
      state: 'coherent',
    });
    expect(useMetricsStore.getState().agentMetrics['agent-1']).toBeDefined();
    expect(useMetricsStore.getState().agentMetrics['agent-1'].gwt_score).toBe(0.9);
  });

  it('sets agent states', () => {
    const { setAgentStates } = useMetricsStore.getState();
    setAgentStates({
      counts: { coherent: 5, dormant: 3 },
      states: { 'agent-1': 'coherent', 'agent-2': 'dormant' },
    });
    expect(useMetricsStore.getState().agentStates.counts.coherent).toBe(5);
  });

  it('resets state', () => {
    const { setCollectiveMetrics, reset } = useMetricsStore.getState();
    setCollectiveMetrics({
      average_gwt_score: 0.8,
      average_phi: 0.7,
      average_ast: 0.6,
      average_free_energy: 0.5,
      agent_count: 10,
      timestamp: '2025-01-01T00:00:00Z',
    });
    reset();
    expect(useMetricsStore.getState().collectiveMetrics).toBeNull();
  });
});
```

- [ ] **Step 5: Write setupStore test**

Create `swarm-dashboard/tests/stores/setupStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useSetupStore } from '../../src/stores/setupStore';

describe('setupStore', () => {
  beforeEach(() => {
    useSetupStore.getState().resetSetup();
  });

  it('sets config', () => {
    const { setConfig } = useSetupStore.getState();
    setConfig({ apiHost: 'http://localhost:8000', apiKey: 'test-key', wsHost: 'ws://localhost:8000' });
    expect(useSetupStore.getState().config.apiHost).toBe('http://localhost:8000');
    expect(useSetupStore.getState().config.apiKey).toBe('test-key');
  });

  it('sets current step', () => {
    const { setStep } = useSetupStore.getState();
    setStep('api-key');
    expect(useSetupStore.getState().currentStep).toBe('api-key');
  });

  it('sets rerunning', () => {
    const { setRerunning } = useSetupStore.getState();
    setRerunning(true);
    expect(useSetupStore.getState().isRerunning).toBe(true);
  });

  it('resets setup', () => {
    const { setConfig, resetSetup } = useSetupStore.getState();
    setConfig({ apiHost: 'http://localhost:8000', apiKey: 'test-key', wsHost: '' });
    resetSetup();
    expect(useSetupStore.getState().config.apiHost).toBe('');
    expect(useSetupStore.getState().currentStep).toBe('welcome');
  });
});
```

- [ ] **Step 6: Run store tests**

```bash
cd swarm-dashboard && npx vitest run tests/stores/
```

Expected: All 4 test files pass (~20 tests).

- [ ] **Step 7: Commit**

```bash
cd swarm-dashboard && git add tests/stores/ && git commit -m "test: add unit tests for canvasStore, deliberation-store, metricsStore, setupStore"
```

---

## Task 6: Add Component Tests (Agents, Chat, Canvas, Settings)

**Files:**
- Create: `swarm-dashboard/tests/components/AgentsPage.test.tsx`
- Create: `swarm-dashboard/tests/components/AgentChat.test.tsx`
- Create: `swarm-dashboard/tests/components/EnhancedCanvas.test.tsx`
- Create: `swarm-dashboard/tests/components/SettingsPage.test.tsx`

**Interfaces:**
- Consumes: Components from `swarm-dashboard/src/components/`
- Produces: 4 test files covering key untested components

- [ ] **Step 1: Create tests/components directory**

```bash
mkdir -p swarm-dashboard/tests/components
```

- [ ] **Step 2: Write AgentsPage test**

Create `swarm-dashboard/tests/components/AgentsPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AgentsPage } from '../../src/components/Agents/AgentsPage';

vi.mock('../../src/api/agents', () => ({
  getAgents: vi.fn(),
  getAgentInstances: vi.fn(),
}));

import { getAgents, getAgentInstances } from '../../src/api/agents';

describe('AgentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    (getAgents as any).mockReturnValue(new Promise(() => {})); // never resolves
    (getAgentInstances as any).mockReturnValue(new Promise(() => {}));
    render(<AgentsPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders agents list when data loads', async () => {
    (getAgents as any).mockResolvedValue({ agents: [{ id: 'agent-1', type: 'alpha', status: 'running' }], total: 1 });
    (getAgentInstances as any).mockResolvedValue({ instances: [], total: 0 });
    render(<AgentsPage />);
    await waitFor(() => {
      expect(screen.getByText(/agent-1/i)).toBeInTheDocument();
    });
  });

  it('renders error state on failure', async () => {
    (getAgents as any).mockRejectedValue(new Error('Network error'));
    (getAgentInstances as any).mockResolvedValue({ instances: [], total: 0 });
    render(<AgentsPage />);
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 3: Write AgentChat test**

Create `swarm-dashboard/tests/components/AgentChat.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AgentChat } from '../../src/components/Chat/AgentChat';

vi.mock('../../src/api/agents', () => ({
  getAgents: vi.fn().mockResolvedValue({ agents: [], total: 0 }),
  sendChatMessage: vi.fn(),
}));

describe('AgentChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders chat interface', () => {
    render(<AgentChat />);
    expect(screen.getByText(/chat/i)).toBeInTheDocument();
  });

  it('renders message input area', () => {
    render(<AgentChat />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Write EnhancedCanvas test**

Create `swarm-dashboard/tests/components/EnhancedCanvas.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EnhancedCanvas } from '../../src/components/Canvas/EnhancedCanvas';

vi.mock('../../src/stores/canvasStore', () => ({
  useCanvasStore: Object.assign(
    (selector: any) => selector({
      nodes: [],
      edges: [],
      selectedNode: null,
      isExecuting: false,
      loading: false,
      error: null,
      setNodes: vi.fn(),
      setEdges: vi.fn(),
    }),
    {
      getState: () => ({
        nodes: [],
        edges: [],
        selectedNode: null,
        isExecuting: false,
        loading: false,
        error: null,
        setNodes: vi.fn(),
        setEdges: vi.fn(),
      }),
    }
  ),
}));

describe('EnhancedCanvas', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders canvas container', () => {
    render(<EnhancedCanvas />);
    expect(screen.getByText(/canvas/i)).toBeInTheDocument();
  });

  it('shows empty state when no nodes', () => {
    render(<EnhancedCanvas />);
    expect(screen.getByText(/no agents/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Write SettingsPage test**

Create `swarm-dashboard/tests/components/SettingsPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SettingsPage } from '../../src/components/Settings/SettingsPage';

describe('SettingsPage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders settings page', () => {
    render(<SettingsPage onRerunSetup={() => {}} />);
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
  });

  it('saves API key to localStorage', async () => {
    render(<SettingsPage onRerunSetup={() => {}} />);
    const input = screen.getByLabelText(/api key/i);
    fireEvent.change(input, { target: { value: 'test-key-123' } });
    fireEvent.click(screen.getByText(/save/i));
    await waitFor(() => {
      expect(localStorage.getItem('api_key')).toBe('test-key-123');
    });
  });
});
```

- [ ] **Step 6: Run component tests**

```bash
cd swarm-dashboard && npx vitest run tests/components/
```

Expected: All 4 test files pass.

- [ ] **Step 7: Commit**

```bash
cd swarm-dashboard && git add tests/components/ && git commit -m "test: add component tests for AgentsPage, AgentChat, EnhancedCanvas, SettingsPage"
```

---

## Task 7: Add E2E Tests with Playwright

**Files:**
- Create: `swarm-dashboard/tests/e2e/navigation.spec.ts`
- Create: `swarm-dashboard/tests/e2e/deliberation-flow.spec.ts`
- Create: `swarm-dashboard/tests/e2e/settings.spec.ts`
- Create: `swarm-dashboard/playwright.config.ts`

**Interfaces:**
- Consumes: Running tier-1 backend at localhost:8000, frontend at localhost:3000
- Produces: 3 Playwright E2E test specs

- [ ] **Step 1: Create playwright.config.ts**

Create `swarm-dashboard/playwright.config.ts`:

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:3000',
    headless: true,
    viewport: { width: 1280, height: 720 },
  },
  webServer: {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: true,
  },
});
```

- [ ] **Step 2: Create tests/e2e directory**

```bash
mkdir -p swarm-dashboard/tests/e2e
```

- [ ] **Step 3: Write navigation E2E test**

Create `swarm-dashboard/tests/e2e/navigation.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('home page loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('body')).toBeVisible();
  });

  test('navigate to agents page', async ({ page }) => {
    await page.goto('/');
    const agentsLink = page.locator('nav a, button', { hasText: /agents/i }).first();
    if (await agentsLink.isVisible()) {
      await agentsLink.click();
      await expect(page).toHaveURL(/\/agents/);
    }
  });

  test('navigate to settings page', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('body')).toBeVisible();
  });

  test('navigate to deliberations page', async ({ page }) => {
    await page.goto('/deliberations');
    await expect(page.locator('body')).toBeVisible();
  });
});
```

- [ ] **Step 4: Write deliberation flow E2E test**

Create `swarm-dashboard/tests/e2e/deliberation-flow.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Deliberation Flow', () => {
  test('can create a new deliberation', async ({ page }) => {
    await page.goto('/');
    const textarea = page.locator('textarea');
    if (await textarea.isVisible()) {
      await textarea.fill('What is the best architecture for our system?');
      const submitBtn = page.locator('button[type="submit"], button', { hasText: /submit|create|start/i }).first();
      if (await submitBtn.isVisible()) {
        await submitBtn.click();
        await expect(page).toHaveURL(/\/deliberations\//);
      }
    }
  });

  test('deliberation list page loads', async ({ page }) => {
    await page.goto('/deliberations');
    await expect(page.locator('body')).toBeVisible();
  });
});
```

- [ ] **Step 5: Write settings E2E test**

Create `swarm-dashboard/tests/e2e/settings.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Settings', () => {
  test('settings page loads', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('body')).toBeVisible();
  });

  test('API key can be saved', async ({ page }) => {
    await page.goto('/settings');
    const apiKeyInput = page.locator('input[type="password"], input[placeholder*="api key" i]').first();
    if (await apiKeyInput.isVisible()) {
      await apiKeyInput.fill('test-api-key');
      const saveBtn = page.locator('button', { hasText: /save/i }).first();
      if (await saveBtn.isVisible()) {
        await saveBtn.click();
        const savedKey = await page.evaluate(() => localStorage.getItem('api_key'));
        expect(savedKey).toBe('test-api-key');
      }
    }
  });
});
```

- [ ] **Step 6: Verify E2E tests can be discovered**

```bash
cd swarm-dashboard && npx playwright test --list
```

Expected: Lists 3 test files with ~8 tests total.

- [ ] **Step 7: Commit**

```bash
cd swarm-dashboard && git add playwright.config.ts tests/e2e/ && git commit -m "test: add Playwright E2E tests for navigation, deliberation flow, settings"
```

---

## Task 8: Final Verification and Cleanup

**Files:**
- Modify: `swarm-dashboard/src/App.tsx` — remove unused imports if any remain

**Interfaces:**
- Consumes: All previous tasks
- Produces: Clean codebase with all tests passing

- [ ] **Step 1: Check for unused imports**

```bash
cd swarm-dashboard && npx tsc --noEmit
```

Fix any type errors found.

- [ ] **Step 2: Run full test suite**

```bash
cd swarm-dashboard && npm test
```

Expected: All unit tests pass (~280+ tests after additions).

- [ ] **Step 3: Check for any remaining references to deleted files**

```bash
cd swarm-dashboard && grep -rn "deliberation\.ts\|DeliberationPage\|LiveDeliberationPanel\|HistoricalDeliberations\|HomePage.*components" src/ --include="*.ts" --include="*.tsx" | grep -v "node_modules" | grep -v "__tests__"
```

Expected: No results referencing deleted files.

- [ ] **Step 4: Verify vitest.config.ts includes tests/stores**

The vitest config at `swarm-dashboard/vitest.config.ts` already includes `tests/stores/**/*.{test,spec}.{ts,tsx}` in its include pattern. Verify this is correct:

```bash
grep -A5 "include:" swarm-dashboard/vitest.config.ts
```

Expected: Shows `tests/stores/**/*.{test,spec}.{ts,tsx}` in the list.

- [ ] **Step 5: Final commit if any cleanup was needed**

```bash
cd swarm-dashboard && git add -A && git commit -m "chore: final cleanup and verification of dashboard overhaul" --allow-empty
```
