/**
 * API Client - Consciousness metrics endpoints
 */

import { api } from './client';

export interface ConsciousnessStatistics {
  total_agents: number;
  average_phi: number;
  average_free_energy: number;
  active_connections: number;
  timestamp: string;
}

export interface AgentMetrics {
  agent_id: string;
  phi_score: number;
  fep_metrics: {
    free_energy: number;
    prediction_accuracy: number;
    surprise: number;
    belief_precision: number;
  };
  state: 'dormant' | 'emerging' | 'coherent' | 'transcendent';
  timestamp: string;
}

export interface AgencyMetrics {
  agency_score: number;
  autonomy_score: number;
  decision_count: number;
  last_decision: string | null;
}

export interface TimeSeriesData {
  agent_id: string;
  metric: string;
  hours: number;
  data_points: {
    timestamp: string;
    value: number;
  }[];
  count: number;
}

export interface NetworkVisualization {
  nodes: {
    id: string;
    phi: number;
    state: 'dormant' | 'emerging' | 'coherent' | 'transcendent';
  }[];
  links: {
    source: string;
    target: string;
    weight: number;
  }[];
}

/**
 * WebSocket event types for consciousness updates
 * These mirror the event shapes broadcast from the backend via /ws/dashboard
 */

/** phi_update event broadcast from consciousness_event_handler */
export interface PhiUpdateEvent {
  type: 'phi_update';
  agent_id: string;
  phi_score: number;
  state: 'dormant' | 'emerging' | 'coherent' | 'transcendent';
  timestamp: string;
}

/** fep_update event broadcast from consciousness_event_handler */
export interface FepUpdateEvent {
  type: 'fep_update';
  agent_id: string;
  free_energy: number;
  prediction_accuracy: number;
  surprise: number;
  belief_precision: number;
  timestamp: string;
}

/** agency_update event broadcast from consciousness_event_handler */
export interface AgencyUpdateEvent {
  type: 'agency_update';
  agent_id: string;
  agency_score: number;
  autonomy_score: number;
  timestamp: string;
}

/** Union type for all consciousness WebSocket event types */
export type ConsciousnessWebSocketEvent = PhiUpdateEvent | FepUpdateEvent | AgencyUpdateEvent;

/**
 * Get collective consciousness statistics
 */
export const getConsciousnessStatistics = async (): Promise<ConsciousnessStatistics> => {
  const response = await api.get<ConsciousnessStatistics>('/api/consciousness/statistics');
  return response.data;
};

/**
 * Get consciousness metrics for specific agent
 */
export const getAgentMetrics = async (agentId: string): Promise<AgentMetrics> => {
  const response = await api.get<AgentMetrics>(`/api/consciousness/agents/${agentId}`);
  return response.data;
};

/**
 * Get agency metrics for specific agent
 */
export const getAgencyMetrics = async (agentId: string): Promise<AgencyMetrics> => {
  const response = await api.get<AgencyMetrics>(`/api/consciousness/agency/${agentId}`);
  return response.data;
};

/**
 * Get time series data for metrics visualization
 */
export const getTimeSeriesData = async (
  agentId: string,
  metric: string,
  hours: number = 24,
): Promise<TimeSeriesData> => {
  const response = await api.get<TimeSeriesData>(
    `/api/consciousness/visualization/timeseries?agent_id=${agentId}&metric=${metric}&hours=${hours}`,
  );
  return response.data;
};

/**
 * Get network visualization data
 */
export const getNetworkVisualization = async (): Promise<NetworkVisualization> => {
  const response = await api.get<NetworkVisualization>('/api/consciousness/visualization/network');
  return response.data;
};

/**
 * Get agent states distribution
 */
export const getAgentStates = async (): Promise<{
  counts: Record<string, number>;
  states: Record<string, 'dormant' | 'emerging' | 'coherent' | 'transcendent'>;
}> => {
  const response = await api.get<{
    counts: Record<string, number>;
    states: Record<string, 'dormant' | 'emerging' | 'coherent' | 'transcendent'>;
  }>('/api/consciousness/states');
  return response.data;
};
