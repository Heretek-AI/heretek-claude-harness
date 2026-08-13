import type { ConsciousnessMetrics, SwarmHealthMetrics } from './useMetrics';

interface MetricsOverlayProps {
  consciousness: ConsciousnessMetrics | null;
  swarmHealth: SwarmHealthMetrics | null;
  metricsLoading: boolean;
  onClose: () => void;
}

function getHealthColor(score: number): string {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-blue-400';
  if (score >= 40) return 'text-yellow-400';
  if (score >= 20) return 'text-orange-400';
  return 'text-red-400';
}

function getPhiColor(score: number): string {
  if (score >= 0.7) return 'text-green-400';
  if (score >= 0.5) return 'text-blue-400';
  if (score >= 0.3) return 'text-yellow-400';
  return 'text-red-400';
}

export function MetricsOverlay({
  consciousness,
  swarmHealth,
  metricsLoading,
  onClose,
}: MetricsOverlayProps) {
  return (
    <div className="absolute top-4 left-4 z-50 w-80 bg-gray-900 border border-gray-700 rounded-lg shadow-xl p-4 max-h-[80vh] overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-bold">Swarm Metrics</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white"
        >
          ✕
        </button>
      </div>

      {metricsLoading && !consciousness && !swarmHealth && (
        <div className="text-center text-gray-400 py-4">Loading metrics...</div>
      )}

      {/* Swarm Health Section */}
      {swarmHealth && (
        <div className="mb-6">
          <h4 className="text-gray-300 text-sm font-semibold mb-2 uppercase tracking-wide">
            Swarm Health
          </h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Health Score</span>
              <span className={`font-bold ${getHealthColor(swarmHealth.overall_health_score)}`}>
                {swarmHealth.overall_health_score}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Active Agents</span>
              <span className="text-white font-medium">{swarmHealth.active_agents}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Idle Agents</span>
              <span className="text-white font-medium">{swarmHealth.idle_agents}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Task Completion</span>
              <span className="text-white font-medium">{swarmHealth.task_completion_rate}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Consciousness Metrics Section */}
      {consciousness && (
        <div>
          <h4 className="text-gray-300 text-sm font-semibold mb-2 uppercase tracking-wide">
            Consciousness
          </h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Φ Score</span>
              <span className={`font-bold ${getPhiColor(consciousness.phi_score)}`}>
                {consciousness.phi_score.toFixed(3)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Φ Average</span>
              <span className="text-white font-medium">{consciousness.phi_avg.toFixed(3)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Φ Max</span>
              <span className="text-white font-medium">{consciousness.phi_max.toFixed(3)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Free Energy</span>
              <span className="text-white font-medium">{consciousness.free_energy_avg.toFixed(3)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Integration Level</span>
              <span className="text-white font-medium">{consciousness.integration_level}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MetricsOverlay;
