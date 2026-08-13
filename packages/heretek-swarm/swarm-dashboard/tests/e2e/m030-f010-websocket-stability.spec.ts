/**
 * M030 G-03 (F-010) Test — WebSocket Stability Under Re-Renders
 *
 * REGRESSION TEST for the F-010 issue (per PRIME_DIRECTIVE.md):
 *   The dashboard's WebSocket is rebuilt on every React render because
 *   useWebSocket.ts:102 has `onOpen`/`onClose`/`onError`/`onMessage`
 *   in its `connect` useCallback's dependency array, and
 *   useRealTimeAgentUpdates.ts:289-318 passes inline arrow functions
 *   for those callbacks. This causes:
 *     - `connect` to be recreated on every render
 *     - the mount useEffect ([connect, disconnect] deps) to re-run
 *     - WS close → WS reopen cycle
 *   The api container logs 74,107 "Dashboard WebSocket disconnected"
 *   / min under load.
 *
 * VERIFICATION (black-box, no in-browser instrumentation):
 *   - Count "Dashboard WebSocket connected" in api container logs.
 *   - Before fix: count rises by 15-20 during a 20s render-forcing test.
 *   - After fix: count rises by ≤ 2 (initial + maybe one intentional reconnect).
 *
 * FIX (after this test):
 *   Move onMessage/onOpen/onClose/onError to refs in useWebSocket.ts;
 *   have `connect` read from refs; mount useEffect deps = []. Then
 *   `connect` is stable across renders, the effect runs once per mount,
 *   and the WS stays open across re-renders.
 */

import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

const REPO_ROOT = '/home/john/Desktop/heretek-swarm';
const API_HOST = 'http://localhost:8000';
const API_KEY = process.env.HERETEK_API_KEY || 'htsk_deploy_test_key_2026';

function countWsConnects(): number {
  const cmd = `docker compose -f ${REPO_ROOT}/docker-compose.yml logs api 2>/dev/null | grep -c "Dashboard WebSocket connected" || true`;
  const out = execSync(cmd, { encoding: 'utf-8' }).trim();
  return parseInt(out, 10) || 0;
}

async function setupDashboard(page: any) {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.evaluate(
    ([host, key]) => {
      localStorage.setItem('swarm_configured', 'true');
      localStorage.setItem('swarm_api_host', host);
      localStorage.setItem('api_key', key);
    },
    [API_HOST, API_KEY]
  );
  await page.reload();
  await expect(page.getByText('Overview')).toBeVisible({ timeout: 15000 });
}

test.describe.configure({ mode: 'serial' });

test.describe('M030 G-03 — WebSocket Stability Under Re-Renders', () => {

  test('G-03-01: api logs "Dashboard WebSocket connected" ≤ 2 times when forcing 20 re-renders', async ({ page }) => {
    const before = countWsConnects();
    console.log(`WS-connects in api logs BEFORE: ${before}`);

    await setupDashboard(page);
    await page.waitForTimeout(2000); // let initial WS connect settle

    // Force 20 re-renders in 20 seconds
    const navButtons = page.locator('nav button');
    const buttonCount = await navButtons.count();
    console.log(`Found ${buttonCount} nav buttons; forcing 20 re-renders`);

    for (let i = 0; i < 20; i++) {
      const idx = i % Math.max(buttonCount, 1);
      try {
        await navButtons.nth(idx).click({ timeout: 1000 });
      } catch {
        // ignore individual click failures
      }
      await page.waitForTimeout(1000);
    }
    console.log('Forced 20 re-renders (1 per second over 20s)');

    // Wait for any final churn to settle
    await page.waitForTimeout(2000);

    const after = countWsConnects();
    const delta = after - before;
    console.log(`WS-connects in api logs AFTER: ${after} (delta = ${delta})`);

    // Pre-fix baseline: delta = 20+ (one WS construction per render).
    // Post-fix expectation: delta ≤ 2 (one initial + maybe one reconnect).
    expect(delta).toBeLessThanOrEqual(2);
    console.log(`✓ G-03-01: WS connect delta = ${delta} (≤ 2 threshold)`);
  });
});
