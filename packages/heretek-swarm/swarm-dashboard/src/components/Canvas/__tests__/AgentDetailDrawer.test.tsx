/**
 * AgentDetailDrawer component tests
 *
 * Verifies Memory, Tools/MCP, and Tasks tab content rendering across
 * loading, error, empty, populated, and unavailable states.
 * Also verifies tab switching renders correct content.
 */

import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { AgentDetailDrawer } from '../AgentDetailDrawer';

// ── Mock data factories ─────────────────────────────────────────────────────

const makeMemoryPopulated = () => ({
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
      content: 'Deployed habit_forge agent with 3 skills at 14:22 UTC',
      memory_type: 'episodic',
      created_at: new Date(Date.now() - 60000).toISOString(),
    },
  ],
  status: 'ok',
});

const makeMemoryUnavailable = () => ({
  agent_id: 'agent-1',
  total_memories: 0,
  by_type: {},
  recent_entries: [],
  status: 'unavailable',
});

const makeMemoryEmpty = () => ({
  agent_id: 'agent-1',
  total_memories: 0,
  by_type: {},
  recent_entries: [],
  status: 'ok',
});

const makeToolsPopulated = () => ({
  agent_id: 'agent-1',
  skills: [
    {
      name: 'web_search',
      category: 'retrieval',
      description: 'Search the web for real-time information',
      version: '1.2.0',
      tags: ['search', 'web'],
      source: 'builtin',
    },
    {
      name: 'code_executor',
      category: 'execution',
      description: 'Execute code in sandbox',
      version: '2.0.1',
      tags: ['code', 'sandbox'],
      source: 'plugin',
    },
  ],
  plugins: [
    {
      name: 'weather',
      version: '1.0.0',
      description: 'Get weather forecasts',
      author: 'heretek-team',
    },
  ],
  total: 3,
});

const makeToolsEmpty = () => ({
  agent_id: 'agent-1',
  skills: [],
  plugins: [],
  total: 0,
});

const makeTasksActive = () => ({
  agent_id: 'agent-1',
  status: 'active',
  capabilities: ['web_search', 'code_execution', 'text_generation'],
  topics: ['deployment', 'monitoring'],
  message_count: 1283,
  error_count: 3,
  last_activity: new Date().toISOString(),
  uptime_seconds: 45210,
});

const makeTasksNotRunning = () => ({
  agent_id: 'agent-1',
  status: 'not_running',
  capabilities: [],
  topics: [],
  message_count: 0,
  error_count: 0,
  last_activity: null,
  uptime_seconds: null,
});

// ── Mock return value builder ────────────────────────────────────────────────

interface MockState {
  data: ReturnType<typeof useAgentDetailMock>['data'];
  loading: boolean;
  errors: Record<string, string>;
}

function buildMockReturn(overrides: Partial<MockState> = {}): ReturnType<typeof useAgentDetailMock> {
  return {
    data: null,
    loading: false,
    errors: {},
    ...overrides,
  };
}

// ── Mock the hooks ──────────────────────────────────────────────────────────

const useAgentDetailMock = vi.fn();
const useConsciousnessWebSocketMock = vi.fn();

vi.mock('../useAgentDetail', () => ({
  useAgentDetail: (agentId: string | null) => useAgentDetailMock(agentId),
}));

vi.mock('../../../hooks/useConsciousnessWebSocket', () => ({
  useConsciousnessWebSocket: () => useConsciousnessWebSocketMock(),
}));

// ── Shared setup ────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  // Default WebSocket: not connected, no agent states
  useConsciousnessWebSocketMock.mockReturnValue({
    agentStates: new Map(),
    connected: false,
  });
  // Default hook: loading with no data
  useAgentDetailMock.mockReturnValue(buildMockReturn({
    loading: true,
    data: null,
  }));
});

afterEach(() => {
  cleanup();
});

// ── Helper to render with a specific agentId ────────────────────────────────

function renderDrawer(agentId: string | null = 'agent-1', onClose = vi.fn()) {
  return render(<AgentDetailDrawer agentId={agentId} onClose={onClose} />);
}

// ── Helper to click a tab button ────────────────────────────────────────────

function clickTab(label: string) {
  const tab = screen.getByRole('tab', { name: label });
  fireEvent.click(tab);
}

// ═══════════════════════════════════════════════════════════════════════════
// Memory tab tests
// ═══════════════════════════════════════════════════════════════════════════

