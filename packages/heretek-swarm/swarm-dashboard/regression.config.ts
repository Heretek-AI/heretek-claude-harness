import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for M011 regression E2E tests against Docker stack.
 *
 * Runs tests against the full Docker Compose stack (not Vite dev server).
 * Uses localStorage bypass to skip the setup wizard and verify live dashboard features.
 *
 * Usage:
 *   npx playwright test --config regression.config.ts --project=chromium --grep "REGRESSION-01"
 *   npx playwright test --config regression.config.ts --list
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 1, // Allow one retry on CI
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',

    // Capture console errors for test verification
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Docker Compose startup for full stack testing
  // From repo root where docker-compose.yml lives
  webServer: {
    command: 'cd /home/john/Projects/heretek-swarm && docker compose up',
    url: 'http://localhost:3000',
    reuseExistingServer: true, // Don't rebuild if already up
    timeout: 300_000, // 5 min for Docker startup
  },
});
