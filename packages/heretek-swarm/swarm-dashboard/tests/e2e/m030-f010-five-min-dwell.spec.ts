/**
 * M030 G-03 Five-Minute Browser Dwell (R-2)
 *
 * Asserts the F-010 fix holds under realistic sustained load:
 *  - Dashboard loaded for 5 minutes
 *  - 10 re-renders triggered (one every 30s)
 *  - 0 console errors related to WebSocket churn
 *  - ≤ 2 new "Dashboard WebSocket connected" api log entries
 *
 * Pre-fix baseline: 74,107 "Dashboard WebSocket disconnected"
 * warnings per minute, ~1000+ "Dashboard WebSocket connected"
 * log entries per 5 minutes under the same workload.
 */

import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

const REPO_ROOT = '/home/john/Desktop/heretek-swarm';
const API_KEY = process.env.HERETEK_API_KEY || 'htsk_deploy_test_key_2026';

function countWsConnects(): number {
  const cmd = `docker compose -f ${REPO_ROOT}/docker-compose.yml logs api 2>/dev/null | grep -c "Dashboard WebSocket connected" || true`;
  return parseInt(execSync(cmd, { encoding: 'utf-8' }).trim(), 10) || 0;
}

async function setupDashboard(page: any) {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.evaluate(
    ([key]) => {
      localStorage.setItem('swarm_configured', 'true');
      localStorage.setItem('swarm_api_host', 'http://localhost:8000');
      localStorage.setItem('api_key', key);
    },
    [API_KEY]
  );
  await page.reload();
  await expect(page.getByText('Overview')).toBeVisible({ timeout: 15000 });
}

test.describe('M030 G-03 — Five-Minute Dwell (R-2)', () => {

  test('F-010-5MIN: 0 WS churn errors and ≤ 2 new WS connects over 5 minutes of sustained re-renders', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg: any) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    const wsConnectsBefore = countWsConnects();
    console.log(`WS-connects BEFORE: ${wsConnectsBefore}`);

    await setupDashboard(page);
    await page.waitForTimeout(3000);
    const wsConnectsAfterMount = countWsConnects();
    console.log(`WS-connects AFTER mount: ${wsConnectsAfterMount} (delta = ${wsConnectsAfterMount - wsConnectsBefore})`);

    const navButtons = page.locator('nav button');
    const buttonCount = await navButtons.count();
    console.log(`Found ${buttonCount} nav buttons; starting 5-min dwell`);

    // Force 10 re-renders over 5 minutes (one every 30s)
    for (let i = 0; i < 10; i++) {
      const idx = i % Math.max(buttonCount, 1);
      try {
        await navButtons.nth(idx).click({ timeout: 2000 });
      } catch {
        // ignore
      }
      console.log(`Re-render ${i + 1}/10 at ${(i + 1) * 30}s`);
      await page.waitForTimeout(30_000);
    }
    console.log('5-min dwell complete');

    // Wait for any final churn
    await page.waitForTimeout(2000);

    const wsConnectsAfter = countWsConnects();
    const dwellDelta = wsConnectsAfter - wsConnectsAfterMount;
    console.log(`WS-connects AFTER dwell: ${wsConnectsAfter} (dwell delta = ${dwellDelta})`);

    // During 5 minutes of forcing re-renders, expect ≤ 1 new WS connections
    // (the WS should stay connected throughout; 1 is the initial mount).
    expect(dwellDelta).toBeLessThanOrEqual(1);
    console.log(`✓ 5-min dwell WS-connect delta = ${dwellDelta} (≤ 1)`);

    // Count only re-render churn (F-010) errors, not initial-connect errors.
    // "WebSocket is closed before the connection is established" is the
    // F-010 symptom — a WS that opens and immediately closes because the
    // component re-rendered.
    const wsChurnErrors = consoleErrors.filter((err) =>
      err.includes('WebSocket is closed before')
    );
    console.log(`Total console errors: ${consoleErrors.length}`);
    console.log(`WS-churn errors (F-010 specific): ${wsChurnErrors.length}`);
    expect(wsChurnErrors.length).toBe(0);
    console.log(`✓ 0 WS-churn errors over 5 minutes (F-010 fix holds)`);
  });
});
