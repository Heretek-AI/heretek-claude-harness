/**
 * AgentCard Component
 *
 * Visual display card for an agent type with metadata and actions.
 */

import React, { useCallback } from 'react';
import { StatusBadge } from '../UI/StatusBadge';

export interface AgentType {
  type_name: string;
  module_path: string;
  description: string;
  capabilities: string[];
  topics: string[];
  actor_type: string;
}

export interface AgentInstance {
  instance_id: string;
  agent_type: string;
  state: 'available' | 'deployed' | 'running' | 'stopped' | 'suspended' | 'error';
  config?: Record<string, unknown>;
  has_actor?: boolean;
}

interface AgentCardProps {
  agent: AgentType;
  instances?: AgentInstance[];
  onDeploy?: (agentType: string) => void;
  onStart?: (instanceId: string) => void;
  onStop?: (instanceId: string) => void;
  onSelect?: (agent: AgentType) => void;
  compact?: boolean;
}

export function AgentCard({
  agent,
  instances = [],
  onDeploy,
  onStart,
  onStop,
  onSelect,
  compact = false,
}: AgentCardProps) {
  const runningCount = instances.filter(inst => inst.state === 'running').length;
  const totalCount = instances.length;

  const getStatusColor = (state: string): 'healthy' | 'active' | 'warning' | 'error' | 'inactive' | 'pending' => {
    switch (state) {
      case 'running':
        return 'healthy';
      case 'deployed':
      case 'suspended':
        return 'active';
      case 'stopped':
        return 'inactive';
      case 'error':
        return 'error';
      case 'available':
        return 'pending';
      default:
        return 'inactive';
    }
  };

  const handleDeploy = useCallback(() => {
    onDeploy?.(agent.type_name);
  }, [onDeploy, agent.type_name]);

  const handleCardClick = useCallback(() => {
    onSelect?.(agent);
  }, [onSelect, agent]);

  if (compact) {
    return (
      <div
        onClick={handleCardClick}
        className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 hover:border-blue-500 transition-colors cursor-pointer"
      >
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <h3 className="text-white font-semibold">{agent.type_name}</h3>
            <p className="text-gray-400 text-sm mt-1 line-clamp-1">{agent.description}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-right">
              <div className="text-xs text-gray-500">Running</div>
              <div className="text-lg font-bold text-green-400">{runningCount}/{totalCount}</div>
            </div>
            {onDeploy && totalCount === 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeploy();
                }}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium transition-colors"
              >
                Deploy
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={handleCardClick}
      className="bg-gray-800 border border-gray-700 rounded-xl p-5 hover:border-blue-500 transition-all cursor-pointer group"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-white font-bold text-lg group-hover:text-blue-400 transition-colors">
              {agent.type_name}
            </h3>
            <span className="text-xs text-gray-500 bg-gray-700 px-2 py-0.5 rounded">
              {agent.actor_type}
            </span>
          </div>
          <p className="text-gray-400 text-sm mt-2 line-clamp-2">{agent.description}</p>
        </div>
      </div>

      {/* Instance Status */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-gray-500">Instances</span>
          <div className="flex items-center gap-2">
            <span className="text-green-400 font-medium">{runningCount} running</span>
            <span className="text-gray-600">/</span>
            <span className="text-gray-400">{totalCount} total</span>
          </div>
        </div>
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-green-500 to-green-400 transition-all duration-300"
            style={{ width: `${totalCount > 0 ? (runningCount / totalCount) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Capabilities */}
      {agent.capabilities.length > 0 && (
        <div className="mb-4">
          <div className="text-xs text-gray-500 mb-2">Capabilities</div>
          <div className="flex flex-wrap gap-1.5">
            {agent.capabilities.slice(0, 4).map((cap, idx) => (
              <span
                key={idx}
                className="text-xs text-blue-300 bg-blue-900/30 px-2 py-1 rounded"
              >
                {cap}
              </span>
            ))}
            {agent.capabilities.length > 4 && (
              <span className="text-xs text-gray-500 px-1">
                +{agent.capabilities.length - 4} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Instance States */}
      {instances.length > 0 && (
        <div className="mb-4 pt-4 border-t border-gray-700">
          <div className="text-xs text-gray-500 mb-2">Active Instances</div>
          <div className="space-y-1.5">
            {instances.slice(0, 3).map((inst) => (
              <div key={inst.instance_id} className="flex items-center justify-between text-sm">
                <span className="text-gray-400 font-mono text-xs truncate max-w-[150px]">
                  {inst.instance_id}
                </span>
                <div className="flex items-center gap-2">
                  <StatusBadge status={getStatusColor(inst.state)} size="sm" />
                  {inst.state === 'running' && onStop && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onStop(inst.instance_id);
                      }}
                      className="text-xs text-red-400 hover:text-red-300 transition-colors"
                    >
                      Stop
                    </button>
                  )}
                  {inst.state === 'stopped' && onStart && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onStart(inst.instance_id);
                      }}
                      className="text-xs text-green-400 hover:text-green-300 transition-colors"
                    >
                      Start
                    </button>
                  )}
                </div>
              </div>
            ))}
            {instances.length > 3 && (
              <div className="text-xs text-gray-500 text-center pt-1">
                +{instances.length - 3} more instances
              </div>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      {onDeploy && totalCount === 0 && (
        <div className="pt-4 border-t border-gray-700">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleDeploy();
            }}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
          >
            🚀 Deploy Agent
          </button>
        </div>
      )}
    </div>
  );
}

export default AgentCard;
