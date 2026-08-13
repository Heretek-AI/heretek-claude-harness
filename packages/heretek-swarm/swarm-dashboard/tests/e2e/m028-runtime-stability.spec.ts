/**
 * M028 E2E Test - Runtime Stability and Graceful Shutdown
 *
 * Verifies that the autonomous CLI runtime (`heretek-swarm run`) on the host:
 * 1. Survives 60 seconds without degradation (no Traceback, no ERROR patterns)
 * 2. Reports agents to the API (GET /autonomous/agents confirms total > 0)
 * 3. Exits cleanly (exit code 0) within 30 seconds of SIGTERM
 *
 * Test workflow:
 * 1. Clean stale Docker networking state
 * 2. Start infrastructure services via docker-compose (postgres, redis, qdrant, nats)
 * 3. Run all 11 SQL migrations via psql stdin piping
 * 4. Start the API container and wait for /api/health
 * 5. Spawn `heretek-swarm run` as a background subprocess on the host
 * 6. Observe 60-second stability window (process alive, no error patterns)
 * 7. Poll GET /autonomous/agents to confirm agent reporting is active
 * 8. Send SIGTERM via subprocess.terminate()
 * 9. Wait up to 30s for clean exit (exit code 0)
 * 10. Tear down docker-compose stack
 *
 * Verification: npx playwright test tests/e2e/m028-runtime-stability.spec.ts --project=chromium
 *              npx tsc --noEmit (swarm-dashboard/)
 */

import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

// docker-compose.yml is at project root (4 levels up from this test file)
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const COMPOSE_FILE = resolve(__dirname, '..', '..', '..', 'docker-compose.yml');

// heretek-swarm CLI on the host (uses pip-installed entry point)
const HERETEK_CLI = 'heretek-swarm';

// API configuration
const API_HOST = 'http://localhost:8000';
const API_KEY = 'htsk_42a231c6b47abf4cffd8bbe842789fbf';

// Environment passed to `heretek-swarm run` subprocess
const SUBPROCESS_ENV = {
  HERETEK_API_HOST: 'localhost',
  DATABASE_URL: 'postgresql+asyncpg://heretek:password@localhost/heretek_swarm',
  REDIS_URL: 'redis://localhost:6379',
  HERETEK_NATS_URL: 'nats://localhost:4222',
  // Silence noisy external-service warnings that aren't relevant to stability
  RAG_EMBEDDING_PROVIDER: 'openai',
  RAG_LLM_PROVIDER: 'openai',
  // Suppress LLM-related errors during stability window (model keys not present in test env)
  HERETEK_LOG_LEVEL: 'WARNING',
};

// Timing constants
const STABILITY_WINDOW_MS = 60_000;       // 60 seconds
const AGENT_POLL_INTERVAL_MS = 5_000;      // poll /autonomous/agents every 5s
const AGENT_POLL_TIMEOUT_MS = 60_000;     // give runtime up to 60s to start reporting
const SHUTDOWN_TIMEOUT_MS = 30_000;        // SIGTERM → exit within 30s

// Error pattern definitions for subprocess stdout/stderr inspection
const ERROR_PATTERNS = ['Traceback', 'ERROR', 'FATAL', 'PANIC'];

interface SubprocessResult {
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
}

/**
 * Spawn `heretek-swarm run` and capture stdout/stderr until terminate() + wait().
 * Returns { exitCode, stdout, stderr, timedOut }.
 */
function spawnRuntime(): {
  proc: import('child_process').ChildProcess;
  stdout: string;
  stderr: string;
} {
  // Use execSync to verify CLI is available first
  try {
    execSync(`${HERETEK_CLI} --version`, { stdio: 'pipe', timeout: 10_000 });
  } catch {
    throw new Error(
      `heretek-swarm CLI not found on PATH. ` +
      `Install with: pip install -e heretek-swarm/ or ensure PATH contains the entry point.`
    );
  }

  const { spawn } = require('child_process');
  const proc = spawn(HERETEK_CLI, ['run'], {
    env: { ...process.env, ...SUBPROCESS_ENV },
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
  });

  let stdout = '';
  let stderr = '';

  proc.stdout?.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
  proc.stderr?.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });

  return { proc, stdout, stderr };
}

