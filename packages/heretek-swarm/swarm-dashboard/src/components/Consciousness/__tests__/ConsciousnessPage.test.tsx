/**
 * ConsciousnessPage component tests
 *
 * Verifies the dashboard page correctly integrates with the consciousness WebSocket hook,
 * renders gauge metrics from live agent states, shows REST-fetched statistics, and
 * handles loading / error / empty states.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('../../../api/consciousness', () => ({
  getConsciousnessStatistics: vi.fn(),
  getAgentStates: vi.fn(),
  getNetworkVisualization: vi.fn(),
}));

const mockWsReturn: {
  agentStates: Map<string, import('../../../hooks/useConsciousnessWebSocket').ConsciousnessAgentState>;
  connected: boolean;
  error: null;
  disconnect: () => void;
} = {
  agentStates: new Map(),
  connected: true,
  error: null,
  disconnect: vi.fn(),
};

vi.mock('../../../hooks/useConsciousnessWebSocket', () => ({
  useConsciousnessWebSocket: vi.fn(() => mockWsReturn),
}));

const mockToast = {
  toasts: [],
  addToast: vi.fn(),
  removeToast: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
};

vi.mock('../../../components/UI/Toast', () => ({
  useToast: vi.fn(() => mockToast),
}));

// ── Imports after mocks are hoisted ────────────────────────────────────────

import { ConsciousnessPage } from '../ConsciousnessPage';
import {
  getConsciousnessStatistics,
  getAgentStates,
  getNetworkVisualization,
} from '../../../api/consciousness';

const mockGetStats = vi.mocked(getConsciousnessStatistics);
const mockGetAgentStates = vi.mocked(getAgentStates);
const mockGetNetwork = vi.mocked(getNetworkVisualization);

// ── Helpers ────────────────────────────────────────────────────────────────

function defaultStats() {
  return {
    total_agents: 5,
    average_phi: 0.7234,
    average_free_energy: 0.1500,
    active_connections: 3,
    timestamp: new Date().toISOString(),
  };
}

function defaultAgentStates() {
  return {
    counts: { coherent: 3, emerging: 2 },
    states: {
      'agent-001': 'coherent' as const,
      'agent-002': 'coherent' as const,
      'agent-003': 'emerging' as const,
      'agent-004': 'coherent' as const,
      'agent-005': 'emerging' as const,
    },
  };
}

function defaultNetwork() {
  return {
    nodes: [
      { id: 'agent-001', phi: 0.8, state: 'coherent' as const },
      { id: 'agent-002', phi: 0.6, state: 'emerging' as const },
    ],
    links: [{ source: 'agent-001', target: 'agent-002', weight: 0.5 }],
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('ConsciousnessPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
    mockGetStats.mockResolvedValue(defaultStats());
    mockGetAgentStates.mockResolvedValue(defaultAgentStates());
    mockGetNetwork.mockResolvedValue(defaultNetwork());
    mockWsReturn.agentStates = new Map();
    mockWsReturn.connected = true;
    mockWsReturn.error = null;
  });

  afterEach(() => {
    cleanup();
  });

  it('shows loading spinner initially then renders statistics', async () => {
    render(<ConsciousnessPage />);

    expect(screen.getByText('Loading consciousness metrics...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Total Agents')).toBeInTheDocument();
    });

    expect(screen.getByText('Average Phi Score')).toBeInTheDocument();
    expect(screen.getByText('Avg Free Energy')).toBeInTheDocument();
    expect(screen.getByText('Active Connections')).toBeInTheDocument();
  });

  it('renders the ConsciousnessGauge with zero values when WS has no agents', async () => {
    mockWsReturn.agentStates = new Map();
    mockWsReturn.connected = true;

    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Total Agents')).toBeInTheDocument();
    });

    expect(screen.getByText('Live (WebSocket)')).toBeInTheDocument();
  });

  it('derives gauge values from WebSocket agent states', async () => {
    mockWsReturn.agentStates = new Map([
      ['agent-001', {
        phi_score: 0.8,
        state: 'coherent',
        free_energy: 0.2,
        prediction_accuracy: 0.9,
        surprise: 0.1,
        belief_precision: 0.85,
        agency_score: 0.7,
        autonomy_score: 0.6,
        last_updated: new Date().toISOString(),
      }],
      ['agent-002', {
        phi_score: 0.6,
        state: 'emerging',
        free_energy: 0.4,
        prediction_accuracy: 0.7,
        surprise: 0.3,
        belief_precision: 0.65,
        agency_score: 0.5,
        autonomy_score: 0.4,
        last_updated: new Date().toISOString(),
      }],
    ]);

    const { container } = render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Total Agents')).toBeInTheDocument();
    });

    // Verify gauge average: (100 + 70 + 60 + 70) / 4 = 75.0
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    expect(texts).toContain('75.0');
  });

  it('shows "Polling (fallback)" when WS is disconnected', async () => {
    mockWsReturn.connected = false;

    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Total Agents')).toBeInTheDocument();
    });

    expect(screen.getByText('Polling (fallback)')).toBeInTheDocument();
    expect(screen.queryByText('Live (WebSocket)')).not.toBeInTheDocument();
  });

  it('renders agent state distribution from REST data', async () => {
    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Consciousness State Distribution')).toBeInTheDocument();
    });

    // coherent and emerging appear both in distribution bars AND agent state list
    const coherentEls = screen.getAllByText('coherent');
    expect(coherentEls.length).toBeGreaterThanOrEqual(2); // distribution + agent list
    const emergingEls = screen.getAllByText('emerging');
    expect(emergingEls.length).toBeGreaterThanOrEqual(2);
  });

  it('renders network visualization with nodes and links', async () => {
    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Agent Network')).toBeInTheDocument();
    });

    const circles = document.querySelectorAll('circle');
    expect(circles.length).toBeGreaterThanOrEqual(2);
  });

  it('renders agent state buttons in the Agent States list', async () => {
    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Agent States')).toBeInTheDocument();
    });

    expect(screen.getByText('agent-001')).toBeInTheDocument();
    expect(screen.getByText('agent-002')).toBeInTheDocument();
    expect(screen.getByText('agent-003')).toBeInTheDocument();
  });

  it('shows empty state when no agent states are available', async () => {
    mockGetAgentStates.mockResolvedValue({ counts: {}, states: {} });

    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('No state data')).toBeInTheDocument();
    });

    expect(screen.getByText('No agent states')).toBeInTheDocument();
  });

  it('shows empty state when no network data is available', async () => {
    mockGetNetwork.mockResolvedValue({ nodes: [], links: [] });

    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('No network data')).toBeInTheDocument();
    });
  });

  it('calls all three REST APIs on mount', async () => {
    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(mockGetStats).toHaveBeenCalledTimes(1);
      expect(mockGetAgentStates).toHaveBeenCalledTimes(1);
      expect(mockGetNetwork).toHaveBeenCalledTimes(1);
    });
  });

  it('handles agent state with null phi_score gracefully', async () => {
    mockWsReturn.agentStates = new Map([
      ['agent-partial', {
        phi_score: null,
        state: 'dormant',
        free_energy: null,
        prediction_accuracy: null,
        surprise: null,
        belief_precision: null,
        agency_score: null,
        autonomy_score: null,
        last_updated: null,
      }],
    ]);

    const { container } = render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Total Agents')).toBeInTheDocument();
    });

    // All null values: iit=0, ast=0, gwt=0 (dormant)
    // fep: avgFep=0 (no data) → (1-0)*100 = 100
    // Average = (0+0+0+100)/4 = 25.0
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    expect(texts).toContain('25.0');
  });

  it('refresh button re-fetches data', async () => {
    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('↻ Refresh')).toBeInTheDocument();
    });

    mockGetStats.mockClear();
    mockGetAgentStates.mockClear();
    mockGetNetwork.mockClear();

    const refreshButton = screen.getByText('↻ Refresh');
    refreshButton.click();

    await waitFor(() => {
      expect(mockGetStats).toHaveBeenCalledTimes(1);
      expect(mockGetAgentStates).toHaveBeenCalledTimes(1);
      expect(mockGetNetwork).toHaveBeenCalledTimes(1);
    });
  });

  it('renders statistics values from API data', async () => {
    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('0.7234')).toBeInTheDocument();
    });

    expect(screen.getByText('0.1500')).toBeInTheDocument();
    // "5" is total_agents and "3" appears in both MetricCard (active_connections) and state counts
    expect(screen.getByText('5')).toBeInTheDocument();
    const threes = screen.getAllByText('3');
    expect(threes.length).toBeGreaterThanOrEqual(2);
  });

  it('renders gauge theory labels in overview section', async () => {
    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Consciousness Overview')).toBeInTheDocument();
    });

    // GWT, IIT, AST, FEP labels are rendered by ConsciousnessGauge
    const gwtEls = screen.getAllByText('GWT');
    expect(gwtEls.length).toBeGreaterThanOrEqual(1);
  });

  it('shows disabled banner when all REST APIs fail', async () => {
    mockGetStats.mockRejectedValue(new Error('Not found'));
    mockGetAgentStates.mockRejectedValue(new Error('Not found'));
    mockGetNetwork.mockRejectedValue(new Error('Not found'));

    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Consciousness Plugin Disabled')).toBeInTheDocument();
    });

    expect(screen.getByText(/consciousness plugin is not active/)).toBeInTheDocument();
    expect(screen.getByText('CONSCIOUSNESS_ENABLED=true')).toBeInTheDocument();
  });

  it('shows partial error when some APIs fail', async () => {
    mockGetStats.mockRejectedValue(new Error('Not found'));
    // agentStates and network succeed (from defaults)

    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Some consciousness data could not be loaded. Partial results are shown below.')).toBeInTheDocument();
    });

    // Should NOT show the disabled banner
    expect(screen.queryByText('Consciousness Plugin Disabled')).not.toBeInTheDocument();
  });

  it('shows no error banner when all APIs succeed', async () => {
    render(<ConsciousnessPage />);

    await waitFor(() => {
      expect(screen.getByText('Total Agents')).toBeInTheDocument();
    });

    expect(screen.queryByText('Consciousness Plugin Disabled')).not.toBeInTheDocument();
    expect(screen.queryByText(/could not be loaded/)).not.toBeInTheDocument();
  });
});
