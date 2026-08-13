/**
 * Consciousness Metrics Panel
 *
 * Displays IIT Phi and FEP metrics for the agent swarm.
 * Shows per-agent consciousness scores and aggregate metrics.
 */

import { useState, useEffect, useCallback } from "react";

// Types
interface ConsciousnessMetrics {
  system_id: string;
  phi_score: number;
  phi_max: number;
  phi_min: number;
  phi_avg: number;
  integration_level: string;
  differentiation_level: string;
  free_energy: number;
  free_energy_avg: number;
  surprise_avg: number;
  prediction_accuracy: number;
  belief_precision: number;
  agent_phi_scores: Record<string, number>;
  agent_fep_scores: Record<string, number>;
  timestamp: string;
  metadata: Record<string, any>;
}

interface AgentPhiScore {
  agent_id: string;
  phi_score: number;
  fep_score: number;
}

interface ConsciousnessMetricsPanelProps {
  apiBaseUrl?: string;
  refreshInterval?: number;
  onMetricsUpdate?: (metrics: ConsciousnessMetrics) => void;
}

// Use environment variable or relative path (nginx proxies /api to api:8000)
const API_URL = import.meta.env.VITE_API_HOST || "";

export function ConsciousnessMetricsPanel({
  apiBaseUrl = API_URL,
  refreshInterval = 5000,
  onMetricsUpdate,
}: ConsciousnessMetricsPanelProps) {
  const [metrics, setMetrics] = useState<ConsciousnessMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  // Fetch consciousness metrics
  const fetchMetrics = useCallback(async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/observability/consciousness`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch consciousness metrics: ${response.status}`);
      }

      const data = await response.json();
      setMetrics(data);
      setError(null);

      if (onMetricsUpdate) {
        onMetricsUpdate(data);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch consciousness metrics";
      setError(errorMessage);
      console.error("ConsciousnessMetricsPanel error:", err);
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, onMetricsUpdate]);

  // Initial fetch and refresh interval
  useEffect(() => {
    fetchMetrics();

    const interval = setInterval(() => {
      fetchMetrics();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [fetchMetrics, refreshInterval]);

  // Get integration level color
  const getIntegrationColor = (level: string): string => {
    const colors: Record<string, string> = {
      very_high: "text-green-400",
      high: "text-blue-400",
      moderate: "text-yellow-400",
      low: "text-orange-400",
      minimal: "text-red-400",
      unknown: "text-gray-400",
    };
    return colors[level] || colors.unknown;
  };

  // Get differentiation level color
  const getDifferentiationColor = (level: string): string => {
    return getIntegrationColor(level);
  };

  // Get phi score color
  const getPhiColor = (score: number): string => {
    if (score >= 0.7) return "text-green-400";
    if (score >= 0.5) return "text-blue-400";
    if (score >= 0.3) return "text-yellow-400";
    if (score >= 0.1) return "text-orange-400";
    return "text-red-400";
  };

  // Get agent phi scores as sorted array
  const getAgentPhiScores = (): AgentPhiScore[] => {
    if (!metrics) return [];

    const allAgents = new Set([
      ...Object.keys(metrics.agent_phi_scores),
      ...Object.keys(metrics.agent_fep_scores),
    ]);

    return Array.from(allAgents)
      .map((agentId) => ({
        agent_id: agentId,
        phi_score: metrics?.agent_phi_scores[agentId] || 0,
        fep_score: metrics?.agent_fep_scores[agentId] || 0,
      }))
      .sort((a, b) => b.phi_score - a.phi_score);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-800 rounded-lg border border-gray-700">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white">Consciousness Metrics</h2>
        <div className="text-sm text-gray-400">
          {metrics?.timestamp ? new Date(metrics.timestamp).toLocaleTimeString() : ""}
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="mb-4 bg-red-900/30 border border-red-500 rounded-lg p-3">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Aggregate Metrics */}
      {metrics && (
        <>
          {/* Top-level metrics grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {/* Phi Score */}
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <h3 className="text-gray-400 text-xs uppercase tracking-wider mb-2">
                Average Phi (IIT)
              </h3>
              <p className={`text-2xl font-bold ${getPhiColor(metrics.phi_avg)}`}>
                {metrics.phi_avg.toFixed(4)}
              </p>
              <div className="mt-2 text-xs text-gray-500">
                Max: {metrics.phi_max.toFixed(4)} | Min: {metrics.phi_min.toFixed(4)}
              </div>
            </div>

            {/* Free Energy */}
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <h3 className="text-gray-400 text-xs uppercase tracking-wider mb-2">
                Free Energy (FEP)
              </h3>
              <p className="text-2xl font-bold text-green-400">
                {metrics.free_energy_avg.toFixed(4)}
              </p>
              <div className="mt-2 text-xs text-gray-500">
                Prediction: {(metrics.prediction_accuracy * 100).toFixed(1)}%
              </div>
            </div>

            {/* Integration Level */}
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <h3 className="text-gray-400 text-xs uppercase tracking-wider mb-2">
                Integration
              </h3>
              <p className={`text-2xl font-bold capitalize ${getIntegrationColor(metrics.integration_level)}`}>
                {metrics.integration_level.replace("_", " ")}
              </p>
              <div className="mt-2 text-xs text-gray-500">
                IIT 3.0+ Measure
              </div>
            </div>

            {/* Differentiation Level */}
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <h3 className="text-gray-400 text-xs uppercase tracking-wider mb-2">
                Differentiation
              </h3>
              <p className={`text-2xl font-bold capitalize ${getDifferentiationColor(metrics.differentiation_level)}`}>
                {metrics.differentiation_level.replace("_", " ")}
              </p>
              <div className="mt-2 text-xs text-gray-500">
                State Diversity
              </div>
            </div>
          </div>

          {/* Agent Phi Scores Table */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-400 mb-3">Agent Consciousness Scores</h3>
            <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-950">
                  <tr>
                    <th className="px-4 py-3 text-left text-gray-400 font-medium">Agent ID</th>
                    <th className="px-4 py-3 text-left text-gray-400 font-medium">Phi Score</th>
                    <th className="px-4 py-3 text-left text-gray-400 font-medium">FEP Score</th>
                    <th className="px-4 py-3 text-left text-gray-400 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {getAgentPhiScores().map((agent) => (
                    <tr
                      key={agent.agent_id}
                      className={`hover:bg-gray-800 cursor-pointer ${
                        selectedAgent === agent.agent_id ? "bg-blue-900/20" : ""
                      }`}
                      onClick={() => setSelectedAgent(agent.agent_id)}
                    >
                      <td className="px-4 py-3 text-white font-mono">{agent.agent_id}</td>
                      <td className={`px-4 py-3 font-medium ${getPhiColor(agent.phi_score)}`}>
                        {agent.phi_score.toFixed(4)}
                      </td>
                      <td className="px-4 py-3 text-green-400">
                        {agent.fep_score.toFixed(4)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                            agent.phi_score >= 0.5
                              ? "bg-green-900/50 text-green-400"
                              : agent.phi_score >= 0.3
                              ? "bg-yellow-900/50 text-yellow-400"
                              : "bg-red-900/50 text-red-400"
                          }`}
                        >
                          {agent.phi_score >= 0.5 ? "Coherent" : agent.phi_score >= 0.3 ? "Emerging" : "Dormant"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {getAgentPhiScores().length === 0 && (
                <div className="px-4 py-8 text-center text-gray-500">
                  No agent consciousness data available
                </div>
              )}
            </div>
          </div>

          {/* Phi Distribution Visualization */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-3">Phi Distribution</h3>
            <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
              <div className="flex items-end justify-between h-32 gap-1">
                {getAgentPhiScores().slice(0, 20).map((agent) => {
                  const height = Math.max(4, agent.phi_score * 100);
                  return (
                    <div
                      key={agent.agent_id}
                      className="flex-1 flex flex-col items-center gap-1"
                      title={`${agent.agent_id}: ${agent.phi_score.toFixed(4)}`}
                    >
                      <div
                        className={`w-full rounded-t ${
                          agent.phi_score >= 0.5
                            ? "bg-green-500"
                            : agent.phi_score >= 0.3
                            ? "bg-yellow-500"
                            : "bg-red-500"
                        }`}
                        style={{ height: `${height}%` }}
                      />
                      <div className="text-xs text-gray-500 truncate w-full text-center">
                        {agent.agent_id.split("-")[0]}
                      </div>
                    </div>
                  );
                })}
              </div>
              {getAgentPhiScores().length > 20 && (
                <div className="mt-2 text-xs text-gray-500 text-center">
                  +{getAgentPhiScores().length - 20} more agents
                </div>
              )}
            </div>
          </div>

          {/* Selected Agent Details */}
          {selectedAgent && (
            <div className="mt-6 bg-blue-900/20 border border-blue-500/50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-blue-400">
                  Selected Agent: {selectedAgent}
                </h3>
                <button
                  onClick={() => setSelectedAgent(null)}
                  className="text-gray-400 hover:text-white"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Phi Score:</span>
                  <span className={`ml-2 font-medium ${getPhiColor(
                    metrics.agent_phi_scores[selectedAgent] || 0
                  )}`}>
                    {(metrics.agent_phi_scores[selectedAgent] || 0).toFixed(4)}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">FEP Score:</span>
                  <span className="ml-2 font-medium text-green-400">
                    {(metrics.agent_fep_scores[selectedAgent] || 0).toFixed(4)}
                  </span>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ConsciousnessMetricsPanel;
