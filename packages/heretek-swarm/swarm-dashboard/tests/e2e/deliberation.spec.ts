/**
 * E2E Tests for Deliberation Page
 *
 * Tests the Historical Deliberations view with mocked API responses,
 * including history list, detail drill-down, audit stats, and tab navigation.
 */

import { test, expect } from '@playwright/test';

// =============================================================================
// Mock data
// =============================================================================

const MOCK_HISTORY = {
  consensus_history: [
    {
      id: 'round-abc-123',
      topic: 'Deploy v2.0 to production',
      decision: 'approved — deploy with canary rollout',
      confidence: 0.92,
      vote_count: 4,
      completed_at: '2025-06-15T14:30:00Z',
      red_flags: [],
    },
    {
      id: 'round-def-456',
      topic: 'Migrate database to Postgres 16',
      decision: 'approved with conditions',
      confidence: 0.78,
      vote_count: 4,
      completed_at: '2025-06-14T10:00:00Z',
      red_flags: ['Low confidence threshold', 'Conflicting opinions'],
    },
    {
      id: 'round-ghi-789',
      topic: 'Add rate limiting to public API',
      decision: null,
      confidence: null,
      vote_count: 2,
      completed_at: null,
      red_flags: [],
    },
  ],
  total: 3,
};

const MOCK_ROUND_DETAIL = {
  id: 'round-abc-123',
  topic: 'Deploy v2.0 to production',
  state: 'completed',
  votes: [
    {
      agent_id: 'agent-alpha',
      decision: 'Approve deployment with canary strategy',
      confidence: 0.95,
      timestamp: '2025-06-15T14:25:00Z',
      metadata: { strategy: 'canary' },
    },
    {
      agent_id: 'agent-beta',
      decision: 'Approve — all integration tests pass',
      confidence: 0.9,
      timestamp: '2025-06-15T14:26:00Z',
      metadata: {},
    },
    {
      agent_id: 'agent-gamma',
      decision: 'Approve but monitor error rates closely',
      confidence: 0.85,
      timestamp: '2025-06-15T14:27:00Z',
      metadata: { caveat: 'monitoring' },
    },
    {
      agent_id: 'agent-delta',
      decision: 'Approve with rollback plan ready',
      confidence: 0.98,
      timestamp: '2025-06-15T14:28:00Z',
      metadata: {},
    },
  ],
  decision: 'approved — deploy with canary rollout',
  confidence: 0.92,
  red_flags: [],
  created_at: '2025-06-15T14:00:00Z',
  completed_at: '2025-06-15T14:30:00Z',
  metadata: {},
};

const MOCK_ROUND_WITH_FLAGS = {
  id: 'round-def-456',
  topic: 'Migrate database to Postgres 16',
  state: 'completed',
  votes: [
    {
      agent_id: 'agent-alpha',
      decision: 'Approve migration',
      confidence: 0.8,
      timestamp: '2025-06-14T09:50:00Z',
      metadata: {},
    },
    {
      agent_id: 'agent-beta',
      decision: 'Oppose — too risky without rollback plan',
      confidence: 0.65,
      timestamp: '2025-06-14T09:51:00Z',
      metadata: {},
    },
  ],
  decision: 'approved with conditions',
  confidence: 0.78,
  red_flags: ['Low confidence threshold', 'Conflicting opinions'],
  created_at: '2025-06-14T09:00:00Z',
  completed_at: '2025-06-14T10:00:00Z',
  metadata: {},
};

const MOCK_AUDIT_STATS = {
  total_decisions: 42,
  successful: 38,
  failed: 4,
  average_confidence: 0.84,
  average_deliberation_rounds: 2.3,
};

// =============================================================================
// Helpers
// =============================================================================

