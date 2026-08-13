# Swarm Dashboard Overhaul — Design Spec

**Date:** 2026-06-25
**Status:** Approved (pending implementation)

## Context

The swarm-dashboard frontend (React 19 + TypeScript + Vite + Tailwind + Zustand) has 132 source files but only 17 test files (13% coverage). It was originally built for the monolith backend, and while tier-1 pages have been added, the codebase has accumulated architectural debt: dual routing, fragmented API clients, two parallel deliberation systems, duplicate dependencies, and massive test gaps.

This spec addresses all of these in one coherent overhaul.

## Goals

1. Unify routing to `react-router-dom` `<Routes>` — remove legacy view switcher
2. Consolidate API clients — all modules use centralized `client.ts`
3. Remove legacy deliberation system — clean break, tier-1 only
4. Expand test coverage to 80% — unit tests for stores/components + Playwright E2E
5. Remove duplicate `reactflow` dependency — keep `@xyflow/react` only
6. Verify tier-1 API connection — ensure proxy, types, and health checks align

## Non-goals

- New frontend features (no new pages or components)
- Redesigning the UI/UX
- Migrating to a different state management library
- Backend changes (tier1 API is assumed stable)

## Architecture

```
swarm-dashboard/
├── src/
│   ├── App.tsx                    # MODIFIED: unified Routes, no view switcher
│   ├── api/
│   │   ├── client.ts              # UNCHANGED: centralized axios instance
│   │   ├── agents.ts              # MODIFIED: use client.ts instead of local axios
│   │   ├── consciousness.ts       # MODIFIED: use client.ts
│   │   ├── autonomous.ts          # MODIFIED: use client.ts
│   │   ├── deliberations.ts       # MODIFIED: use client.ts
│   │   ├── wizard.ts              # MODIFIED: use client.ts instead of raw fetch
│   │   ├── consensus.ts           # UNCHANGED: already uses client.ts
│   │   ├── configuration.ts       # UNCHANGED
│   │   ├── events.ts              # UNCHANGED
│   │   ├── mcp.ts                 # UNCHANGED
│   │   ├── metrics.ts             # UNCHANGED
│   │   └── observability.ts       # UNCHANGED
│   ├── components/
│   │   ├── Agents/                # NEW: tests for AgentsPage, AgentCard, etc.
│   │   ├── Canvas/                # NEW: tests for EnhancedCanvas, AgentNode, etc.
│   │   ├── Chat/                  # NEW: tests for AgentChat, MessageInput, MessageList
│   │   ├── Consciousness/         # UNCHANGED (tests exist)
│   │   ├── Dashboard/             # UNCHANGED
│   │   ├── Deliberation/          # REMOVED: legacy deliberation components
│   │   ├── deliberations/         # UNCHANGED: tier-1 sub-components
│   │   ├── Home/                  # REMOVED: legacy HomePage.tsx
│   │   ├── Logs/                  # NEW: test for LogsPage
│   │   ├── Observability/         # NEW: tests for A2ATracker, LLMTrace
│   │   ├── Settings/              # NEW: tests for ModelGarage, MCPToolsSection
│   │   ├── Setup/                 # NEW: test for SetupWizard
│   │   └── UI/                    # UNCHANGED (CommandPalette test exists)
│   ├── hooks/                     # UNCHANGED (8 hook tests exist)
│   ├── pages/                     # UNCHANGED: tier-1 pages
│   ├── stores/                    # NEW: tests for all 4 zustand stores
│   └── types/
│       └── deliberation.ts        # UNCHANGED: tier-1 types
├── tests/                         # NEW: Playwright E2E tests
│   ├── e2e/
│   │   ├── deliberation-flow.spec.ts
│   │   ├── navigation.spec.ts
│   │   └── settings.spec.ts
│   └── setup.ts
└── package.json                   # MODIFIED: remove reactflow, add playwright config
```

## Components

### A. Routing Unification (`App.tsx`)

Replace the dual routing system with a single `<Routes>` block:

```tsx
// BEFORE: dual system (MemoryRouter + useState view switcher)
function App() {
  const [currentView, setCurrentView] = useState('home');
  const location = useLocation();
  const isTier1Route = location.pathname === '/' || location.pathname.startsWith('/deliberations');

  if (isTier1Route) {
    // tier-1 pages via pathname
  } else {
    // legacy pages via renderView() switch
  }
}

// AFTER: unified react-router-dom
function App() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        {/* Tier-1 routes */}
        <Route path="/" element={<NewHomePage />} />
        <Route path="/deliberations" element={<NewDeliberationListPage />} />
        <Route path="/deliberations/:id" element={<NewDeliberationPage />} />

        {/* Legacy routes (kept as-is, just routed properly) */}
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/consciousness" element={<ConsciousnessPage />} />
        <Route path="/autonomous" element={<AutonomousPage />} />
        <Route path="/observability" element={<ObservabilityPage />} />
        <Route path="/chat" element={<AgentChat />} />
        <Route path="/canvas" element={<EnhancedCanvas />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
```

