/**
 * API Client - Metrics endpoints
 *
 * Provides access to Prometheus-derived metrics and per-agent
 * performance data from the swarm runtime.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface SwarmMetrics {
  total_agents: number;
  active_agents: number;
  idle_agents: number;
  tasks_completed: number;
  tasks_failed: number;
  messages_total: number;
  consensus_rounds: number;
  health_score: number;
}

export interface ConsciousnessMetrics {
  phi_avg: number;
  phi_max: number;
  phi_min: number;
  free_energy_avg: number;
  free_energy_max: number;
  free_energy_min: number;
  agent_phi_scores: Record<string, number>;
  agent_fep_scores: Record<string, number>;
}

export interface MetricsJsonResponse {
  swarm: SwarmMetrics;
  consciousness: ConsciousnessMetrics;
  health_score: number;
}

export interface AgentMetrics {
  agent_id: string;
  agent_type: string;
  tasks_completed: number;
  tasks_failed: number;
  avg_task_duration_seconds: number;
  messages_sent: number;
  messages_received: number;
  error_count: number;
  success_rate: number;
  health_score: number;
  last_activity: string | null;
}

export interface AgentMetricsResponse {
  agents: Record<string, AgentMetrics>;
  states: Record<string, string>;
  total_agents: number;
  timestamp: string;
}

// =============================================================================
// Metrics API
// =============================================================================

/**
 * Fetch Prometheus-derived metrics in JSON format.
 *
 * Calls GET /api/metrics/json which returns swarm stats, consciousness
 * data, and the aggregate health score.
 */
export async function fetchMetricsJson(): Promise<MetricsJsonResponse> {
  const response = await api.get<MetricsJsonResponse>('/api/metrics/json');
  return response.data;
}

/**
 * Fetch per-agent performance metrics.
 *
 * Calls GET /api/observability/agents to get per-agent
 * avg_task_duration_seconds and other health data.
 */
export async function fetchAgentMetrics(): Promise<AgentMetricsResponse> {
  const response = await api.get<AgentMetricsResponse>(
    '/api/observability/agents',
  );
  return response.data;
}
