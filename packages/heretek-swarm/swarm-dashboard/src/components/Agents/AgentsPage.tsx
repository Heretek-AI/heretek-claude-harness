/**
 * Agents Page
 *
 * Enhanced agent management view with deployment workflow,
 * lifecycle controls, and configuration management.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DataTable, Column } from '../UI/DataTable';
import { StatusBadge } from '../UI/StatusBadge';
import { MetricCard, MetricCardGrid } from '../UI/MetricCard';
import { LoadingSpinner } from '../UI/LoadingSpinner';
import { EmptyState } from '../UI/EmptyState';
import { useToast } from '../UI/Toast';
import {
  getAgents,
  getAvailableAgentTypes,
  getAgentInstances,
  startAgent,
  stopAgent,
  suspendAgent,
  resumeAgent,
  removeAgent,
  deployAgent,
  updateAgentConfig,
  getRegistryStats,
  Agent as LegacyAgent,
  AgentType,
  AgentInstance,
} from '../../api/agents';
import { AgentCard, AgentInstance as AgentInstanceType } from './AgentCard';
import { DeployAgentModal, DeployConfig } from './DeployAgentModal';
import { AgentConfigPanel, AgentConfig } from './AgentConfigPanel';
import { AgentControls, AgentState } from './AgentControls';

interface AgentsPageData {
  legacyAgents: LegacyAgent[];
  instances: AgentInstance[];
  agentTypes: AgentType[];
  total: number;
  activeCount: number;
  inactiveCount: number;
  errorCount: number;
  runningCount: number;
}

export function AgentsPage() {
  const [data, setData] = useState<AgentsPageData>({
    legacyAgents: [],
    instances: [],
    agentTypes: [],
    total: 0,
    activeCount: 0,
    inactiveCount: 0,
    errorCount: 0,
    runningCount: 0,
  });
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'list' | 'cards'>('cards');
  const [filterType, setFilterType] = useState<string>('all');
  const [selectedAgent, setSelectedAgent] = useState<LegacyAgent | null>(null);
  const [selectedInstance, setSelectedInstance] = useState<AgentInstance | null>(null);
  const [showAgentDetails, setShowAgentDetails] = useState(false);
  const [showConfigPanel, setShowConfigPanel] = useState(false);

  // Modal states
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [selectedAgentType, setSelectedAgentType] = useState<AgentType | null>(null);

  const toast = useToast();

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch legacy agents (supervisor-managed)
      const legacyResponse = await getAgents();
      const legacyAgents = legacyResponse.agents || [];

      // Fetch deployed instances
      const instancesResponse = await getAgentInstances();
      const instances = instancesResponse.instances || [];

      // Fetch available agent types
      const typesResponse = await getAvailableAgentTypes();
      const agentTypes = typesResponse.available_agents || [];

      // Calculate stats
      const runningCount = instances.filter((inst: AgentInstance) => inst.state === 'running').length;
      const deployedCount = instances.filter((inst: AgentInstance) => inst.state === 'deployed' || inst.state === 'stopped').length;

      setData({
        legacyAgents,
        instances,
        agentTypes,
        total: legacyAgents.length + instances.length,
        activeCount: legacyAgents.filter((a: LegacyAgent) => a.status === 'active').length + runningCount,
        inactiveCount: legacyAgents.filter((a: LegacyAgent) => a.status === 'inactive').length + deployedCount,
        errorCount: legacyAgents.filter((a: LegacyAgent) => a.status === 'error').length + instances.filter((inst: AgentInstance) => inst.state === 'error').length,
        runningCount,
      });
    } catch (error) {
      console.error('Failed to fetch agents:', error);
      toast.error('Failed to fetch agents', error instanceof Error ? error.message : 'Unknown error');
      setData({
        legacyAgents: [],
        instances: [],
        agentTypes: [],
        total: 0,
        activeCount: 0,
        inactiveCount: 0,
        errorCount: 0,
        runningCount: 0,
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, [fetchAllData]);

  // Lifecycle action handlers
  const handleDeploy = useCallback(async (agentType: string, config: DeployConfig) => {
    try {
      await deployAgent(agentType, config);
      toast.success('Agent deployed', `${agentType} instance deployed successfully`);
      fetchAllData();
    } catch (error) {
      toast.error('Deployment failed', error instanceof Error ? error.message : 'Unknown error');
      throw error;
    }
  }, [toast, fetchAllData]);

  const handleStart = useCallback(async (instanceId: string) => {
    try {
      await startAgent(instanceId);
      toast.success('Agent started', `Instance ${instanceId} is now running`);
      fetchAllData();
    } catch (error) {
      toast.error('Failed to start agent', error instanceof Error ? error.message : 'Unknown error');
    }
  }, [toast, fetchAllData]);

  const handleStop = useCallback(async (instanceId: string) => {
    try {
      await stopAgent(instanceId);
      toast.success('Agent stopped', `Instance ${instanceId} has been stopped`);
      fetchAllData();
    } catch (error) {
      toast.error('Failed to stop agent', error instanceof Error ? error.message : 'Unknown error');
    }
  }, [toast, fetchAllData]);

  const handleSuspend = useCallback(async (instanceId: string) => {
    try {
      await suspendAgent(instanceId);
      toast.success('Agent suspended', `Instance ${instanceId} is now suspended`);
      fetchAllData();
    } catch (error) {
      toast.error('Failed to suspend agent', error instanceof Error ? error.message : 'Unknown error');
    }
  }, [toast, fetchAllData]);

  const handleResume = useCallback(async (instanceId: string) => {
    try {
      await resumeAgent(instanceId);
      toast.success('Agent resumed', `Instance ${instanceId} is now running`);
      fetchAllData();
    } catch (error) {
      toast.error('Failed to resume agent', error instanceof Error ? error.message : 'Unknown error');
    }
  }, [toast, fetchAllData]);

  const handleRemove = useCallback(async (instanceId: string) => {
    try {
      await removeAgent(instanceId);
      toast.success('Agent removed', `Instance ${instanceId} has been removed`);
      fetchAllData();
    } catch (error) {
      toast.error('Failed to remove agent', error instanceof Error ? error.message : 'Unknown error');
    }
  }, [toast, fetchAllData]);

  const handleUpdateConfig = useCallback(async (instanceId: string, config: AgentConfig) => {
    try {
      await updateAgentConfig(instanceId, config);
      toast.success('Configuration updated', `Agent ${instanceId} configuration saved`);
      fetchAllData();
    } catch (error) {
      toast.error('Failed to update config', error instanceof Error ? error.message : 'Unknown error');
      throw error;
    }
  }, [toast, fetchAllData]);

  const handleDeployClick = useCallback((agentType: AgentType) => {
    setSelectedAgentType(agentType);
    setShowDeployModal(true);
  }, []);

  const handleInstanceSelect = useCallback((instance: AgentInstance) => {
    setSelectedInstance(instance);
    setShowConfigPanel(true);
  }, []);

  const getStatusFromType = (type: string): 'healthy' | 'active' | 'warning' | 'error' | 'inactive' | 'pending' => {
    const statusMap: Record<string, 'healthy' | 'active' | 'warning' | 'error' | 'inactive' | 'pending'> = {
      'active': 'active',
      'inactive': 'inactive',
      'error': 'error',
      'starting': 'pending',
      'dormant': 'inactive',
      'emerging': 'warning',
      'coherent': 'healthy',
      'transcendent': 'healthy',
      'running': 'healthy',
      'deployed': 'active',
      'stopped': 'inactive',
      'suspended': 'active',
    };
    return statusMap[type.toLowerCase()] || 'inactive';
  };

  const getInstanceState = (state: string): AgentState => {
    return state as AgentState;
  };

  // Filter instances by type (memoized — only recompute when filter or instances change)
  const filteredInstances = useMemo(
    () =>
      filterType === 'all'
        ? data.instances
        : data.instances.filter((inst: AgentInstance) => inst.agent_type === filterType),
    [data.instances, filterType],
  );

  // Group instances by type for card view (memoized — powers list rendering)
  const instancesByType = useMemo(
    () =>
      filteredInstances.reduce((acc, inst) => {
        if (!acc[inst.agent_type]) {
          acc[inst.agent_type] = [];
        }
        acc[inst.agent_type].push(inst);
        return acc;
      }, {} as Record<string, AgentInstance[]>),
    [filteredInstances],
  );

  const columns: Column<AgentInstance>[] = [
    {
      key: 'instance_id',
      title: 'Instance ID',
      sortable: true,
      filterable: true,
      width: '250px',
      render: (value: string | boolean | Record<string, unknown>) => (
        <span className="font-mono text-sm text-blue-400">{String(value)}</span>
      ),
    },
    {
      key: 'agent_type',
      title: 'Type',
      sortable: true,
      filterable: true,
      width: '150px',
      render: (value: string | boolean | Record<string, unknown>) => (
        <span className="text-gray-300 capitalize">{String(value)}</span>
      ),
    },
    {
      key: 'state',
      title: 'Status',
      sortable: true,
      filterable: true,
      width: '120px',
      render: (value: string | boolean | Record<string, unknown>) => (
        <StatusBadge status={getStatusFromType(String(value))} size="sm" />
      ),
    },
    {
      key: 'actions',
      title: 'Actions',
      width: '280px',
      render: (_: unknown, row: AgentInstance) => (
        <AgentControls
          instanceId={row.instance_id}
          state={getInstanceState(row.state)}
          onStart={handleStart}
          onStop={handleStop}
          onSuspend={handleSuspend}
          onResume={handleResume}
          onRemove={handleRemove}
          compact
        />
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" message="Loading agents..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agents</h1>
          <p className="text-gray-400 text-sm mt-1">
            Manage and deploy swarm agents
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* View Toggle */}
          <div className="flex items-center bg-gray-800 rounded-lg p-1">
            <button
              onClick={() => setViewMode('cards')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                viewMode === 'cards'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Cards
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                viewMode === 'list'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              List
            </button>
          </div>
          <button
            onClick={fetchAllData}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors"
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Summary Metrics */}
      <MetricCardGrid columns={4}>
        <MetricCard
          title="Total Agents"
          value={data.total}
          color="blue"
        />
        <MetricCard
          title="Running"
          value={data.runningCount}
          color="green"
        />
        <MetricCard
          title="Deployed"
          value={data.inactiveCount}
          color="gray"
        />
        <MetricCard
          title="Errors"
          value={data.errorCount}
          color={data.errorCount > 0 ? 'red' : 'green'}
        />
      </MetricCardGrid>

      {/* Filter Bar */}
      {data.agentTypes.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          <button
            onClick={() => setFilterType('all')}
            className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
              filterType === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            All Types
          </button>
          {data.agentTypes.map((type) => {
            const count = instancesByType[type.type_name]?.length || 0;
            return (
              <button
                key={type.type_name}
                onClick={() => setFilterType(type.type_name)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                  filterType === type.type_name
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                {type.type_name} ({count})
              </button>
            );
          })}
        </div>
      )}

      {/* Content Area */}
      {viewMode === 'cards' ? (
        /* Card View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.agentTypes.map((agentType) => (
            <AgentCard
              key={agentType.type_name}
              agent={agentType}
              instances={instancesByType[agentType.type_name] || []}
              onDeploy={() => handleDeployClick(agentType)}
              onStart={handleStart}
              onStop={handleStop}
              onSelect={(agent: { type_name: string; module_path: string; description: string; capabilities: string[]; topics: string[]; actor_type: string }) => handleDeployClick(agent as AgentType)}
            />
          ))}

          {data.agentTypes.length === 0 && (
            <div className="col-span-full">
              <EmptyState
                icon="🤖"
                title="No agent types available"
                description="Agent types will appear here when discovered"
                action={{
                  label: 'Refresh',
                  onClick: fetchAllData,
                }}
              />
            </div>
          )}
        </div>
      ) : (
        /* List View */
        <div>
          {filteredInstances.length > 0 ? (
            <DataTable
              data={filteredInstances}
              columns={columns}
              keyExtractor={(instance) => instance.instance_id}
              onRowClick={handleInstanceSelect}
              sortable
              filterable
              filterPlaceholder="Search instances by ID or type..."
              emptyMessage="No agent instances found"
              pageSize={10}
            />
          ) : (
            <EmptyState
              icon="🤖"
              title="No agent instances deployed"
              description="Deploy an agent to get started"
              action={
                data.agentTypes.length > 0
                  ? {
                      label: 'Deploy Agent',
                      onClick: () => handleDeployClick(data.agentTypes[0]),
                    }
                  : {
                      label: 'Refresh',
                      onClick: fetchAllData,
                    }
              }
            />
          )}
        </div>
      )}

      {/* Deploy Modal */}
      <DeployAgentModal
        agentType={selectedAgentType}
        isOpen={showDeployModal}
        onClose={() => {
          setShowDeployModal(false);
          setSelectedAgentType(null);
        }}
        onDeploy={handleDeploy}
      />

      {/* Config Panel */}
      {showConfigPanel && selectedInstance && (
        <AgentConfigPanel
          instanceId={selectedInstance.instance_id}
          config={selectedInstance.config as AgentConfig}
          onUpdate={handleUpdateConfig}
          onClose={() => {
            setShowConfigPanel(false);
            setSelectedInstance(null);
          }}
        />
      )}

      {/* Legacy Agents Section */}
      {data.legacyAgents.length > 0 && (
        <div className="border-t border-gray-700 pt-6">
          <h2 className="text-lg font-semibold mb-4">Legacy Agents (Supervisor-Managed)</h2>
          <DataTable<LegacyAgent>
            data={data.legacyAgents}
            columns={[
              {
                key: 'id',
                title: 'Agent ID',
                sortable: true,
                filterable: true,
                width: '200px',
                render: (value) => (
                  <span className="font-mono text-sm text-blue-400">{String(value)}</span>
                ),
              },
              {
                key: 'type',
                title: 'Type',
                sortable: true,
                filterable: true,
                width: '150px',
                render: (value) => (
                  <span className="text-gray-300 capitalize">{String(value)}</span>
                ),
              },
              {
                key: 'status',
                title: 'Status',
                sortable: true,
                filterable: true,
                width: '120px',
                render: (value) => (
                  <StatusBadge status={getStatusFromType(String(value))} size="sm" />
                ),
              },
              {
                key: 'lastActivity',
                title: 'Last Activity',
                sortable: true,
                width: '180px',
                formatValue: (value) => {
                  const strValue = typeof value === 'string' ? value : undefined;
                  if (!strValue) return 'Never';
                  return new Date(strValue).toLocaleString();
                },
              },
            ]}
            keyExtractor={(agent) => agent.id}
            onRowClick={(agent) => {
              setSelectedAgent(agent);
              setShowAgentDetails(true);
            }}
            sortable
            filterable
            filterPlaceholder="Search legacy agents..."
            emptyMessage="No legacy agents"
            pageSize={5}
          />
        </div>
      )}

      {/* Agent Details Modal (Legacy) */}
      {showAgentDetails && selectedAgent && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-800 border border-gray-700 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-auto">
            <div className="flex items-center justify-between p-6 border-b border-gray-700">
              <h2 className="text-xl font-bold">Agent Details</h2>
              <button
                onClick={() => setShowAgentDetails(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-400">Agent ID</label>
                  <p className="font-mono text-blue-400">{selectedAgent.id}</p>
                </div>
                <div>
                  <label className="text-sm text-gray-400">Type</label>
                  <p className="text-white capitalize">{selectedAgent.type}</p>
                </div>
                <div>
                  <label className="text-sm text-gray-400">Status</label>
                  <StatusBadge status={getStatusFromType(selectedAgent.status)} />
                </div>
                <div>
                  <label className="text-sm text-gray-400">Last Activity</label>
                  <p className="text-white">
                    {selectedAgent.lastActivity
                      ? new Date(selectedAgent.lastActivity).toLocaleString()
                      : 'Never'}
                  </p>
                </div>
              </div>

              {/* Consciousness Metrics */}
              {selectedAgent.consciousness_metrics && (
                <div className="border-t border-gray-700 pt-4">
                  <h3 className="text-sm font-semibold text-gray-400 mb-3">Consciousness Metrics</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-900 rounded-lg p-3">
                      <label className="text-xs text-gray-500">GWT Score</label>
                      <p className="text-lg font-bold text-blue-400">
                        {selectedAgent.consciousness_metrics.gwt_score.toFixed(4)}
                      </p>
                    </div>
                    <div className="bg-gray-900 rounded-lg p-3">
                      <label className="text-xs text-gray-500">Phi Value</label>
                      <p className="text-lg font-bold text-purple-400">
                        {selectedAgent.consciousness_metrics.phi_value.toFixed(4)}
                      </p>
                    </div>
                    <div className="bg-gray-900 rounded-lg p-3">
                      <label className="text-xs text-gray-500">AST Competence</label>
                      <p className="text-lg font-bold text-green-400">
                        {selectedAgent.consciousness_metrics.ast_competence.toFixed(4)}
                      </p>
                    </div>
                    <div className="bg-gray-900 rounded-lg p-3">
                      <label className="text-xs text-gray-500">Free Energy</label>
                      <p className="text-lg font-bold text-yellow-400">
                        {selectedAgent.consciousness_metrics.free_energy.toFixed(4)}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentsPage;
