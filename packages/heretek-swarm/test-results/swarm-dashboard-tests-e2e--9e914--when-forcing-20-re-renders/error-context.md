# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: swarm-dashboard/tests/e2e/m030-f010-websocket-stability.spec.ts >> M030 G-03 — WebSocket Stability Under Re-Renders >> G-03-01: api logs "Dashboard WebSocket connected" ≤ 2 times when forcing 20 re-renders
- Location: swarm-dashboard/tests/e2e/m030-f010-websocket-stability.spec.ts:60:3

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/", waiting until "load"

```

# Test source

```ts
  1  | /**
  2  |  * M030 G-03 (F-010) Test — WebSocket Stability Under Re-Renders
  3  |  *
  4  |  * REGRESSION TEST for the F-010 issue (per PRIME_DIRECTIVE.md):
  5  |  *   The dashboard's WebSocket is rebuilt on every React render because
  6  |  *   useWebSocket.ts:102 has `onOpen`/`onClose`/`onError`/`onMessage`
  7  |  *   in its `connect` useCallback's dependency array, and
  8  |  *   useRealTimeAgentUpdates.ts:289-318 passes inline arrow functions
  9  |  *   for those callbacks. This causes:
  10 |  *     - `connect` to be recreated on every render
  11 |  *     - the mount useEffect ([connect, disconnect] deps) to re-run
  12 |  *     - WS close → WS reopen cycle
  13 |  *   The api container logs 74,107 "Dashboard WebSocket disconnected"
  14 |  *   / min under load.
  15 |  *
  16 |  * VERIFICATION (black-box, no in-browser instrumentation):
  17 |  *   - Count "Dashboard WebSocket connected" in api container logs.
  18 |  *   - Before fix: count rises by 15-20 during a 20s render-forcing test.
  19 |  *   - After fix: count rises by ≤ 2 (initial + maybe one intentional reconnect).
  20 |  *
  21 |  * FIX (after this test):
  22 |  *   Move onMessage/onOpen/onClose/onError to refs in useWebSocket.ts;
  23 |  *   have `connect` read from refs; mount useEffect deps = []. Then
  24 |  *   `connect` is stable across renders, the effect runs once per mount,
  25 |  *   and the WS stays open across re-renders.
  26 |  */
  27 |
  28 | import { test, expect } from '@playwright/test';
  29 | import { execSync } from 'child_process';
  30 |
  31 | const REPO_ROOT = '/home/john/Desktop/heretek-swarm';
  32 | const API_HOST = 'http://localhost:8000';
  33 | const API_KEY = process.env.HERETEK_API_KEY || 'htsk_deploy_test_key_2026';
  34 |
  35 | function countWsConnects(): number {
  36 |   const cmd = `docker compose -f ${REPO_ROOT}/docker-compose.yml logs api 2>/dev/null | grep -c "Dashboard WebSocket connected" || true`;
  37 |   const out = execSync(cmd, { encoding: 'utf-8' }).trim();
  38 |   return parseInt(out, 10) || 0;
  39 | }
  40 |
  41 | async function setupDashboard(page: any) {
> 42 |   await page.goto('/');
     |              ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  43 |   await page.evaluate(() => localStorage.clear());
  44 |   await page.evaluate(
  45 |     ([host, key]) => {
  46 |       localStorage.setItem('swarm_configured', 'true');
  47 |       localStorage.setItem('swarm_api_host', host);
  48 |       localStorage.setItem('api_key', key);
  49 |     },
  50 |     [API_HOST, API_KEY]
  51 |   );
  52 |   await page.reload();
  53 |   await expect(page.getByText('Overview')).toBeVisible({ timeout: 15000 });
  54 | }
  55 |
  56 | test.describe.configure({ mode: 'serial' });
  57 |
  58 | test.describe('M030 G-03 — WebSocket Stability Under Re-Renders', () => {
  59 |
  60 |   test('G-03-01: api logs "Dashboard WebSocket connected" ≤ 2 times when forcing 20 re-renders', async ({ page }) => {
  61 |     const before = countWsConnects();
  62 |     console.log(`WS-connects in api logs BEFORE: ${before}`);
  63 |
  64 |     await setupDashboard(page);
  65 |     await page.waitForTimeout(2000); // let initial WS connect settle
  66 |
  67 |     // Force 20 re-renders in 20 seconds
  68 |     const navButtons = page.locator('nav button');
  69 |     const buttonCount = await navButtons.count();
  70 |     console.log(`Found ${buttonCount} nav buttons; forcing 20 re-renders`);
  71 |
  72 |     for (let i = 0; i < 20; i++) {
  73 |       const idx = i % Math.max(buttonCount, 1);
  74 |       try {
  75 |         await navButtons.nth(idx).click({ timeout: 1000 });
  76 |       } catch {
  77 |         // ignore individual click failures
  78 |       }
  79 |       await page.waitForTimeout(1000);
  80 |     }
  81 |     console.log('Forced 20 re-renders (1 per second over 20s)');
  82 |
  83 |     // Wait for any final churn to settle
  84 |     await page.waitForTimeout(2000);
  85 |
  86 |     const after = countWsConnects();
  87 |     const delta = after - before;
  88 |     console.log(`WS-connects in api logs AFTER: ${after} (delta = ${delta})`);
  89 |
  90 |     // Pre-fix baseline: delta = 20+ (one WS construction per render).
  91 |     // Post-fix expectation: delta ≤ 2 (one initial + maybe one reconnect).
  92 |     expect(delta).toBeLessThanOrEqual(2);
  93 |     console.log(`✓ G-03-01: WS connect delta = ${delta} (≤ 2 threshold)`);
  94 |   });
  95 | });
  96 |
```