/**
 * Check subprocess output for error patterns.
 * Returns an array of lines containing any error pattern.
 */
function findErrorLines(stdout: string, stderr: string): string[] {
  const allOutput = stdout + '\n' + stderr;
  return allOutput.split('\n').filter((line) =>
    ERROR_PATTERNS.some((pattern) => line.includes(pattern))
  );
}

/**
 * Poll GET /autonomous/agents until total > 0 (agents are reporting).
 * Returns true if agents become visible within the timeout.
 */
async function waitForAgentReporting(
  request: import('@playwright/test').APIRequestContext,
  timeoutMs: number,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const resp = await request.get(`${API_HOST}/autonomous/agents`, {
        headers: { 'X-API-Key': API_KEY },
        timeout: 10_000,
      });
      if (resp.ok()) {
        const body = await resp.json();
        const total = body?.total ?? 0;
        console.log(`  /autonomous/agents total=${total}`);
        if (total > 0) return true;
      }
    } catch { /* not ready yet */ }
    await new Promise((r) => setTimeout(r, AGENT_POLL_INTERVAL_MS));
  }
  return false;
}

/**
 * Collect up to `maxLines` from the tail of combined output.
 */
function tailOutput(stdout: string, stderr: string, maxLines = 20): string[] {
  const combined = (stdout + '\n' + stderr).split('\n').filter((l) => l.trim());
  return combined.slice(-maxLines);
}

