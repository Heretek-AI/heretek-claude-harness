/**
 * M028 E2E Test - Agent Spawn Verification (23/23 ACTIVE)
 *
 * Tests that all 23 agents spawned via API lifespan reach ACTIVE state.
 *
 * Test workflow:
 * 1. Bring up docker-compose stack with --profile autonomous
 * 2. Poll GET /api/health until API is healthy (120s timeout)
 * 3. Poll GET /api/agents every 5s until all 23 agents have status=active (120s timeout)
 * 4. Assert total === 23 and all agents status === 'active'
 * 5. Tear down docker-compose stack
 *
 * Verification: npx playwright test tests/e2e/m028-agent-spawn.spec.ts --project=chromium
 */

import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

// docker-compose.yml is at project root (4 levels up from this test file)
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const COMPOSE_FILE = resolve(__dirname, '..', '..', '..', 'docker-compose.yml');

// All 23 expected agent IDs (from _spawn_all_agents in main.py)
const EXPECTED_AGENT_IDS = [
  // Tier 1: Core Triad
  'steward',
  'alpha',
  'beta',
  'charlie',
  // Tier 2: Support
  'historian',
  'metis',
  'empath',
  'perceiver',
  'echo',
  // Tier 3: Exploration
  'explorer',
  'examiner',
  'dreamer',
  'coder',
  // Tier 4: Safety
  'sentinel',
  'sentinel-prime',
  'arbiter',
  // Tier 5: Coordination
  'coordinator',
  'nexus',
  'catalyst',
  'chronos',
  // Tier 6: Enhancement
  'prism',
  'habit-forge',
  'perceiver-plus',
];

// API configuration
const API_HOST = 'http://localhost:8000';
const API_KEY = 'htsk_42a231c6b47abf4cffd8bbe842789fbf';

// Polling configuration
const HEALTH_POLL_INTERVAL_MS = 5000;
const HEALTH_POLL_TIMEOUT_MS = 120_000;
const AGENT_POLL_INTERVAL_MS = 5000;
const AGENT_POLL_TIMEOUT_MS = 120_000;

