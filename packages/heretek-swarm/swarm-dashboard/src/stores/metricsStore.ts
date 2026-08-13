/**
 * Metrics Store - Zustand state management for consciousness metrics
 *
 * Enhanced with debug middleware for state transition logging.
 */

import { create } from 'zustand';
import { withDebugMiddleware } from './middleware/debugMiddleware';

export interface ConsciousnessMetrics {
  average_gwt_score: number;
  average_phi: number;
  average_ast: number;
  average_free_energy: number;
  agent_count: number;
  timestamp: string;
}

export interface AgentMetrics {
  agent_id: string;
  gwt_score: number;
  phi_value: number;
  ast_competence: number;
  free_energy: number;
  state: 'dormant' | 'emerging' | 'coherent' | 'transcendent';
  timestamp: string;
}

export interface AgentStates {
  counts: Record<string, number>;
  states: Record<string, 'dormant' | 'emerging' | 'coherent' | 'transcendent'>;
}

interface MetricsState {
  // State
  collectiveMetrics: ConsciousnessMetrics | null;
  agentMetrics: Record<string, AgentMetrics>;
  agentStates: AgentStates | null;
  loading: boolean;
  error: string | null;

  // Actions
  setCollectiveMetrics: (metrics: ConsciousnessMetrics) => void;
  setAgentMetrics: (agentId: string, metrics: AgentMetrics) => void;
  setAgentStates: (states: AgentStates) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useMetricsStore = create<MetricsState>(
  withDebugMiddleware((set, get) => {
    // Action helpers with action type tracking
    const setWithAction = <T extends Partial<MetricsState>>(
      partial: T | ((state: MetricsState) => T),
      actionType: string
    ) => {
      const currentState = get();
      set(partial);
      const nextState = get();

      // Dispatch state transition event for DebugPanel
      if (typeof window !== 'undefined' && localStorage.getItem('developer_mode') === 'true') {
        const changes: Record<string, { before: unknown; after: unknown }> = {};
        const allKeys = new Set([...Object.keys(currentState), ...Object.keys(nextState)]);

        for (const key of allKeys) {
          const prevValue = currentState[key as keyof typeof currentState];
          const nextValue = nextState[key as keyof typeof nextState];

          if (JSON.stringify(prevValue) !== JSON.stringify(nextValue)) {
            changes[key] = { before: prevValue, after: nextValue };
          }
        }

        window.dispatchEvent(
          new CustomEvent('state-transition', {
            detail: {
              timestamp: new Date().toISOString(),
              actionType,
              previousState: currentState,
              nextState,
              changes,
            },
          })
        );
      }
    };

    return {
      // Initial state
      collectiveMetrics: null,
      agentMetrics: {},
      agentStates: null,
      loading: false,
      error: null,

      // Actions
      setCollectiveMetrics: (metrics: ConsciousnessMetrics) => {
        setWithAction({ collectiveMetrics: metrics }, 'setCollectiveMetrics');
      },
      setAgentMetrics: (agentId: string, metrics: AgentMetrics) => {
        setWithAction((state) => ({
          agentMetrics: { ...state.agentMetrics, [agentId]: metrics }
        }), 'setAgentMetrics');
      },
      setAgentStates: (states: AgentStates) => {
        setWithAction({ agentStates: states }, 'setAgentStates');
      },
      setLoading: (loading: boolean) => {
        setWithAction({ loading }, 'setLoading');
      },
      setError: (error: string | null) => {
        setWithAction({ error }, 'setError');
      },
      reset: () => {
        setWithAction({
          collectiveMetrics: null,
          agentMetrics: {},
          agentStates: null,
          loading: false,
          error: null,
        }, 'reset');
      },
    };
  }, {
    logToConsole: true,
    logToWindow: true,
    skipActions: [],
  })
);