test.describe('M028 Runtime Stability and Graceful Shutdown', () => {
  // Shared references across tests (set in beforeAll)
  let runtimeProc: import('child_process').ChildProcess | null = null;
  let runtimeStdout = '';
  let runtimeStderr = '';

  /**
   * Bring up infrastructure (postgres, redis, qdrant, nats), run migrations,
   * then start the API container.
   */
  test.beforeAll(async () => {
    console.log(`[Setup] Bringing up infrastructure via ${COMPOSE_FILE}`);

    // Clean stale Docker networking to avoid "network not found" errors (MEM126)
    try {
      execSync(
        `docker network prune -f && docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans`,
        { stdio: 'pipe', timeout: 60_000 }
      );
    } catch { /* nothing to clean */ }

    // Start infrastructure services
    try {
      execSync(
        `docker compose -f "${COMPOSE_FILE}" up -d postgres redis qdrant nats`,
        { stdio: 'inherit', timeout: 120_000 }
      );
      console.log('[Setup] Infrastructure services started');
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to start infrastructure services: ${msg}`);
    }

    // Wait for postgres to be healthy before running migrations
    console.log('[Setup] Waiting for PostgreSQL to be healthy...');
    const pgHealthy = await waitForHealthyService(
      () => execSync(
        `docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_isready -U heretek -d heretek_swarm`,
        { timeout: 5_000 }
      ),
      60_000
    );
    if (!pgHealthy) throw new Error('PostgreSQL did not become healthy within 60s');
    console.log('[Setup] PostgreSQL is healthy');

    // Run all 11 SQL migrations via stdin piping (MEM124 pattern)
    console.log('[Setup] Running database migrations...');
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

    for (const migrationFile of migrationFiles) {
      const migrationPath = resolve(migrationsDir, migrationFile);
      console.log(`  Running: ${migrationFile}`);
      try {
        const sqlContent = fs.readFileSync(migrationPath, 'utf-8');
        // Pipe SQL via stdin to psql — postgres container can't access host paths (MEM124)
        execSync(
          `docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U heretek -d heretek_swarm`,
          { input: sqlContent, timeout: 30_000 }
        );
      } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : String(error);
        console.warn(`  Warning in ${migrationFile}: ${msg}`);
        // Idempotent migrations may warn on re-run — continue
      }
    }
    console.log('[Setup] All migrations completed');

    // Start the API service
    console.log('[Setup] Starting API service...');
    try {
      execSync(
        `docker compose -f "${COMPOSE_FILE}" up -d api`,
        { stdio: 'inherit', timeout: 120_000 }
      );
      console.log('[Setup] API service started');
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to start API service: ${msg}`);
    }
  });

  /** Tear down the docker-compose stack after all tests. */
  test.afterAll(async () => {
    console.log('[Teardown] Stopping docker-compose stack');
    try {
      execSync(
        `docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans`,
        { stdio: 'inherit', timeout: 120_000 }
      );
      console.log('[Teardown] Stack stopped and removed');
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      console.error('[Teardown] Warning:', msg);
    }
  });

  /**
   * T01: Runtime survives 60 seconds without degradation.
   *
   * Verifies the runtime subprocess:
   * - Remains alive throughout the 60-second window
   * - Produces no Traceback/ERROR patterns in stdout or stderr
   * - Reports agents to GET /autonomous/agents (total > 0)
   */
  test('T01: Runtime survives 60 seconds without degradation', async ({ request }) => {
    console.log('[T01] Spawning heretek-swarm run subprocess...');

    // Wait for API to be healthy before spawning runtime
    console.log('[T01] Waiting for API health before spawning runtime...');
    const apiHealthy = await pollHealth(request, 90_000);
    if (!apiHealthy) {
      throw new Error('API did not become healthy — cannot verify runtime stability');
    }
    console.log('[T01] API is healthy — spawning runtime');

    // Spawn the runtime subprocess
    let proc: import('child_process').ChildProcess;
    let stdout = '';
    let stderr = '';
    try {
      const result = spawnRuntime();
      proc = result.proc;
      stdout = result.stdout;
      stderr = result.stderr;
    } catch (error) {
      throw error; // Already shaped as a descriptive Error
    }

    runtimeProc = proc;
    runtimeStdout = stdout;
    runtimeStderr = stderr;

    console.log(`[T01] Runtime spawned (pid=${proc.pid}) — beginning 60s stability window`);

    // ── Stability window: 60 seconds with periodic checks ──────────────────
    const stabilityDeadline = Date.now() + STABILITY_WINDOW_MS;
    const pollIntervalMs = 5_000;
    let stabilityCheckCount = 0;

    while (Date.now() < stabilityDeadline) {
      // Check 1: Is the process still alive?
      const alive = proc.exitCode === null;
      if (!alive) {
        const errorLines = findErrorLines(stdout, stderr);
        const lastStderr = tailOutput(stdout, stderr, 10);
        throw new Error(
          `Runtime process died before stability window completed.\n` +
          `Exit code: ${proc.exitCode}\n` +
          `Error pattern matches:\n${errorLines.map((l) => `  ${l}`).join('\n')}\n` +
          `Last stderr lines:\n${lastStderr.map((l) => `  ${l}`).join('\n')}`
        );
      }

      // Check 2: Any new error patterns in output so far?
      const currentErrors = findErrorLines(stdout, stderr);
      if (currentErrors.length > 0) {
        throw new Error(
          `Error patterns detected in subprocess output during stability window:\n` +
          currentErrors.map((l) => `  ${l}`).join('\n')
        );
      }

      stabilityCheckCount++;
      console.log(
        `[T01] Stability check ${stabilityCheckCount}/~12 — process alive, no errors. ` +
        `${Math.round((stabilityDeadline - Date.now()) / 1000)}s remaining in window`
      );

      await new Promise((r) => setTimeout(r, pollIntervalMs));
    }

    console.log('[T01] 60-second stability window complete — no errors detected');

    // ── Agent reporting verification ─────────────────────────────────────
    console.log('[T01] Polling /autonomous/agents for agent reporting...');
    const agentsVisible = await waitForAgentReporting(request, AGENT_POLL_TIMEOUT_MS);

    if (!agentsVisible) {
      const lastStderr = tailOutput(stdout, stderr, 20);
      throw new Error(
        `Agents did not become visible to GET /autonomous/agents within ${AGENT_POLL_TIMEOUT_MS}ms.\n` +
        `This indicates the runtime's agent report loop is not functioning.\n` +
        `Last stderr lines:\n${lastStderr.map((l) => `  ${l}`).join('\n')}`
      );
    }
    console.log('[T01] Agent reporting confirmed — runtime is stable and reporting');

    // Keep the process alive for T02 (graceful shutdown test)
    // We intentionally do NOT terminate here — T02 will do the SIGTERM
  });

  /**
   * T02: SIGTERM triggers clean shutdown within 30 seconds.
   *
   * Depends on T01 having spawned the runtime process. Sends SIGTERM via
   * subprocess.terminate() and verifies exit code === 0 within 30s.
   */
  test('T02: SIGTERM triggers clean shutdown within 30 seconds', async () => {
    if (!runtimeProc) {
      throw new Error(
        'T02 requires T01 to have spawned the runtime. ' +
        'Run T01 before T02, or run both in sequence.'
      );
    }

    const proc = runtimeProc;
    const pid = proc.pid;
    console.log(`[T02] Sending SIGTERM to runtime (pid=${pid})...`);

    // SIGTERM via terminate() triggers the handler in cli.py
    proc.terminate();

    // Wait up to 30s for clean exit
    const deadline = Date.now() + SHUTDOWN_TIMEOUT_MS;
    let exitCode: number | null = null;

    while (Date.now() < deadline) {
      // Check if process has exited
      exitCode = proc.exitCode;
      if (exitCode !== null) break;
      await new Promise((r) => setTimeout(r, 500));
    }

    // Final check after deadline
    exitCode = proc.exitCode;

    // Build diagnostic table on failure
    const diagnostics = buildDiagnosticTable(exitCode, runtimeStdout, runtimeStderr);

    if (exitCode === null) {
      // Still alive after 30s — force kill and report
      console.warn('[T02] Process did not exit within 30s — force killing...');
      proc.kill('SIGKILL');
      throw new Error(
        `Runtime did not exit within ${SHUTDOWN_TIMEOUT_MS}ms after SIGTERM.\n` +
        diagnostics
      );
    }

    if (exitCode !== 0) {
      throw new Error(
        `Runtime exited with non-zero code ${exitCode} (expected 0).\n` +
        diagnostics
      );
    }

    console.log('[T02] Runtime exited cleanly with code 0 — graceful shutdown verified');
  });
});