/** Set localStorage to skip setup wizard */
async function skipSetupWizard(page: import('@playwright/test').Page) {
  // Navigate first so the page context exists
  await page.goto('/');
  // Set localStorage values
  await page.evaluate(() => {
    window.localStorage.setItem('swarm_configured', 'true');
    window.localStorage.setItem('swarm_api_host', 'http://localhost:8000');
    window.localStorage.setItem('api_key', 'test-key');
  });
  // Reload so the app reads the new values
  await page.reload();
}

/** Intercept API calls with mock responses */
async function mockApis(page: import('@playwright/test').Page) {
  // Intercept all requests to the API host (port 8000) — use full glob
  await page.route('**/api/consensus**', route => {
    const url = route.request().url();
    const body = (() => {
      if (url.includes('/history')) return MOCK_HISTORY;
      if (url.includes('/round-abc-123')) return MOCK_ROUND_DETAIL;
      if (url.includes('/round-def-456')) return MOCK_ROUND_WITH_FLAGS;
      if (url.includes('/audit/statistics')) return MOCK_AUDIT_STATS;
      if (url.includes('/audit/')) return {};
      // Default: return empty for any other consensus endpoint
      return { consensus_rounds: [], total: 0 };
    })();

    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });

  // WebSocket — prevent real connections
  await page.route('**/ws**', route => route.abort());
}

/** Navigate to the Deliberation page — skipSetupWizard already loaded the page */
async function goToDeliberation(page: import('@playwright/test').Page) {
  // Page is already loaded after skipSetupWizard's reload
  // Click the Deliberation nav item in the sidebar
  await page.getByRole('button', { name: /Deliberation/ }).click();
}

// =============================================================================
// Tests
// =============================================================================

test.describe('Deliberation Page', () => {
  test.beforeEach(async ({ page }) => {
    await skipSetupWizard(page);
    await mockApis(page);
  });

  test('should display the page heading and tab navigation', async ({ page }) => {
    await goToDeliberation(page);

    await expect(page.getByRole('heading', { name: 'Deliberation', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: /Live/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /History/ })).toBeVisible();
  });

  test('should have Live tab active by default', async ({ page }) => {
    await goToDeliberation(page);

    const liveTab = page.getByRole('button', { name: /Live/ });
    await expect(liveTab).toHaveClass(/bg-blue-600/);
  });
});

