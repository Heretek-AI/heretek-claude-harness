/**
 * useAgentDetail Hook Tests
 *
 * Tests for the useAgentDetail polling hook covering:
 * - Skeleton/loading state when agentId is set
 * - Graceful "No metrics" on consciousness 404
 * - Polling stops when agentId becomes null (drawer closed)
 * - Polling restarts when agentId changes to a different agent
 * - Individual section errors don't crash other sections (Promise.allSettled)
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useAgentDetail } from '../../components/Canvas/useAgentDetail';

// ─── Mock the consciousness API module ────────────────────────────────────────
vi.mock('../../api/consciousness', () => ({
  getAgentMetrics: vi.fn(),
  getAgencyMetrics: vi.fn(),
}));

// ─── Mock the agents API module ───────────────────────────────────────────────
vi.mock('../../api/agents', () => ({
  getAgent: vi.fn(),
  getAgentMemory: vi.fn(),
  getAgentTools: vi.fn(),
  getAgentTasks: vi.fn(),
}));

// ─── Import mocked modules ────────────────────────────────────────────────────
import { getAgentMetrics, getAgencyMetrics } from '../../api/consciousness';
import { getAgent, getAgentMemory, getAgentTools, getAgentTasks } from '../../api/agents';

const mockedGetAgentMetrics = vi.mocked(getAgentMetrics);
const mockedGetAgencyMetrics = vi.mocked(getAgencyMetrics);
const mockedGetAgent = vi.mocked(getAgent);
const mockedGetAgentMemory = vi.mocked(getAgentMemory);
const mockedGetAgentTools = vi.mocked(getAgentTools);
const mockedGetAgentTasks = vi.mocked(getAgentTasks);

// ─── Mock data factories ─────────────────────────────────────────────────────
const mockAgentMetrics = {
  agent_id: 'agent-1',
  phi_score: 0.723,
  fep_metrics: {
    free_energy: 0.142,
    prediction_accuracy: 0.891,
    surprise: 0.033,
    belief_precision: 0.678,
  },
  state: 'coherent' as const,
  timestamp: new Date().toISOString(),
};

const mockAgencyMetrics = {
  agency_score: 0.847,
  autonomy_score: 0.623,
  decision_count: 42,
  last_decision: new Date().toISOString(),
};

const mockAgentInfo = {
  id: 'agent-1',
  type: 'steward',
  status: 'active',
  lastActivity: new Date().toISOString(),
};

const mockAgentMemory = {
  agent_id: 'agent-1',
  total_memories: 42,
  by_type: {
    episodic: 12,
    semantic: 8,
    procedural: 10,
    working: 5,
    declarative: 4,
    reflection: 3,
  },
  recent_entries: [
    {
      id: 'mem-001',
      content: 'The user prefers terse error messages with actionable next steps',
      memory_type: 'semantic',
      created_at: new Date().toISOString(),
    },
    {
      id: 'mem-002',
      content: 'Deployed habit_forge agent with 3 skills at 14:22 UTC — startup succeeded',
      memory_type: 'episodic',
      created_at: new Date(Date.now() - 60000).toISOString(),
    },
    {
      id: 'mem-003',
      content: 'Reflection on last 5 interactions: response latency improved by 200ms after switching to streaming',
      memory_type: 'reflection',
      created_at: new Date(Date.now() - 300000).toISOString(),
    },
  ],
  status: 'ok',
};

const mockAgentTools = {
  agent_id: 'agent-1',
  skills: [
    {
      name: 'web_search',
      category: 'retrieval',
      description: 'Search the web for real-time information',
      version: '1.2.0',
      tags: ['search', 'web', 'information'],
      source: 'builtin',
    },
    {
      name: 'code_executor',
      category: 'execution',
      description: 'Execute code in a sandboxed environment',
      version: '2.0.1',
      tags: ['code', 'execution', 'sandbox'],
      source: 'plugin',
    },
    {
      name: 'data_analyzer',
      category: 'analysis',
      description: 'Analyze structured data and produce summaries',
      version: '0.9.3',
      tags: ['data', 'analysis', 'statistics'],
      source: 'builtin',
    },
  ],
  plugins: [
    {
      name: 'weather',
      version: '1.0.0',
      description: 'Retrieve current weather and forecasts',
      author: 'heretek-team',
    },
    {
      name: 'calendar',
      version: '2.1.0',
      description: 'Manage calendar events and reminders',
      author: 'heretek-team',
    },
  ],
  total: 5,
};

const mockAgentTasks = {
  agent_id: 'agent-1',
  status: 'active',
  capabilities: ['web_search', 'code_execution', 'text_generation'],
  topics: ['deployment', 'monitoring', 'alerts'],
  message_count: 1283,
  error_count: 3,
  last_activity: new Date().toISOString(),
  uptime_seconds: 45210,
};

// ─── Shared setup ─────────────────────────────────────────────────────────────
beforeEach(() => {
  vi.clearAllMocks();
  // Default: all calls succeed
  mockedGetAgentMetrics.mockResolvedValue(mockAgentMetrics);
  mockedGetAgencyMetrics.mockResolvedValue(mockAgencyMetrics);
  mockedGetAgent.mockResolvedValue(mockAgentInfo);
  mockedGetAgentMemory.mockResolvedValue(mockAgentMemory);
  mockedGetAgentTools.mockResolvedValue(mockAgentTools);
  mockedGetAgentTasks.mockResolvedValue(mockAgentTasks);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('useAgentDetail', () => {
  it('renders with skeleton when agentId is set (loading state)', async () => {
    // Make the call hang so we can observe loading=true before it resolves
    let resolveMetrics: (value: typeof mockAgentMetrics) => void;
    mockedGetAgentMetrics.mockImplementation(
      () => new Promise((r) => { resolveMetrics = r; })
    );

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    // Before any promise resolves, loading should be true (skeleton shown)
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);

    // Resolve and wait for state update
    await act(async () => {
      resolveMetrics!(mockAgentMetrics);
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data?.consciousness?.phi_score).toBeCloseTo(0.723);
  });

  it('shows graceful "no metrics yet" when consciousness endpoint returns 404', async () => {
    // Mock 404 — axios throws an error with the response object attached
    mockedGetAgentMetrics.mockRejectedValue(
      Object.assign(new Error('Request failed with status code 404'), {
        response: { status: 404 },
      })
    );
    mockedGetAgencyMetrics.mockResolvedValue(mockAgencyMetrics);
    mockedGetAgent.mockResolvedValue(mockAgentInfo);

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // 404 → consciousness is null (not an error), agency still populated
    expect(result.current.data?.consciousness).toBe(null);
    expect(result.current.data?.agency?.agency_score).toBeCloseTo(0.847);
    // No consciousness error key (404 is graceful null)
    expect(result.current.errors.consciousness).toBeUndefined();
  });

  it('polling stops when agentId becomes null (drawer closed)', async () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useAgentDetail(id),
      { initialProps: { id: 'agent-1' } }
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    const callsBefore = mockedGetAgentMetrics.mock.calls.length;

    // Simulate drawer close → agentId becomes null
    rerender({ id: null });

    // State should reset immediately
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBe(null);

    // Advance time well past the 10s polling interval — no new calls should fire
    await act(async () => {
      await new Promise((r) => setTimeout(r, 200));
    });

    expect(mockedGetAgentMetrics.mock.calls.length).toBe(callsBefore);
  });

  it('polling restarts when agentId changes to a different agent', async () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useAgentDetail(id),
      { initialProps: { id: 'agent-1' } }
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    const callsForAgent1 = mockedGetAgentMetrics.mock.calls.length;

    // Switch to a different agent
    rerender({ id: 'agent-2' });

    // Should immediately start fetching (loading resets)
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // New calls should have been made for agent-2
    const newCalls = mockedGetAgentMetrics.mock.calls.slice(callsForAgent1);
    expect(newCalls.length).toBeGreaterThan(0);
  });

  it('individual section errors do not crash other sections (Promise.allSettled)', async () => {
    // consciousness fails hard, agency succeeds, agent succeeds
    mockedGetAgentMetrics.mockRejectedValue(new Error('Network error'));
    mockedGetAgencyMetrics.mockRejectedValue(new Error('Agency network error'));
    mockedGetAgent.mockResolvedValue(mockAgentInfo);

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Both sections should have recorded errors
    expect(result.current.errors.consciousness).toBe('Network error');
    expect(result.current.errors.agency).toBe('Agency network error');
    // Agent succeeded despite the other failures
    expect(result.current.data?.agent?.type).toBe('steward');
    expect(result.current.data?.agency).toBe(null); // agency failed → null
    expect(result.current.data?.consciousness).toBe(null); // consciousness failed → null
  });

  it('gracefully handles partial failures — agency 404, consciousness ok', async () => {
    mockedGetAgentMetrics.mockResolvedValue(mockAgentMetrics);
    mockedGetAgencyMetrics.mockRejectedValue(
      Object.assign(new Error('Request failed with status code 404'), {
        response: { status: 404 },
      })
    );
    mockedGetAgent.mockResolvedValue(mockAgentInfo);

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Consciousness succeeded
    expect(result.current.data?.consciousness?.phi_score).toBeCloseTo(0.723);
    // Agency failed with 404
    expect(result.current.data?.agency).toBe(null);
    expect(result.current.errors.agency).toBe('Request failed with status code 404');
  });

  // ─── Memory / Tools / Tasks ────────────────────────────────────────────

  it('memory/tools/tasks data flows through to return value', async () => {
    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Memory data
    expect(result.current.data?.memory).not.toBeNull();
    expect(result.current.data?.memory?.agent_id).toBe('agent-1');
    expect(result.current.data?.memory?.total_memories).toBe(42);
    expect(result.current.data?.memory?.by_type?.episodic).toBe(12);
    expect(result.current.data?.memory?.recent_entries).toHaveLength(3);

    // Tools data
    expect(result.current.data?.tools).not.toBeNull();
    expect(result.current.data?.tools?.agent_id).toBe('agent-1');
    expect(result.current.data?.tools?.skills).toHaveLength(3);
    expect(result.current.data?.tools?.plugins).toHaveLength(2);
    expect(result.current.data?.tools?.total).toBe(5);

    // Tasks data
    expect(result.current.data?.tasks).not.toBeNull();
    expect(result.current.data?.tasks?.agent_id).toBe('agent-1');
    expect(result.current.data?.tasks?.status).toBe('active');
    expect(result.current.data?.tasks?.message_count).toBe(1283);
    expect(result.current.data?.tasks?.error_count).toBe(3);
    expect(result.current.data?.tasks?.uptime_seconds).toBe(45210);
    expect(result.current.data?.tasks?.capabilities).toContain('web_search');

    // No errors for any endpoint
    expect(result.current.errors.memory).toBeUndefined();
    expect(result.current.errors.tools).toBeUndefined();
    expect(result.current.errors.tasks).toBeUndefined();
  });

  it('404 on memory endpoint returns graceful null (no error key)', async () => {
    mockedGetAgentMemory.mockRejectedValue(
      Object.assign(new Error('Request failed with status code 404'), {
        response: { status: 404 },
      })
    );

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // 404 → null, not an error
    expect(result.current.data?.memory).toBe(null);
    expect(result.current.errors.memory).toBeUndefined();
    // Other endpoints still populated
    expect(result.current.data?.tools?.skills).toHaveLength(3);
    expect(result.current.data?.tasks?.status).toBe('active');
  });

  it('404 on tools endpoint returns graceful null', async () => {
    mockedGetAgentTools.mockRejectedValue(
      Object.assign(new Error('Request failed with status code 404'), {
        response: { status: 404 },
      })
    );

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data?.tools).toBe(null);
    expect(result.current.errors.tools).toBeUndefined();
  });

  it('404 on tasks endpoint returns graceful null', async () => {
    mockedGetAgentTasks.mockRejectedValue(
      Object.assign(new Error('Request failed with status code 404'), {
        response: { status: 404 },
      })
    );

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data?.tasks).toBe(null);
    expect(result.current.errors.tasks).toBeUndefined();
  });

  it('individual memory endpoint failure does not crash others (allSettled)', async () => {
    mockedGetAgentMemory.mockRejectedValue(new Error('Memory service timeout'));
    // tools and tasks still succeed

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Memory failed hard — not 404, so it's an error
    expect(result.current.data?.memory).toBe(null);
    expect(result.current.errors.memory).toBe('Memory service timeout');

    // Other three (tools, tasks, agent, consciousness, agency) still succeed
    expect(result.current.data?.tools).not.toBeNull();
    expect(result.current.data?.tools?.skills).toHaveLength(3);
    expect(result.current.data?.tasks).not.toBeNull();
    expect(result.current.data?.tasks?.status).toBe('active');
    expect(result.current.data?.consciousness?.phi_score).toBeCloseTo(0.723);
    expect(result.current.data?.agent?.type).toBe('steward');
  });

  it('all three new endpoints populate with valid response shapes', async () => {
    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Verify memory response shape
    const mem = result.current.data?.memory;
    expect(mem).toMatchObject({
      agent_id: expect.any(String),
      total_memories: expect.any(Number),
      by_type: expect.any(Object),
      recent_entries: expect.any(Array),
      status: expect.any(String),
    });

    // Verify tools response shape
    const tools = result.current.data?.tools;
    expect(tools).toMatchObject({
      agent_id: expect.any(String),
      skills: expect.any(Array),
      plugins: expect.any(Array),
      total: expect.any(Number),
    });

    // Verify tasks response shape
    const tasks = result.current.data?.tasks;
    expect(tasks).toMatchObject({
      agent_id: expect.any(String),
      status: expect.any(String),
      capabilities: expect.any(Array),
      message_count: expect.any(Number),
      error_count: expect.any(Number),
      uptime_seconds: expect.any(Number),
    });
  });

  it('memory/tools/tasks errors are preserved in errors map when non-404', async () => {
    mockedGetAgentMemory.mockRejectedValue(new Error('DB connection lost'));
    mockedGetAgentTools.mockRejectedValue(new Error('Plugin registry unavailable'));
    mockedGetAgentTasks.mockRejectedValue(new Error('Supervisor unreachable'));

    const { result } = renderHook(() => useAgentDetail('agent-1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.errors.memory).toBe('DB connection lost');
    expect(result.current.errors.tools).toBe('Plugin registry unavailable');
    expect(result.current.errors.tasks).toBe('Supervisor unreachable');
    expect(result.current.data?.memory).toBe(null);
    expect(result.current.data?.tools).toBe(null);
    expect(result.current.data?.tasks).toBe(null);
  });
});
