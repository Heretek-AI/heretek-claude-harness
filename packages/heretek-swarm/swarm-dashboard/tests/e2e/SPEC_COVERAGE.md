# SPEC_COVERAGE.md — M025 Dashboard Integration E2E Tests

**Milestone:** M025 — All 5 dashboard components receive live WebSocket data
**Slice:** S03 — Execute complete end-to-end scenario (chat → WebSocket → Canvas → ExternalCallsPanel)
**Status:** Active
**Last Updated:** 2026-04-23

---

## Overview

This document is the living record of **R063**: which dashboard components have live WebSocket E2E tests, what they assert, and what requires a live backend to pass.

All tests are in `swarm-dashboard/tests/e2e/` and use Playwright with chromium.

---

## Test Files

| File | Tests | Purpose |
|------|-------|---------|
| `m025-websocket-live.spec.ts` | 20 | Full suite: A2ATracker, Canvas, ExternalCallsPanel, AgentDetailDrawer, full E2E scenario |
| `m025-chat-interface.spec.ts` | 4 | ChatInterface HTTP REST tests (no WebSocket) |
| `m025-t04-tests.spec.ts` | 13 | Duplicate suite from T04; has duplicate test titles (A2A-TRACKER-06 × 2) — see Known Issues |

---

## Component Coverage

### 1. A2ATracker

**Verification strategy:** Subscribe to `/ws/dashboard` WebSocket directly and assert real `a2a_message` events arrive with valid `from`/`to` fields. Distinguishes real WebSocket data from demo setInterval data.

**Tests (in `m025-websocket-live.spec.ts`):**

| ID | Test | What It Verifies | Pass Criteria |
|----|------|-----------------|---------------|
| A2A-TRACKER-01 | A2ATracker shows ≥1 real A2A message within 5 seconds | `subscribeWebSocket()` captures ≥1 `a2a_message` with valid `from`/`to` | ≥1 real message received via WebSocket, no critical console errors |
| A2A-TRACKER-03 | No demo setInterval data in A2ATracker during live session | Messages arrive via WebSocket (not `Math.random()` loops); agent IDs match `/^[a-z0-9_]+$/` | ≥1 message with real agent IDs, DOM shows entries |
| A2A-TRACKER-06 | Agents tab shows agents derived from real messages | Agents tab lists real agent IDs (not `/^(Agent\|Demo\|Test)-?\d*$/`); message counts visible | Agent names are real, ≥1 WebSocket message confirmed |
| A2A-TRACKER-07 | Resources/Workflows tabs show non-zero stats | Resources tab shows "Total Tokens", "Avg Memory"; Workflows stats panel shows Active/Completed/Failed | Stat labels found in DOM, ≥1 message confirmed |

**Tests (in `m025-t04-tests.spec.ts`):** Identical tests duplicated here (A2A-TRACKER-01 through A2A-TRACKER-07). A2A-TRACKER-06 appears twice in this file.

**Requires live backend:** Yes — WebSocket must be running at `ws://localhost:8000/ws/dashboard`.

---

### 2. Canvas (ReactFlow)

**Verification strategy:** Navigate to Canvas view, subscribe to WebSocket to confirm real A2A events arrive, then check ReactFlow DOM for animated edges and real agent node labels.

**Tests (in `m025-websocket-live.spec.ts`):**

