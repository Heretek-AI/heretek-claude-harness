/**
 * Consciousness Metrics WebSocket Hook
 *
 * Subscribes to the dashboard WebSocket channel and tracks live phi/FEP/agency
 * metrics for each agent, updating every 5 seconds when agents are active.
 *
 * Supplements REST polling — when WebSocket is unavailable, metrics fall back
 * to the polling interval shown in the UI.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { useWebSocket, WebSocketMessage } from './useWebSocket';
import {
  PhiUpdateEvent,
  FepUpdateEvent,
  AgencyUpdateEvent,
  ConsciousnessWebSocketEvent,
} from '../api/consciousness';

/** Per-agent consciousness state maintained from WebSocket events */
export interface ConsciousnessAgentState {
  phi_score: number | null;
  state: string | null;
  free_energy: number | null;
  prediction_accuracy: number | null;
  surprise: number | null;
  belief_precision: number | null;
  agency_score: number | null;
  autonomy_score: number | null;
  last_updated: string | null;
}

interface UseConsciousnessWebSocketOptions {
  /** Throttle interval in ms to prevent UI flicker (default: 100) */
  throttleInterval?: number;
}

interface UseConsciousnessWebSocketReturn {
  /** Per-agent consciousness state keyed by agent_id */
  agentStates: Map<string, ConsciousnessAgentState>;
  /** Whether the WebSocket is connected */
  connected: boolean;
  /** Error state for diagnostics */
  error: Event | null;
  /** Manual disconnect function */
  disconnect: () => void;
}

/** Merge an incoming phi update into an agent state */
function applyPhiUpdate(
  state: ConsciousnessAgentState,
  update: PhiUpdateEvent
): ConsciousnessAgentState {
  return {
    ...state,
    phi_score: update.phi_score,
    state: update.state,
    last_updated: update.timestamp,
  };
}

/** Merge an incoming FEP update into an agent state */
function applyFepUpdate(
  state: ConsciousnessAgentState,
  update: FepUpdateEvent
): ConsciousnessAgentState {
  return {
    ...state,
    free_energy: update.free_energy,
    prediction_accuracy: update.prediction_accuracy,
    surprise: update.surprise,
    belief_precision: update.belief_precision,
    last_updated: update.timestamp,
  };
}

/** Merge an incoming agency update into an agent state */
function applyAgencyUpdate(
  state: ConsciousnessAgentState,
  update: AgencyUpdateEvent
): ConsciousnessAgentState {
  return {
    ...state,
    agency_score: update.agency_score,
    autonomy_score: update.autonomy_score,
    last_updated: update.timestamp,
  };
}

/**
 * Hook to track consciousness metrics per agent via dashboard WebSocket channel.
 *
 * Subscribes to the `dashboard` channel which broadcasts `phi_update`, `fep_update`,
 * and `agency_update` type events from the backend consciousness loop.
 * Gracefully handles missing fields on partial updates.
 */
export function useConsciousnessWebSocket(
  options: UseConsciousnessWebSocketOptions = {}
): UseConsciousnessWebSocketReturn {
  const { throttleInterval = 100 } = options;

  const [agentStates, setAgentStates] = useState<Map<string, ConsciousnessAgentState>>(new Map());
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<Event | null>(null);

  // Refs for throttling state
  const pendingUpdates = useRef<Map<string, ConsciousnessAgentState>>(new Map());
  const throttleTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isProcessing = useRef(false);

  /** Flush accumulated updates to state */
  const flushUpdates = useCallback(() => {
    if (isProcessing.current || pendingUpdates.current.size === 0) return;
    isProcessing.current = true;

    setAgentStates((prev) => {
      const next = new Map(prev);
      pendingUpdates.current.forEach((state, agentId) => {
        next.set(agentId, state);
      });
      return next;
    });

    pendingUpdates.current.clear();
    isProcessing.current = false;
  }, []);

  /** Handle incoming WebSocket message */
  const handleMessage = useCallback(
    (msg: WebSocketMessage) => {
      const eventType = msg.type;

      // Only process consciousness event types
      if (
        eventType !== 'phi_update' &&
        eventType !== 'fep_update' &&
        eventType !== 'agency_update'
      ) {
        return;
      }

      // Validate agent_id presence
      const agentId = msg.agent_id;
      if (!agentId) {
        console.debug('[useConsciousnessWebSocket] Received event without agent_id:', msg);
        return;
      }

      const now = msg.timestamp || new Date().toISOString();

      // Get or initialize current state for this agent
      const pending = pendingUpdates.current.get(agentId);
      const prev = pending ?? agentStates.get(agentId) ?? {
        phi_score: null,
        state: null,
        free_energy: null,
        prediction_accuracy: null,
        surprise: null,
        belief_precision: null,
        agency_score: null,
        autonomy_score: null,
        last_updated: null,
      };

      let updated: ConsciousnessAgentState;

      if (eventType === 'phi_update') {
        updated = applyPhiUpdate(prev, msg as unknown as PhiUpdateEvent);
      } else if (eventType === 'fep_update') {
        updated = applyFepUpdate(prev, msg as unknown as FepUpdateEvent);
      } else {
        updated = applyAgencyUpdate(prev, msg as unknown as AgencyUpdateEvent);
      }

      pendingUpdates.current.set(agentId, updated);

      // Schedule flush if not already scheduled
      if (!throttleTimeout.current) {
        throttleTimeout.current = setTimeout(() => {
          throttleTimeout.current = null;
          flushUpdates();
        }, throttleInterval);
      }
    },
    [agentStates, throttleInterval, flushUpdates]
  );

  /** WebSocket subscription to dashboard channel */
  const { disconnect } = useWebSocket('dashboard', {
    onMessage: handleMessage,
    onOpen: () => setConnected(true),
    onClose: () => setConnected(false),
    onError: (err) => setError(err),
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
  });

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (throttleTimeout.current) {
        clearTimeout(throttleTimeout.current);
        throttleTimeout.current = null;
      }
      disconnect();
    };
  }, [disconnect]);

  return {
    agentStates,
    connected,
    error,
    disconnect,
  };
}