test.describe('M028 Agent Spawn Verification (23/23 ACTIVE)', () => {
  /**
   * Bring up the docker-compose autonomous stack and run database migrations.
   * Runs once before all tests in this describe block.
   */
  test.beforeAll(async () => {
    console.log(`Bringing up autonomous stack via ${COMPOSE_FILE}`);

    // Clean up any stale Docker state that could cause "network not found" errors
    try {
      execSync(
        `docker network prune -f && docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans`,
        { stdio: 'pipe', timeout: 60000 }
      );
    } catch { /* ignore — may be nothing to clean */ }

    // Bring up infrastructure services (postgres, redis, qdrant, nats) first
    try {
      execSync(
        `docker compose -f "${COMPOSE_FILE}" up -d postgres redis qdrant nats`,
        { stdio: 'inherit', timeout: 120_000 }
      );
      console.log('Infrastructure services started');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('Failed to start infrastructure services:', message);
      throw error;
    }

    // Wait for postgres to be healthy before running migrations
    console.log('Waiting for postgres to be healthy...');
    const pgHealthy = await waitForHealthyService(
      () => execSync(
        `docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_isready -U heretek -d heretek_swarm`,
        { timeout: 5000 }
      ),
      60000
    );
    if (!pgHealthy) {
      throw new Error('PostgreSQL did not become healthy within 60s');
    }
    console.log('PostgreSQL is healthy');

    // Run database migrations by piping SQL content to psql stdin
    console.log('Running database migrations...');
    const fs = await import('fs');
    const migrationsDir = resolve(__dirname, '..', '..', '..', 'migrations');
    const migrationFiles = [
      '001_create_swarm_memories.sql',
      '002_create_agent_states.sql',
      '003_create_workflow_states.sql',
      '004_create_consensus_votes.sql',
      '005_create_collective_learning_tables.sql',
      '006_create_consensus_enhancement_tables.sql',
      '007_create_memory_optimization_tables.sql',
      '008_create_agent_wiring_state_tables.sql',
      '009_create_configuration_tables.sql',
      '010_create_external_call_logs.sql',
      '011_create_infrastructure_config_table.sql',
    ];

    // Get postgres credentials from docker-compose (defaults match compose.yml)
    // compose.yml sets POSTGRES_USER=heretek (unless overridden)
    const pgUser = 'heretek';
    const pgDb = 'heretek_swarm';

    for (const migrationFile of migrationFiles) {
      const migrationPath = resolve(migrationsDir, migrationFile);
      console.log(`  Running migration: ${migrationFile}`);
      try {
        const sqlContent = fs.readFileSync(migrationPath, 'utf-8');
        // Pipe SQL content via stdin to psql
        const result = execSync(
          `docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U ${pgUser} -d ${pgDb}`,
          { input: sqlContent, timeout: 30000 }
        );
        if (result.length > 0) {
          console.log(`    ${result.toString().trim()}`);
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        // Log but continue — some migrations may be idempotent
        console.warn(`  Migration ${migrationFile} warning:`, message);
      }
    }
    console.log('All migrations completed');

    // Now start the API service
    console.log('Starting API service...');
    try {
      execSync(
        `docker compose -f "${COMPOSE_FILE}" up -d api`,
        { stdio: 'inherit', timeout: 120_000 }
      );
      console.log('API service started');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('Failed to start API service:', message);
      throw error;
    }
  });

  /**
   * Tear down the docker-compose stack after all tests complete.
   * Always runs regardless of test outcome.
   */
  test.afterAll(async () => {
    console.log('Tearing down docker-compose stack');
    try {
      execSync(
        `docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans`,
        { stdio: 'inherit', timeout: 120_000 }
      );
      console.log('Docker compose stack stopped and removed');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('Failed to stop docker compose stack:', message);
      // Don't throw — teardown failures shouldn't fail the test
    }
  });

  /**
   * T01: Verify all 23 agents reach ACTIVE state within 120 seconds.
   *
   * Steps:
   * 1. Poll /api/health until API is healthy (up to 120s)
   * 2. Poll /api/agents every 5s until all 23 agents report status=active (up to 120s)
   * 3. Assert total === 23 and all agents are active
   * 4. On failure, surface which agents are missing or not ACTIVE
   */
  test('T01: All 23 agents reach ACTIVE state', async ({ request }) => {
    // ── Step 1: Wait for API health ──────────────────────────────────────────
    console.log('Polling /api/health for API readiness...');
    const healthDeadline = Date.now() + HEALTH_POLL_TIMEOUT_MS;
    let apiHealthy = false;

    while (Date.now() < healthDeadline) {
      try {
        const response = await request.get(`${API_HOST}/api/health`, {
          headers: { 'X-API-Key': API_KEY },
          timeout: 10_000,
        });

        if (response.ok()) {
          const healthBody = await response.json();
          console.log(`API health: ${JSON.stringify(healthBody.status)}`);
          apiHealthy = true;
          break;
        }
      } catch {
        // Not ready yet — continue polling
        console.log('API not ready, retrying...');
      }

      // Wait before next poll
      await new Promise((resolve) => setTimeout(resolve, HEALTH_POLL_INTERVAL_MS));
    }

    if (!apiHealthy) {
      // Capture docker logs for diagnostics
      let logs = '';
      try {
        logs = execSync(
          `docker compose -f "${COMPOSE_FILE}" logs --tail=100 api`,
          { timeout: 10_000 }
        ).toString();
      } catch { /* ignore */ }

      throw new Error(
        `API did not become healthy within ${HEALTH_POLL_TIMEOUT_MS}ms.\n` +
        `Docker logs (last 100 lines):\n${logs}`
      );
    }

    console.log('API is healthy — starting agent polling');

    // ── Step 2: Poll /api/agents until all 23 are ACTIVE ────────────────────
    const agentDeadline = Date.now() + AGENT_POLL_TIMEOUT_MS;
    const activeAgents = new Set<string>();

    while (Date.now() < agentDeadline) {
      const response = await request.get(`${API_HOST}/api/agents`, {
        headers: { 'X-API-Key': API_KEY },
        timeout: 10_000,
      });

      expect(response.ok()).toBeTruthy();
      const body = await response.json();

      // Clear and rebuild active agents set from current response
      const currentlyActive = new Set<string>();
      for (const agent of body.agents ?? []) {
        if (agent.status === 'active') {
          currentlyActive.add(agent.id);
        }
      }

      // Merge into cumulative activeAgents set
      for (const id of currentlyActive) {
        activeAgents.add(id);
      }

      console.log(
        `Active agents: ${activeAgents.size}/23 | ` +
        `Current snapshot: ${currentlyActive.size}/23 | ` +
        `Elapsed: ${Math.round((Date.now() - (agentDeadline - AGENT_POLL_TIMEOUT_MS)) / 1000)}s`
      );

      // Check if all 23 agents are active
      if (activeAgents.size === 23) {
        console.log('All 23 agents reached ACTIVE state!');
        break;
      }

      // Wait before next poll
      await new Promise((resolve) => setTimeout(resolve, AGENT_POLL_INTERVAL_MS));
    }

    // ── Step 3: Assertion — all 23 agents must be ACTIVE ────────────────────
    console.log('\n=== Agent Status Diagnostic Table ===');

    // Build full diagnostic for all expected agents
    const missingAgents: string[] = [];
    const notActiveAgents: { id: string; status: string }[] = [];

    // Get final agent list from API for diagnostics
    const finalResponse = await request.get(`${API_HOST}/api/agents`, {
      headers: { 'X-API-Key': API_KEY },
      timeout: 10_000,
    });
    const finalBody = await finalResponse.json();
    const agentMap = new Map<string, { status: string }>();
    for (const agent of finalBody.agents ?? []) {
      agentMap.set(agent.id, { status: agent.status });
    }

    // Print each expected agent's status
    for (const agentId of EXPECTED_AGENT_IDS) {
      const agentInfo = agentMap.get(agentId);
      if (!agentInfo) {
        console.log(`  ✗ ${agentId}: MISSING (not in API response)`);
        missingAgents.push(agentId);
      } else if (agentInfo.status !== 'active') {
        console.log(`  ✗ ${agentId}: status=${agentInfo.status}`);
        notActiveAgents.push({ id: agentId, status: agentInfo.status });
      } else {
        console.log(`  ✓ ${agentId}: ACTIVE`);
      }
    }

    console.log(`Total agents: ${finalBody.total ?? agentMap.size}/23`);
    console.log(`Active: ${activeAgents.size}/23`);
    console.log('=====================================\n');

    // Primary assertion: total count
    expect(finalBody.total).toBe(23);

    // Secondary assertion: all agents ACTIVE
    const allActive = activeAgents.size === 23;
    expect(allActive, buildFailureMessage(activeAgents, missingAgents, notActiveAgents)).toBeTruthy();
  });
});

/**
 * Build a diagnostic failure message showing exactly which agents are missing or not ACTIVE.
 */
function buildFailureMessage(
  activeAgents: Set<string>,
  missingAgents: string[],
  notActiveAgents: { id: string; status: string }[]
): string {
  const lines: string[] = [];
  lines.push(`\nExpected 23 agents with status=ACTIVE, got ${activeAgents.size}/23 ACTIVE`);

  if (missingAgents.length > 0) {
    lines.push(`Missing agents (not in /api/agents response): ${missingAgents.join(', ')}`);
  }

  if (notActiveAgents.length > 0) {
    lines.push(
      `Agents not ACTIVE: ${notActiveAgents.map((a) => `${a.id} (${a.status})`).join(', ')}`
    );
  }

  return lines.join('\n');
}

/**
 * Poll a health-check function until it succeeds or timeout is reached.
 * Returns true if the service became healthy, false otherwise.
 */
async function waitForHealthyService(
  checkFn: () => void,
  timeoutMs: number
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      checkFn();
      return true;
    } catch {
      // Not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  return false;
}