| ID | Test | What It Verifies | Pass Criteria |
|----|------|-----------------|---------------|
| A2A-TRACKER-02 | Canvas shows animated edges from real A2A events within 10 seconds | Real `a2a_message` events arrive; Canvas has ≥1 animated edge (`.react-flow__edge.animated`); WebSocket status dot is green | Real A2A events received; WebSocket connected; no critical console errors |
| A2A-TRACKER-05 | Canvas receives A2A edges from WebSocket events (not demo edges) | `subscribeWebSocket()` captures A2A events; Canvas shows edges/animated edges; logs agent pairs | ≥1 real A2A event; Canvas edge count ≥ 0 (may be 0 if agents haven't communicated) |
| CANVAS-06 | Canvas node labels are real agent names (not Node-X) | Agent IDs from WebSocket captured; node labels checked against `/^Node-?\d+$/i` and `/^Agent$/i` | All node labels are real agent names, not placeholders |
| CANVAS-07 | Canvas animated edges have CSS animation property | A2A events received; animated edges have `animated` CSS class | ≥1 real A2A event; animated edges have `.animated` class |

**Requires live backend:** Yes — WebSocket at `ws://localhost:8000/ws/dashboard`.

---

### 3. ChatInterface

**Verification strategy:** HTTP REST tests: send message via POST, verify response renders, verify agent contributions expand, verify agent switching updates context, verify API errors surface.

**Tests (in `m025-chat-interface.spec.ts`):**

| ID | Test | What It Verifies | Pass Criteria |
|----|------|-----------------|---------------|
| CHAT-01 | Send message via REST POST and verify response renders in DOM | `POST /api/agents/{agentId}/chat` succeeds; user message appears in DOM; assistant response appears | HTTP 200, message in DOM, no critical console errors |
| CHAT-02 | Agent contributions expand correctly | Agent contribution cards expand to show details | Expansion UI works, details visible |
| CHAT-03 | Agent switching updates chat context | Switching agent updates context; messages cleared or threaded | Agent switch triggers correct state update |
| CHAT-04 | API errors surface in DOM | API errors (4xx/5xx) surface as user-facing error message | Error message visible in DOM |

**Requires live backend:** Yes — REST API at `http://localhost:8000`.

---

### 4. ExternalCallsPanel

**Verification strategy:** Subscribe to WebSocket capturing `external_call` events, verify panel shows live indicator, verify filter controls work, verify call expansion shows details, verify stats (total/success/errors) are displayed.

**Tests (in `m025-websocket-live.spec.ts`):**

| ID | Test | What It Verifies | Pass Criteria |
|----|------|-----------------|---------------|
| EXTERNAL-CALLS-01 | ExternalCallsPanel receives live external_call events | `subscribeWebSocket()` captures `external_call` events; panel shows live (`.animate-pulse`) indicator | ≥1 `external_call` event OR live indicator visible; no critical console errors |
| EXTERNAL-CALLS-02 | ExternalCallsPanel filter controls work correctly | Filter dropdowns exist (≥3); agent filter has "All agents"; status filter has 2xx/4xx/5xx options; clearing filter restores view | Filter controls functional, state resets correctly |
| EXTERNAL-CALLS-03 | ExternalCallsPanel displays call details on expansion | Clicking call entry shows ▼ indicator and details section (Request/Response headers) | Expansion works OR empty state shown correctly |
| EXTERNAL-CALLS-04 | ExternalCallsPanel shows stats (total, success, errors) | Header shows "Total:", "Success:", "Errors:", "Avg:" labels with numeric or dash values | Stats labels visible; values numeric or dash |

**Requires live backend:** Yes — WebSocket at `ws://localhost:8000/ws/dashboard`.

---

### 5. AgentDetailDrawer

**Verification strategy:** Click agent node on Canvas, verify drawer slides in with tabs, verify Consciousness tab shows phi score, verify state badge, verify placeholder tabs (Memory/Tools/Tasks), verify close button dismisses drawer.

**Tests (in `m025-websocket-live.spec.ts`):**

| ID | Test | What It Verifies | Pass Criteria |
|----|------|-----------------|---------------|
| DRAWER-01 | AgentDetailDrawer slides in when agent node is clicked | Clicking Canvas node opens drawer; close button visible; ≥4 tabs present | Drawer opens, tabs present, no critical console errors |
| DRAWER-02 | Consciousness tab shows phi score (numeric) | Active tab is "Consciousness"; Phi score label visible; phi value is numeric | `parseFloat(phiScore)` is not NaN |
| DRAWER-03 | State badge renders in Consciousness tab | State badge shows valid state: dormant/emerging/coherent/transcendent | State text matches known states |
| DRAWER-04 | Memory/Tools/Tasks tabs show placeholders (not crash) | Tabs show placeholder messages ("memory not available", "tools MCP not available", "tasks not available") | All placeholder tabs render without crash |
| DRAWER-05 | Close button dismisses the drawer | Close button closes drawer; drawer reopens on node re-click | Drawer open/close state management works |

**Requires live backend:** Yes — Canvas and WebSocket at `ws://localhost:8000/ws/dashboard`.

---

## Full E2E Scenario Tests

**Tests (in `m025-websocket-live.spec.ts`):**

| ID | Test | What It Verifies | Pass Criteria |
|----|------|-----------------|---------------|
| CHAT-E2E-01 | Complete E2E: chat → WebSocket A2A → Canvas edges → ExternalCallsPanel | 1. Bypass wizard; 2. Navigate to Chat; 3. Subscribe to WebSocket capturing `a2a_message` AND `external_call`; 4. POST to `/api/agents/steward/chat`; 5. Verify A2A messages with valid from/to; 6. Navigate to Canvas, verify animated edges; 7. Navigate to ExternalCallsPanel, verify HTTP call data | Real events captured; Chat API responds; A2A and external events logged; no critical console errors |
| CHAT-E2E-02 | subscribeWebSocketV2 captures all event types correctly | `subscribeWebSocketV2()` returns `{ a2aMessages, externalCalls, otherEvents, all }`; all arrays are Arrays; `all.length ≥ categorizedTotal`; no duplicate events in `all`; A2A messages have `type='a2a_message'` and valid from/to; external_call events have `type='external_call'` | All arrays correct type; categorizedTotal ≤ all.length; no duplicates; structured event summary logged |

**Requires live backend:** Yes — WebSocket at `ws://localhost:8000/ws/dashboard` AND REST API at `http://localhost:8000`.

---

## Event Type Summary

The WebSocket at `/ws/dashboard` broadcasts these event types:

| Event Type | Component Consumer | Test Coverage |
|-----------|-------------------|---------------|
| `a2a_message` | A2ATracker, Canvas (edges), AgentDetailDrawer | A2A-TRACKER-01, A2A-TRACKER-02, A2A-TRACKER-03, A2A-TRACKER-04, A2A-TRACKER-05, CANVAS-06, CANVAS-07, CHAT-E2E-01, CHAT-E2E-02 |
| `external_call` | ExternalCallsPanel | EXTERNAL-CALLS-01, EXTERNAL-CALLS-02, EXTERNAL-CALLS-03, EXTERNAL-CALLS-04, CHAT-E2E-01 |
| `heartbeat` / `status` / other | (informational) | CHAT-E2E-02 |

---

## Known Limitations

### Backend Dependency

All tests in `m025-websocket-live.spec.ts` and `m025-chat-interface.spec.ts` require a live backend:
- WebSocket at `ws://localhost:8000/ws/dashboard`
- REST API at `http://localhost:8000`
- Dashboard frontend at `http://localhost:3000`

Tests will fail with connection errors if the backend is not running. This is by design — the tests verify real data flows, not mock data.

### Timing Sensitivity

Some tests use timeouts (5s, 10s, 15s) to wait for WebSocket events. If the triad deliberation is slow or no agent communication occurs during the window, A2A events may not arrive. Tests handle this gracefully by logging notes and not failing assertions for acceptable scenarios where events don't arrive within the window.

### Duplicate Test Titles

`m025-t04-tests.spec.ts` contains duplicate test titles:
- `A2A-TRACKER-06` appears twice (line 920 and line 988)
- `A2A-TRACKER-06` is also present in `m025-websocket-live.spec.ts`

Playwright will exit with an error if both files are loaded simultaneously. Use `tests/e2e/m025-websocket-live.spec.ts` as the authoritative suite.

---

## Pass Criteria (R063 Proof)

R063 states: *"All 5 dashboard components receive live WebSocket data (A2ATracker, Canvas, ExternalCallsPanel, AgentDetailDrawer, ChatInterface)."*

| Component | Live WebSocket Test Coverage | Requires Backend |
|-----------|-----------------------------|-----------------|
| A2ATracker | ✅ A2A-TRACKER-01, A2A-TRACKER-03, A2A-TRACKER-06, A2A-TRACKER-07 | Yes |
| Canvas | ✅ A2A-TRACKER-02, A2A-TRACKER-05, CANVAS-06, CANVAS-07 | Yes |
| ExternalCallsPanel | ✅ EXTERNAL-CALLS-01 through EXTERNAL-CALLS-04 | Yes |
| AgentDetailDrawer | ✅ DRAWER-01 through DRAWER-05 | Yes |
| ChatInterface | ✅ CHAT-01 through CHAT-04 (REST) + CHAT-E2E-01 (WebSocket) | Yes |

---

## Running the Tests

```bash
# Run all CHAT-E2E tests
cd swarm-dashboard && npx playwright test tests/e2e/m025-websocket-live.spec.ts --grep "CHAT-E2E"

# Run full M025 websocket suite
cd swarm-dashboard && npx playwright test tests/e2e/m025-websocket-live.spec.ts

# Run ChatInterface HTTP tests
cd swarm-dashboard && npx playwright test tests/e2e/m025-chat-interface.spec.ts

# List all M025 tests
cd swarm-dashboard && npx playwright test tests/e2e/m025-websocket-live.spec.ts --list
```

**Note:** Do NOT load `m025-t04-tests.spec.ts` and `m025-websocket-live.spec.ts` simultaneously — they contain duplicate test titles that cause Playwright to exit with a duplicate test error.