describe('MemoryTabContent', () => {
  it('shows skeleton placeholders when loading with no data', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: true,
      data: null,
    }));

    renderDrawer();
    clickTab('Memory');

    // Skeleton bars use animate-pulse class
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows error message when memory endpoint fails and data is null', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: null,
      errors: { memory: 'Memory service timeout' },
    }));

    renderDrawer();
    clickTab('Memory');

    expect(screen.getByText('Memory unavailable')).toBeInTheDocument();
    expect(screen.getByText('Memory service timeout')).toBeInTheDocument();
  });

  it('shows unavailable status when memory backend is not available', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: makeMemoryUnavailable(), tools: null, tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Memory');

    expect(screen.getByText('Memory backend not available')).toBeInTheDocument();
  });

  it('shows "No memories recorded" when total is 0', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: makeMemoryEmpty(), tools: null, tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Memory');

    expect(screen.getByText('No memories recorded')).toBeInTheDocument();
  });

  it('renders populated memory data with by_type breakdown and recent entries', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: makeMemoryPopulated(), tools: null, tasks: null, consciousness: null, agency: null, agent: { id: 'agent-1', type: 'steward', status: 'active' } },
    }));

    renderDrawer();
    clickTab('Memory');

    // Hero number
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('memories')).toBeInTheDocument();

    // By type heading
    expect(screen.getByText('By Type')).toBeInTheDocument();

    // Type badges — some types appear in both by_type and recent_entries,
    // so use getAllByText for duplicate types.
    const allEpisodic = screen.getAllByText('episodic');
    expect(allEpisodic.length).toBe(2); // by_type badge + recent entry badge
    const allSemantic = screen.getAllByText('semantic');
    expect(allSemantic.length).toBe(2); // by_type badge + recent entry badge
    expect(screen.getByText('procedural')).toBeInTheDocument();
    expect(screen.getByText('working')).toBeInTheDocument();
    expect(screen.getByText('declarative')).toBeInTheDocument();
    expect(screen.getByText('reflection')).toBeInTheDocument();

    // Counts
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    // Recent heading
    expect(screen.getByText('Recent')).toBeInTheDocument();

    // Recent entry content (truncated)
    expect(screen.getByText(/prefers terse error messages/)).toBeInTheDocument();
  });

  it('handles memory with status ok but no by_type keys', () => {
    const memNoTypes = {
      ...makeMemoryEmpty(),
      total_memories: 3,
      recent_entries: [
        { id: 'x', content: 'test', memory_type: 'episodic', created_at: null },
      ],
      status: 'ok',
      by_type: {},
    };

    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: memNoTypes, tools: null, tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Memory');

    // Hero shows 3
    expect(screen.getByText('3')).toBeInTheDocument();
    // Recent entry renders
    expect(screen.getByText('test')).toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Tools/MCP tab tests
// ═══════════════════════════════════════════════════════════════════════════

describe('ToolsTabContent', () => {
  it('shows skeleton placeholders when loading with no data', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: true,
      data: null,
    }));

    renderDrawer();
    clickTab('Tools/MCP');

    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows error message when tools endpoint fails and data is null', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: null,
      errors: { tools: 'Plugin registry unavailable' },
    }));

    renderDrawer();
    clickTab('Tools/MCP');

    expect(screen.getByText('Tools unavailable')).toBeInTheDocument();
    expect(screen.getByText('Plugin registry unavailable')).toBeInTheDocument();
  });

  it('shows empty state when no skills or plugins configured', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: makeToolsEmpty(), tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tools/MCP');

    expect(screen.getByText('No skills or plugins configured')).toBeInTheDocument();
  });

  it('renders populated skills and plugins', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: makeToolsPopulated(), tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tools/MCP');

    // Header count
    expect(screen.getByText('2 skills, 1 plugins')).toBeInTheDocument();

    // Skills section
    expect(screen.getByText('Skills')).toBeInTheDocument();
    expect(screen.getByText('web_search')).toBeInTheDocument();
    expect(screen.getByText('retrieval')).toBeInTheDocument();
    expect(screen.getByText('Search the web for real-time information')).toBeInTheDocument();
    expect(screen.getByText('code_executor')).toBeInTheDocument();

    // Plugins section
    expect(screen.getByText('Plugins')).toBeInTheDocument();
    expect(screen.getByText('weather')).toBeInTheDocument();
    expect(screen.getByText('heretek-team')).toBeInTheDocument();
    expect(screen.getByText('Get weather forecasts')).toBeInTheDocument();
  });

  it('renders only skills when plugins is empty', () => {
    const toolsOnlySkills = {
      ...makeToolsEmpty(),
      skills: [
        { name: 'solo_skill', category: 'misc', description: 'A lone skill', version: '1.0.0', tags: [], source: 'builtin' },
      ],
    };

    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: toolsOnlySkills, tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tools/MCP');

    expect(screen.getByText('1 skills, 0 plugins')).toBeInTheDocument();
    expect(screen.getByText('Skills')).toBeInTheDocument();
    expect(screen.getByText('solo_skill')).toBeInTheDocument();
    // Plugins heading should not be present
    expect(screen.queryByText('Plugins')).not.toBeInTheDocument();
  });

  it('renders only plugins when skills is empty', () => {
    const toolsOnlyPlugins = {
      ...makeToolsEmpty(),
      plugins: [
        { name: 'solo_plugin', version: '1.0.0', description: 'A lone plugin', author: 'author' },
      ],
    };

    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: toolsOnlyPlugins, tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tools/MCP');

    expect(screen.getByText('0 skills, 1 plugins')).toBeInTheDocument();
    expect(screen.getByText('Plugins')).toBeInTheDocument();
    expect(screen.getByText('solo_plugin')).toBeInTheDocument();
    expect(screen.queryByText('Skills')).not.toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Tasks tab tests
// ═══════════════════════════════════════════════════════════════════════════

describe('TasksTabContent', () => {
  it('shows skeleton placeholders when loading with no data', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: true,
      data: null,
    }));

    renderDrawer();
    clickTab('Tasks');

    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows error message when tasks endpoint fails and data is null', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: null,
      errors: { tasks: 'Supervisor unreachable' },
    }));

    renderDrawer();
    clickTab('Tasks');

    expect(screen.getByText('Tasks unavailable')).toBeInTheDocument();
    expect(screen.getByText('Supervisor unreachable')).toBeInTheDocument();
  });

  it('shows "Not Running" status when agent is not_running', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: null, tasks: makeTasksNotRunning(), consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tasks');

    expect(screen.getByText('Not Running')).toBeInTheDocument();
    expect(screen.getByText('Agent is not currently running')).toBeInTheDocument();
    // Still shows stat boxes even when not running — both show 0
    const allZeros = screen.getAllByText('0');
    expect(allZeros.length).toBeGreaterThanOrEqual(2); // messages + errors
  });

  it('renders active status with message_count, error_count, capabilities, uptime', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: null, tasks: makeTasksActive(), consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tasks');

    // Status badge — "Active" (capitalized)
    expect(screen.getByText('Active')).toBeInTheDocument();

    // Stat boxes
    expect(screen.getByText('1283')).toBeInTheDocument(); // message_count
    expect(screen.getByText('3')).toBeInTheDocument(); // error_count
    expect(screen.getByText('Messages')).toBeInTheDocument();
    expect(screen.getByText('Errors')).toBeInTheDocument();

    // Capabilities heading
    expect(screen.getByText('Capabilities')).toBeInTheDocument();
    expect(screen.getByText('web_search')).toBeInTheDocument();
    expect(screen.getByText('code_execution')).toBeInTheDocument();
    expect(screen.getByText('text_generation')).toBeInTheDocument();

    // Uptime
    expect(screen.getByText('Uptime')).toBeInTheDocument();
    expect(screen.getByText('12 hours, 33 minutes')).toBeInTheDocument();

    // Last Activity
    expect(screen.getByText('Last Activity')).toBeInTheDocument();
  });

  it('shows "Running" badge when status is "running"', () => {
    const tasksRunning = { ...makeTasksActive(), status: 'running' };
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: null, tasks: tasksRunning, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tasks');

    expect(screen.getByText('Running')).toBeInTheDocument();
    // Does NOT show "not currently running" message
    expect(screen.queryByText('Agent is not currently running')).not.toBeInTheDocument();
  });

  it('shows "Stopped" badge with correct color when status is stopped', () => {
    const tasksStopped = { ...makeTasksActive(), status: 'stopped' };
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: null, tasks: tasksStopped, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tasks');

    expect(screen.getByText('Stopped')).toBeInTheDocument();
    // Stopped is not "running" or "active", so shows not-running message
    expect(screen.getByText('Agent is not currently running')).toBeInTheDocument();
  });

  it('shows "Error" badge when tasks status is error', () => {
    const tasksError = { ...makeTasksActive(), status: 'error' };
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: null, tasks: tasksError, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tasks');

    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('renders uptime as "—" when null', () => {
    const tasksNoUptime = { ...makeTasksActive(), uptime_seconds: null };
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: null, tasks: tasksNoUptime, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tasks');

    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('renders last activity as "—" when null', () => {
    const tasksNoActivity = { ...makeTasksActive(), last_activity: null };
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: null, tasks: tasksNoActivity, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tasks');

    // "—" should appear in the Last Activity row
    const lastActivityRow = screen.getByText('Last Activity').parentElement;
    expect(lastActivityRow?.textContent).toContain('—');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Tab switching tests
// ═══════════════════════════════════════════════════════════════════════════

describe('Tab switching', () => {
  it('starts on Consciousness tab by default', () => {
    renderDrawer();

    const consciousnessTab = screen.getByRole('tab', { name: 'Consciousness' });
    expect(consciousnessTab.getAttribute('aria-selected')).toBe('true');

    // Memory/Tools/Tasks tabs should not be selected
    expect(screen.getByRole('tab', { name: 'Memory' }).getAttribute('aria-selected')).toBe('false');
    expect(screen.getByRole('tab', { name: 'Tools/MCP' }).getAttribute('aria-selected')).toBe('false');
    expect(screen.getByRole('tab', { name: 'Tasks' }).getAttribute('aria-selected')).toBe('false');
  });

  it('switches to Memory tab and renders memory content', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: makeMemoryPopulated(), tools: null, tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Memory');

    // Memory tab is now selected
    expect(screen.getByRole('tab', { name: 'Memory' }).getAttribute('aria-selected')).toBe('true');
    // Memory data renders
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('By Type')).toBeInTheDocument();
  });

  it('switches to Tools tab and renders tools content', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: makeToolsPopulated(), tasks: null, consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tools/MCP');

    expect(screen.getByRole('tab', { name: 'Tools/MCP' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByText('Skills')).toBeInTheDocument();
    expect(screen.getByText('Plugins')).toBeInTheDocument();
  });

  it('switches to Tasks tab and renders tasks content', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: { memory: null, tools: null, tasks: makeTasksActive(), consciousness: null, agency: null, agent: null },
    }));

    renderDrawer();
    clickTab('Tasks');

    expect(screen.getByRole('tab', { name: 'Tasks' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('1283')).toBeInTheDocument();
  });

  it('cycles through all tabs and renders correct content for each', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: {
        memory: makeMemoryPopulated(),
        tools: makeToolsPopulated(),
        tasks: makeTasksActive(),
        consciousness: null,
        agency: null,
        agent: { id: 'agent-1', type: 'steward', status: 'active' },
      },
    }));

    renderDrawer();

    // Consciousness (default) → loading state with no consciousness data shows "No metrics available"
    // But let's move to Memory tab
    clickTab('Memory');
    expect(screen.getByText('memories')).toBeInTheDocument();

    clickTab('Tools/MCP');
    expect(screen.getByText('Skills')).toBeInTheDocument();

    clickTab('Tasks');
    expect(screen.getByText('Active')).toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Drawer shell tests
// ═══════════════════════════════════════════════════════════════════════════

describe('AgentDetailDrawer shell', () => {
  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    renderDrawer('agent-1', onClose);

    const closeButton = screen.getByRole('button', { name: 'Close agent detail drawer' });
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('displays agent type in the header when agent data is available', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: false,
      data: {
        memory: null,
        tools: null,
        tasks: null,
        consciousness: null,
        agency: null,
        agent: { id: 'agent-1', type: 'steward', status: 'active' },
      },
    }));

    renderDrawer();

    expect(screen.getByText('steward')).toBeInTheDocument();
  });

  it('shows polling indicator in footer', () => {
    renderDrawer();

    expect(screen.getByText('Polling every 10s')).toBeInTheDocument();
  });

  it('shows "Refreshing…" when loading with existing data', () => {
    useAgentDetailMock.mockReturnValue(buildMockReturn({
      loading: true,
      data: {
        memory: null, tools: null, tasks: null,
        consciousness: null, agency: null,
        agent: { id: 'agent-1', type: 'steward', status: 'active' },
      },
    }));

    renderDrawer();

    expect(screen.getByText('Refreshing…')).toBeInTheDocument();
  });
});