Remove: `currentView` state, `renderView()` function, unused imports (`useNavigate`, `Routes`, `Route`, `Navigate` as imports used only for type hints).

### B. API Client Consolidation

Refactor 5 modules to use centralized `client.ts`:

| Module | Current | Fix |
|--------|---------|-----|
| `agents.ts` | Local axios instance | `import api from './client'` |
| `consciousness.ts` | Local axios instance | `import api from './client'` |
| `autonomous.ts` | Local axios instance | `import api from './client'` |
| `deliberations.ts` | Local client with baseURL | `import api from './client'` |
| `wizard.ts` | Raw `fetch()` | `import api from './client'` |

Remove duplicated `API_URL` resolution from each module — it only lives in `client.ts`.

### C. Legacy Deliberation Removal

Delete these files entirely:
- `src/api/deliberation.ts` (legacy consensus-based API)
- `src/components/Deliberation/DeliberationPage.tsx` (legacy page)
- `src/components/Deliberation/LiveDeliberationPanel.tsx`
- `src/components/Deliberation/HistoricalDeliberations.tsx`
- `src/components/Home/HomePage.tsx` (legacy home)

Keep these (tier-1):
- `src/api/deliberations.ts` (tier-1 API)
- `src/components/deliberations/*` (tier-1 sub-components)
- `src/pages/home-page.tsx` (tier-1 home)
- `src/pages/deliberation-page.tsx`
- `src/pages/deliberation-list-page.tsx`

### D. Test Coverage Expansion

**Unit tests to add:**

| Category | Files | Priority |
|----------|-------|----------|
| Store tests | `canvasStore`, `deliberation-store`, `metricsStore`, `setupStore` | P0 |
| Agents tests | `AgentsPage`, `AgentCard`, `AgentConfigPanel`, `AgentControls` | P0 |
| Chat tests | `AgentChat`, `MessageInput`, `MessageList` | P1 |
| Canvas tests | `EnhancedCanvas`, `AgentNode`, `ConnectionEdge` | P1 |
| Settings tests | `ModelGarage`, `MCPToolsSection`, `ImportExportSection` | P2 |
| Observability tests | `A2ATracker`, `LLMTrace` | P2 |
| Setup test | `SetupWizard` | P2 |

**E2E tests to add (Playwright):**

| Test | What it verifies |
|------|------------------|
| `deliberation-flow.spec.ts` | Create deliberation → view list → open detail → interject |
| `navigation.spec.ts` | All routes render, sidebar navigation works |
| `settings.spec.ts` | API key save/load, model provider config |

### E. Dependency Cleanup

Remove from `package.json`:
```json
"reactflow": "11.10.0"
```

Audit imports: replace any `import ... from 'reactflow'` with `import ... from '@xyflow/react'`.

### F. Tier-1 API Verification

Verify:
- Vite proxy config (`/api` → `localhost:8000`) matches tier-1 routes
- `deliberations.ts` types match tier-1 backend schemas
- Home page calls tier-1 health check
- WebSocket URL connects to tier-1 WS endpoint

## Error handling

- Routing: `ErrorBoundary` wraps all routes (already exists)
- API: centralized error interceptor in `client.ts` handles 401/403/404/5xx (already exists)
- Tests: mocking strategy uses `vi.mock()` for API clients, consistent with existing patterns

## Testing

| Category | Current | Target |
|----------|---------|--------|
| Unit tests | 265 (22 files) | ~450+ (35+ files) |
| Component coverage | ~13% files | ~80% files |
| E2E tests | 0 | 3 Playwright specs |
| Store tests | 0 | 4 store test files |

## Implementation order

1. Remove legacy deliberation system (delete files, clean imports)
2. Unify routing in App.tsx
3. Consolidate API clients (5 modules)
4. Remove `reactflow` dependency, audit imports
5. Add store tests (4 files)
6. Add component tests (agents, chat, canvas, settings, observability, setup)
7. Add E2E tests (3 Playwright specs)
8. Verify tier-1 API connection
9. Run full test suite, verify coverage