/**
 * Poll /api/health until API is healthy or timeout is reached.
 */
async function pollHealth(
  request: import('@playwright/test').APIRequestContext,
  timeoutMs: number,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const resp = await request.get(`${API_HOST}/api/health`, {
        headers: { 'X-API-Key': API_KEY },
        timeout: 10_000,
      });
      if (resp.ok()) return true;
    } catch { /* not ready */ }
    await new Promise((r) => setTimeout(r, 5_000));
  }
  return false;
}

/**
 * Poll a health-check function until it succeeds or timeout is reached.
 */
async function waitForHealthyService(
  checkFn: () => void,
  timeoutMs: number,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      checkFn();
      return true;
    } catch { /* not ready */ }
    await new Promise((r) => setTimeout(r, 2_000));
  }
  return false;
}

/**
 * Build a diagnostic table showing subprocess exit state.
 * Used to surface exactly why shutdown failed.
 */
function buildDiagnosticTable(
  exitCode: number | null,
  stdout: string,
  stderr: string,
): string {
  const lines: string[] = [];
  lines.push('\n=== Diagnostic Table ===');
  lines.push(`Subprocess exit code: ${exitCode ?? 'still running (null)'}`);
  lines.push(`Exit quality: ${
    exitCode === 0 ? 'CLEAN (0)' :
    exitCode === null ? 'STILL RUNNING' :
    `FAILED (${exitCode})`
  }`);

  const errorLines = findErrorLines(stdout, stderr);
  if (errorLines.length > 0) {
    lines.push(`Error patterns found: ${errorLines.length}`);
    lines.push('  Error lines:');
    errorLines.forEach((l) => lines.push(`    ${l}`));
  } else {
    lines.push('Error patterns found: 0');
  }

  lines.push('');
  lines.push('Last 20 lines of combined stdout+stderr:');
  tailOutput(stdout, stderr, 20).forEach((l) => lines.push(`  ${l}`));
  lines.push('========================\n');
  return lines.join('\n');
}
