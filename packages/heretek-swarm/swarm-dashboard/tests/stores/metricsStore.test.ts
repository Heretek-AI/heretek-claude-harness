import { describe, it, expect, beforeEach } from 'vitest';
import { useMetricsStore } from '../../src/stores/metricsStore';

describe('metricsStore', () => {
  beforeEach(() => {
    useMetricsStore.getState().reset();
  });

  it('sets collective metrics', () => {
    useMetricsStore.getState().setCollectiveMetrics({
      average_gwt_score: 0.8,
      average_phi: 0.7,
      average_ast: 0.6,
      average_free_energy: 0.5,
      agent_count: 10,
      timestamp: '2025-01-01T00:00:00Z',
    });
    const s = useMetricsStore.getState();
    expect(s.collectiveMetrics).not.toBeNull();
    expect(s.collectiveMetrics!.agent_count).toBe(10);
    expect(s.collectiveMetrics!.average_gwt_score).toBe(0.8);
  });

  it('sets agent metrics', () => {
    useMetricsStore.getState().setAgentMetrics('agent-1', {
      agent_id: 'agent-1',
      gwt_score: 0.9,
      phi_value: 0.8,
      ast_competence: 0.7,
      free_energy: 0.6,
      state: 'coherent',
      timestamp: '2025-01-01T00:00:00Z',
    });
    const s = useMetricsStore.getState();
    expect(s.agentMetrics['agent-1']).toBeDefined();
    expect(s.agentMetrics['agent-1'].gwt_score).toBe(0.9);
  });

  it('sets agent states', () => {
    useMetricsStore.getState().setAgentStates({
      counts: { coherent: 5, dormant: 3 },
      states: { 'agent-1': 'coherent', 'agent-2': 'dormant' },
    });
    const s = useMetricsStore.getState();
    expect(s.agentStates!.counts.coherent).toBe(5);
    expect(s.agentStates!.states['agent-2']).toBe('dormant');
  });

  it('resets state', () => {
    useMetricsStore.getState().setCollectiveMetrics({
      average_gwt_score: 0.8,
      average_phi: 0.7,
      average_ast: 0.6,
      average_free_energy: 0.5,
      agent_count: 10,
      timestamp: '2025-01-01T00:00:00Z',
    });
    useMetricsStore.getState().reset();
    const s = useMetricsStore.getState();
    expect(s.collectiveMetrics).toBeNull();
    expect(s.agentMetrics).toEqual({});
    expect(s.agentStates).toBeNull();
  });

  it('sets loading and error', () => {
    useMetricsStore.getState().setLoading(true);
    expect(useMetricsStore.getState().loading).toBe(true);
    useMetricsStore.getState().setError('oops');
    expect(useMetricsStore.getState().error).toBe('oops');
  });
});