test.describe('Historical Deliberations', () => {
  test.beforeEach(async ({ page }) => {
    await skipSetupWizard(page);
    await mockApis(page);
    // Navigate to Deliberation page and switch to History tab
    await goToDeliberation(page);
    await page.getByRole('button', { name: /History/ }).click();
  });

  test('should switch to History tab and display audit stats', async ({ page }) => {
    const historyTab = page.getByRole('button', { name: /History/ });
    await expect(historyTab).toHaveClass(/bg-blue-600/);

    // Audit stats should show the mocked values
    await expect(page.getByText('42')).toBeVisible(); // total decisions
    await expect(page.getByText('38')).toBeVisible(); // successful
    await expect(page.getByText('4', { exact: true })).toBeVisible(); // failed
  });

  test('should display history list with consensus entries', async ({ page }) => {
    // Should show the past rounds heading
    await expect(page.getByText('Past Rounds (3)')).toBeVisible();

    // Should show the three mock entries
    await expect(page.getByText('Deploy v2.0 to production')).toBeVisible();
    await expect(page.getByText('Migrate database to Postgres 16')).toBeVisible();
    await expect(page.getByText('Add rate limiting to public API')).toBeVisible();
  });

  test('should show consensus badge for entries with decisions', async ({ page }) => {
    // Entries with decisions should show "Consensus" badge
    const consensusBadges = page.getByText('Consensus');
    await expect(consensusBadges.first()).toBeVisible();
  });

  test('should show vote counts and confidence scores', async ({ page }) => {
    // Vote count
    await expect(page.getByText(/🗳️ 4 votes/).first()).toBeVisible();

    // Confidence percentage
    await expect(page.getByText(/92% confidence/).first()).toBeVisible();
  });

  test('should show red flag indicator for entries with flags', async ({ page }) => {
    await expect(page.getByText(/2 red flags/)).toBeVisible();
  });

  test('should show empty detail panel placeholder before selection', async ({ page }) => {
    await expect(page.getByText('Select a round to view details')).toBeVisible();
  });

  test('should display round detail when clicking a history entry', async ({ page }) => {
    // Click the first history entry
    await page.getByText('Deploy v2.0 to production').click();

    // Detail panel should show
    await expect(page.getByTestId('round-detail')).toBeVisible();

    // Should show the topic
    await expect(page.getByTestId('round-detail').getByText('Deploy v2.0 to production')).toBeVisible();

    // Should show the state
    await expect(page.getByTestId('round-detail').getByText('completed', { exact: true })).toBeVisible();

    // Should show the decision
    await expect(page.getByTestId('decision-block')).toBeVisible();
    await expect(page.getByText('approved — deploy with canary rollout')).toBeVisible();
  });

  test('should show individual agent votes in detail panel', async ({ page }) => {
    await page.getByText('Deploy v2.0 to production').click();
    await expect(page.getByTestId('round-detail')).toBeVisible();

    // Should show agent names
    await expect(page.getByText('agent-alpha')).toBeVisible();
    await expect(page.getByText('agent-beta')).toBeVisible();
    await expect(page.getByText('agent-gamma')).toBeVisible();
    await expect(page.getByText('agent-delta')).toBeVisible();

    // Should show confidence scores
    await expect(page.getByText('95%').first()).toBeVisible();
    await expect(page.getByText('90%').first()).toBeVisible();
  });

  test('should show red flags in detail panel for flagged rounds', async ({ page }) => {
    // Click the entry with red flags
    await page.getByText('Migrate database to Postgres 16').click();
    await expect(page.getByTestId('round-detail')).toBeVisible();

    // Should show red flags heading
    await expect(page.getByTestId('red-flags-heading')).toBeVisible();
    await expect(page.getByText('Low confidence threshold')).toBeVisible();
    await expect(page.getByText('Conflicting opinions')).toBeVisible();
  });

  test('should switch between different history entries', async ({ page }) => {
    // Click first entry
    await page.getByText('Deploy v2.0 to production').click();
    await expect(page.getByTestId('decision-block')).toBeVisible();

    // Click second entry — detail should update
    await page.getByText('Migrate database to Postgres 16').click();
    await expect(page.getByTestId('red-flags-heading')).toBeVisible();
  });

  test('should have a refresh button that reloads history', async ({ page }) => {
    const refreshBtn = page.getByTestId('refresh-history');
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toHaveText(/Refresh/);

    // Click refresh — should not crash
    await refreshBtn.click();

    // History list should still be visible after refresh
    await expect(page.getByText('Past Rounds (3)')).toBeVisible();
  });

  test('should show timeline dates in detail panel', async ({ page }) => {
    await page.getByText('Deploy v2.0 to production').click();
    await expect(page.getByTestId('round-detail')).toBeVisible();

    // Should show created and completed dates
    await expect(page.getByText(/Created:/)).toBeVisible();
    await expect(page.getByText(/Completed:/)).toBeVisible();
  });
});

test.describe('Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await skipSetupWizard(page);
    await mockApis(page);
    await goToDeliberation(page);
  });

  test('should switch between Live and History tabs', async ({ page }) => {
    // Start on Live tab
    await expect(page.getByRole('button', { name: /Live/ })).toHaveClass(/bg-blue-600/);

    // Switch to History
    await page.getByRole('button', { name: /History/ }).click();
    await expect(page.getByRole('button', { name: /History/ })).toHaveClass(/bg-blue-600/);
    await expect(page.getByText('Past Rounds')).toBeVisible();

    // Switch back to Live
    await page.getByRole('button', { name: /Live/ }).click();
    await expect(page.getByRole('button', { name: /Live/ })).toHaveClass(/bg-blue-600/);
  });
});
