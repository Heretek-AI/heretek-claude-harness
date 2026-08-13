/**
 * Consciousness Page
 *
 * Metrics visualization for agent consciousness states.
 * Real-time updates via WebSocket (REST polling as fallback).
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { MetricCard, MetricCardGrid } from '../UI/MetricCard';
import { StatusBadge } from '../UI/StatusBadge';
import { LoadingSpinner } from '../UI/LoadingSpinner';
import { EmptyState } from '../UI/EmptyState';
import { useToast } from '../UI/Toast';
import { getConsciousnessStatistics, getAgentStates, getNetworkVisualization } from '../../api/consciousness';
import { useConsciousnessWebSocket, ConsciousnessAgentState } from '../../hooks/useConsciousnessWebSocket';
import { ConsciousnessGauge } from './ConsciousnessGauge';

interface ConsciousnessStatistics {
  total_agents: number;
  average_phi: number;
  average_free_energy: number;
  active_connections: number;
  timestamp: string;
}

interface AgentStates {
  counts: Record<string, number>;
  states: Record<string, 'dormant' | 'emerging' | 'coherent' | 'transcendent'>;
}

interface NetworkNode {
  id: string;
  phi: number;
  state: 'dormant' | 'emerging' | 'coherent' | 'transcendent';
}

interface NetworkLink {
  source: string;
  target: string;
  weight: number;
}

interface NetworkVisualization {
  nodes: NetworkNode[];
  links: NetworkLink[];
}

export function ConsciousnessPage() {
  const [statistics, setStatistics] = useState<ConsciousnessStatistics | null>(null);
  const [agentStates, setAgentStates] = useState<AgentStates | null>(null);
  const [networkData, setNetworkData] = useState<NetworkVisualization | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);
  const toast = useToast();

  // Real-time WebSocket consciousness updates
  const { agentStates: wsAgentStates, connected: wsConnected } = useConsciousnessWebSocket();

  /** Derive aggregate gauge values from WebSocket agent states */
  const gaugeValues = useMemo(() => {
    if (wsAgentStates.size === 0) {
      return { gwt: 0, iit: 0, ast: 0, fep: 0 };
    }

    let phiSum = 0, phiCount = 0;
    let fepSum = 0, fepCount = 0;
    let agencySum = 0, agencyCount = 0;
    // GWT approximated from active connection ratio (workspace broadcasting)
    let activeCount = 0;

    wsAgentStates.forEach((state: ConsciousnessAgentState) => {
      if (state.phi_score != null) { phiSum += state.phi_score; phiCount++; }
      if (state.free_energy != null) { fepSum += state.free_energy; fepCount++; }
      if (state.agency_score != null) { agencySum += state.agency_score; agencyCount++; }
      if (state.state && state.state !== 'dormant') { activeCount++; }
    });

    const avgPhi = phiCount > 0 ? phiSum / phiCount : 0;
    const avgFep = fepCount > 0 ? fepSum / fepCount : 0;
    const avgAgency = agencyCount > 0 ? agencySum / agencyCount : 0;
    // GWT: ratio of active (non-dormant) agents scaled to 0-100
    const gwt = wsAgentStates.size > 0 ? (activeCount / wsAgentStates.size) * 100 : 0;

    // Normalize phi (typically 0-1) and FEP (typically 0-1) to 0-100
    return {
      gwt: Math.min(100, gwt),
      iit: Math.min(100, avgPhi * 100),
      ast: Math.min(100, avgAgency * 100),
      fep: Math.min(100, Math.max(0, (1 - avgFep) * 100)), // Invert: lower free energy = higher score
    };
  }, [wsAgentStates]);

  const fetchStatistics = useCallback(async () => {
    try {
      const data = await getConsciousnessStatistics();
      setStatistics(data);
      return true;
    } catch (error) {
      console.error('Failed to fetch consciousness statistics:', error);
      return false;
    }
  }, []);

  const fetchAgentStates = useCallback(async () => {
    try {
      const data = await getAgentStates();
      setAgentStates(data);
      return true;
    } catch (error) {
      console.error('Failed to fetch agent states:', error);
      return false;
    }
  }, []);

  const fetchNetworkData = useCallback(async () => {
    try {
      const data = await getNetworkVisualization();
      setNetworkData(data);
      return true;
    } catch (error) {
      console.error('Failed to fetch network visualization:', error);
      return false;
    }
  }, []);

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    setApiError(null);
    try {
      const results = await Promise.all([fetchStatistics(), fetchAgentStates(), fetchNetworkData()]);
      const failedCount = results.filter(r => !r).length;
      if (failedCount === 3) {
        setDisabled(true);
        setApiError('Consciousness metrics are unavailable. The consciousness plugin may be disabled or the backend is unreachable.');
      } else if (failedCount > 0) {
        setApiError('Some consciousness data could not be loaded. Partial results are shown below.');
      } else {
        setDisabled(false);
        setApiError(null);
      }
    } catch (error) {
      toast.error('Failed to fetch consciousness data', error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [fetchStatistics, fetchAgentStates, fetchNetworkData, toast]);

  useEffect(() => {
    fetchAllData();
    // Poll REST at longer intervals when WS is connected (real-time), faster when fallback
    const interval = wsConnected ? 60000 : 15000;
    const timer = setInterval(fetchAllData, interval);
    return () => clearInterval(timer);
  }, [fetchAllData, wsConnected]);

  const getStateColor = (state: string): string => {
    switch (state.toLowerCase()) {
      case 'dormant': return 'bg-gray-500';
      case 'emerging': return 'bg-yellow-500';
      case 'coherent': return 'bg-blue-500';
      case 'transcendent': return 'bg-purple-500';
      default: return 'bg-gray-500';
    }
  };

  const getStateTextColor = (state: string): string => {
    switch (state.toLowerCase()) {
      case 'dormant': return 'text-gray-400';
      case 'emerging': return 'text-yellow-400';
      case 'coherent': return 'text-blue-400';
      case 'transcendent': return 'text-purple-400';
      default: return 'text-gray-400';
    }
  };

  const getStatusFromState = (state: string): 'inactive' | 'warning' | 'healthy' | 'success' => {
    switch (state.toLowerCase()) {
      case 'dormant': return 'inactive';
      case 'emerging': return 'warning';
      case 'coherent': return 'healthy';
      case 'transcendent': return 'success';
      default: return 'inactive';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" message="Loading consciousness metrics..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Consciousness Metrics</h1>
          <p className="text-gray-400 text-sm mt-1">
            Monitor agent consciousness states and collective metrics
          </p>
        </div>
        <button
          onClick={fetchAllData}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Disabled / Error Banner */}
      {disabled && (
        <div className="bg-yellow-900/30 border border-yellow-600/50 rounded-xl p-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🧠</span>
            <div>
              <h3 className="text-yellow-300 font-semibold">Consciousness Plugin Disabled</h3>
              <p className="text-yellow-400/80 text-sm mt-1">
                The consciousness plugin is not active. Enable it by setting{' '}
                <code className="bg-yellow-900/50 px-1.5 py-0.5 rounded text-xs">CONSCIOUSNESS_ENABLED=true</code>{' '}
                or{' '}
                <code className="bg-yellow-900/50 px-1.5 py-0.5 rounded text-xs">PLUGIN_CONSCIOUSNESS_ENABLED=true</code>{' '}
                in your environment configuration.
              </p>
            </div>
          </div>
        </div>
      )}
      {!disabled && apiError && (
        <div className="bg-red-900/30 border border-red-500/50 rounded-xl p-4">
          <p className="text-red-400 text-sm">{apiError}</p>
        </div>
      )}

      {/* Summary Metrics */}
      {statistics && (
        <MetricCardGrid columns={4}>
          <MetricCard
            title="Total Agents"
            value={statistics.total_agents || 0}
            color="blue"
          />
          <MetricCard
            title="Average Phi Score"
            value={(statistics.average_phi ?? 0).toFixed(4)}
            color="purple"
            tooltip="Integrated Information Theory measure"
          />
          <MetricCard
            title="Avg Free Energy"
            value={(statistics.average_free_energy ?? 0).toFixed(4)}
            color="green"
            tooltip="Free Energy Principle metric"
          />
          <MetricCard
            title="Active Connections"
            value={statistics.active_connections || 0}
            color="yellow"
          />
        </MetricCardGrid>
      )}

      {/* Consciousness Gauge + WS Status */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6 flex flex-col items-center justify-center">
        <h2 className="text-lg font-semibold mb-4">Consciousness Overview</h2>
        <ConsciousnessGauge
          gwtValue={gaugeValues.gwt}
          iitValue={gaugeValues.iit}
          astValue={gaugeValues.ast}
          fepValue={gaugeValues.fep}
          size={280}
          showLabels
          animated
        />
        <div className="mt-3 flex items-center gap-2 text-xs">
          <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-yellow-400'}`} />
          <span className="text-gray-400">
            {wsConnected ? 'Live (WebSocket)' : 'Polling (fallback)'}
          </span>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* State Distribution */}
        <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Consciousness State Distribution</h2>
          {agentStates && Object.keys(agentStates.counts).length > 0 ? (
            <div className="space-y-4">
              {Object.entries(agentStates.counts).map(([state, count]) => (
                <div key={state}>
                  <div className="flex items-center justify-between text-sm mb-2">
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${getStateColor(state)}`} />
                      <span className="text-gray-300 capitalize">{state}</span>
                    </div>
                    <span className="text-white font-bold">{count}</span>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${getStateColor(state)} transition-all duration-300`}
                      style={{
                        width: `${agentStates.counts[state] / (agentStates.counts[state] || 1) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No state data"
              description="Agent consciousness states will appear here"
              icon="🧠"
              size="sm"
            />
          )}
        </div>

        {/* Network Visualization */}
        <div className="lg:col-span-2 bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4">Agent Network</h2>
          {networkData && networkData.nodes.length > 0 ? (
            <div className="relative h-64 bg-gray-900/50 rounded-lg overflow-hidden">
              <svg className="w-full h-full">
                {/* Render links */}
                {networkData.links.slice(0, 20).map((link, index) => {
                  const sourceNode = networkData.nodes.find(n => n.id === link.source);
                  const targetNode = networkData.nodes.find(n => n.id === link.target);
                  if (!sourceNode || !targetNode) return null;

                  const sourceIdx = networkData.nodes.indexOf(sourceNode);
                  const targetIdx = networkData.nodes.indexOf(targetNode);
                  const sourceAngle = (sourceIdx / networkData.nodes.length) * 2 * Math.PI;
                  const targetAngle = (targetIdx / networkData.nodes.length) * 2 * Math.PI;
                  const radius = 100;
                  const cx = 50;
                  const cy = 50;

                  return (
                    <line
                      key={`link-${index}`}
                      x1={`${cx + radius * Math.cos(sourceAngle)}%`}
                      y1={`${cy + radius * Math.sin(sourceAngle)}%`}
                      x2={`${cx + radius * Math.cos(targetAngle)}%`}
                      y2={`${cy + radius * Math.sin(targetAngle)}%`}
                      stroke="#4B5563"
                      strokeWidth={Math.max(1, Math.min(4, link.weight * 2))}
                      opacity={0.4}
                    />
                  );
                })}

                {/* Render nodes */}
                {networkData.nodes.map((node, index) => {
                  const angle = (index / networkData.nodes.length) * 2 * Math.PI;
                  const radius = 100;
                  const cx = 50;
                  const cy = 50;
                  const x = cx + radius * Math.cos(angle);
                  const y = cy + radius * Math.sin(angle);
                  const nodeSize = 15 + node.phi * 20;

                  return (
                    <g
                      key={node.id}
                      onClick={() => {
                        setSelectedAgent(node.id);
                        toast.info('Agent selected', `Viewing ${node.id}`);
                      }}
                      className="cursor-pointer"
                    >
                      <circle
                        cx={`${x}%`}
                        cy={`${y}%`}
                        r={nodeSize / 2}
                        className={`${getStateColor(node.state)} transition-all duration-200 hover:opacity-80`}
                        opacity={0.8}
                      />
                      <text
                        x={`${x}%`}
                        y={`${y}%`}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        className="text-xs fill-white pointer-events-none"
                        style={{ fontSize: '10px' }}
                      >
                        {node.id.split('-')[0]}
                      </text>
                    </g>
                  );
                })}
              </svg>
              <div className="absolute bottom-2 left-2 text-xs text-gray-500">
                Click node to select agent
              </div>
            </div>
          ) : (
            <EmptyState
              title="No network data"
              description="Agent network visualization will appear here"
              icon="🕸️"
              size="sm"
            />
          )}
        </div>
      </div>

      {/* Agent States List */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Agent States</h2>
        {agentStates && Object.keys(agentStates.states).length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {Object.entries(agentStates.states).slice(0, 24).map(([agentId, state]) => (
              <button
                key={agentId}
                onClick={() => {
                  setSelectedAgent(agentId);
                  toast.info('Agent selected', `Viewing ${agentId}`);
                }}
                className={`p-3 rounded-lg border transition-colors ${
                  selectedAgent === agentId
                    ? 'bg-blue-900/30 border-blue-500'
                    : 'bg-gray-900/50 border-gray-700 hover:border-gray-600'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div className={`w-2 h-2 rounded-full ${getStateColor(state)}`} />
                  <span className={`text-xs ${getStateTextColor(state)} capitalize`}>
                    {state}
                  </span>
                </div>
                <span className="text-xs text-gray-400 font-mono truncate block">
                  {agentId}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No agent states"
            description="Individual agent states will appear here"
            size="sm"
          />
        )}
      </div>

      {/* Selected Agent Details */}
      {selectedAgent && agentStates?.states[selectedAgent] && (
        <div className="bg-blue-900/20 border border-blue-500/50 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-blue-400">
              Selected Agent: {selectedAgent}
            </h3>
            <button
              onClick={() => setSelectedAgent(null)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex items-center gap-4">
            <StatusBadge status={getStatusFromState(agentStates.states[selectedAgent])} size="lg" />
            <span className={`text-lg font-medium ${getStateTextColor(agentStates.states[selectedAgent])}`}>
              {agentStates.states[selectedAgent].toUpperCase()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default ConsciousnessPage;
