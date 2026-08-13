import { useState, useEffect, useCallback } from 'react';

export interface ConsciousnessMetrics {
  phi_score: number;
  phi_avg: number;
  phi_max: number;
  free_energy_avg: number;
  integration_level: number;
}

export interface SwarmHealthMetrics {
  overall_health_score: number;
  active_agents: number;
  idle_agents: number;
  task_completion_rate: number;
}

const API_URL = import.meta.env.VITE_API_HOST || localStorage.getItem('swarm_api_host') || '';

const POLL_INTERVAL = 10000; // 10 seconds

// Try observability endpoint first (no auth), then consciousness (may require auth)
const CONSCIOUSNESS_ENDPOINTS = [
  '/api/observability/consciousness',
  '/api/consciousness/statistics',
];

export function useConsciousnessMetrics() {
  const [metrics, setMetrics] = useState<ConsciousnessMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = useCallback(async () => {
    for (const endpoint of CONSCIOUSNESS_ENDPOINTS) {
      try {
        const response = await fetch(`${API_URL}${endpoint}`);
        if (response.ok) {
          const data = await response.json();
          // Map response to expected shape
          setMetrics({
            phi_score: data.phi_score ?? data.average_phi ?? 0,
            phi_avg: data.phi_avg ?? data.average_phi ?? 0,
            phi_max: data.phi_max ?? data.average_phi ?? 0,
            free_energy_avg: data.free_energy_avg ?? data.average_free_energy ?? 0,
            integration_level: data.integration_level ?? 0,
          });
          setError(null);
          return; // Success - stop trying endpoints
        }
      } catch {
        // Try next endpoint
      }
    }
    // All endpoints failed
    setError('Consciousness metrics unavailable');
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  return { metrics, loading, error };
}

export function useSwarmHealth(agents: AgentApiResponse[]) {
  const [health, setHealth] = useState<SwarmHealthMetrics | null>(null);

  useEffect(() => {
    if (!agents || agents.length === 0) {
      setHealth(null);
      return;
    }

    const activeAgents = agents.filter(a => a.status === 'thinking' || a.status === 'acting').length;
    const idleAgents = agents.filter(a => a.status === 'idle').length;
    const errorAgents = agents.filter(a => a.status === 'error').length;

    // Calculate overall health score (0-100)
    const healthScore = Math.round(
      ((activeAgents + idleAgents * 0.5) / agents.length) * 100 - (errorAgents * 10)
    );

    // Calculate task completion rate (estimate based on non-error agents)
    const completionRate = agents.length > 0
      ? Math.round(((activeAgents + idleAgents) / agents.length) * 100)
      : 0;

    setHealth({
      overall_health_score: Math.max(0, Math.min(100, healthScore)),
      active_agents: activeAgents,
      idle_agents: idleAgents,
      task_completion_rate: completionRate,
    });
  }, [agents]);

  return health;
}

interface AgentApiResponse {
  id: string;
  type: string;
  status: string;
  lastActivity?: string;
}
