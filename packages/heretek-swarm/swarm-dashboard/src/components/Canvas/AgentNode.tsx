/**
 * Agent Node Component for ReactFlow
 *
 * Displays individual agent with status indicators and consciousness metrics.
 * Reference: MiniMax Audit Lines 488-535 (Flowise AgentNode pattern)
 */

import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

export interface ConsciousnessMetrics {
  gwt_score: number;
  phi_value: number;
  ast_competence: number;
  free_energy: number;
}

export interface AgentData {
  agentId: string;
  agentType: string;
  status: 'idle' | 'thinking' | 'acting' | 'error' | 'offline';
  consciousnessMetrics?: ConsciousnessMetrics;
  lastActivity: string;
  messageCount?: number;
  [key: string]: unknown;
}

interface AgentNodeProps {
  id: string;
  data: AgentData;
  selected?: boolean;
}

const statusColors: Record<string, { border: string; bg: string; text: string }> = {
  idle: { border: '#6B7280', bg: '#374151', text: '#9CA3AF' },
  thinking: { border: '#3B82F6', bg: '#1E3A5F', text: '#60A5FA' },
  acting: { border: '#22C55E', bg: '#14532D', text: '#4ADE80' },
  error: { border: '#EF4444', bg: '#7F1D1D', text: '#F87171' },
  offline: { border: '#4B5563', bg: '#1F2937', text: '#6B7280' },
};

const agentIcons: Record<string, string> = {
  steward: '🎯',
  alpha: '🔬',
  beta: '✅',
  charlie: '🎭',
  historian: '📚',
  metis: '🧠',
  empath: '💝',
  perceiver: '👁️',
  echo: '🔊',
  explorer: '🧭',
  examiner: '📋',
  dreamer: '💭',
  coder: '💻',
  sentinel: '🛡️',
  'sentinel-prime': '🛡️⚡',
  arbiter: '⚖️',
  coordinator: '🔄',
  nexus: '🔗',
  catalyst: '⚗️',
  chronos: '⏰',
  prism: '🔮',
  'habit-forge': '⚒️',
  'perceiver-plus': '👁️🧠',
};

function AgentNode({ data, selected }: AgentNodeProps) {
  const colors = statusColors[data.status] || statusColors.idle;
  const icon = agentIcons[data.agentType] || '🤖';

  const timeAgo = (timestamp: string) => {
    const now = new Date();
    const past = new Date(timestamp);
    const diff = Math.floor((now.getTime() - past.getTime()) / 1000);

    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  const renderMetricsBar = () => {
    if (!data.consciousnessMetrics) return null;
    const { gwt_score, phi_value, ast_competence, free_energy } = data.consciousnessMetrics;

    return (
      <div className="mt-2 space-y-1">
        <div className="flex items-center text-xs">
          <span className="text-gray-400 w-6">GWT</span>
          <div className="flex-1 bg-gray-700 rounded-full h-1">
            <div className="bg-blue-500 h-1 rounded-full" style={{ width: `${gwt_score * 100}%` }} />
          </div>
        </div>
        <div className="flex items-center text-xs">
          <span className="text-gray-400 w-6">Φ</span>
          <div className="flex-1 bg-gray-700 rounded-full h-1">
            <div className="bg-purple-500 h-1 rounded-full" style={{ width: `${phi_value * 100}%` }} />
          </div>
        </div>
        <div className="flex items-center text-xs">
          <span className="text-gray-400 w-6">AST</span>
          <div className="flex-1 bg-gray-700 rounded-full h-1">
            <div className="bg-green-500 h-1 rounded-full" style={{ width: `${ast_competence * 100}%` }} />
          </div>
        </div>
        <div className="flex items-center text-xs">
          <span className="text-gray-400 w-6">FEP</span>
          <div className="flex-1 bg-gray-700 rounded-full h-1">
            <div className="bg-orange-500 h-1 rounded-full" style={{ width: `${(1 - free_energy) * 100}%` }} />
          </div>
        </div>
      </div>
    );
  };

  return (
    <div
      className={`
        px-4 py-3 rounded-lg shadow-lg border-2 transition-all duration-200
        ${selected ? 'ring-2 ring-white ring-offset-2 ring-offset-gray-900' : ''}
      `}
      style={{
        backgroundColor: colors.bg,
        borderColor: colors.border,
        minWidth: '240px',
        maxWidth: '300px',
      }}
    >
      {/* Target Handle (input) */}
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-gray-600 !border-2 !border-gray-500"
        id="input-main"
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        <span
          className="text-xs font-semibold px-2 py-1 rounded uppercase"
          style={{
            backgroundColor: colors.border,
            color: '#FFFFFF',
          }}
        >
          {data.status}
        </span>
      </div>

      {/* Agent Type */}
      <div className="text-white font-bold text-lg mb-1">
        {data.agentType.toString().charAt(0).toUpperCase() + data.agentType.toString().slice(1).replace('-', ' ')}
      </div>

      {/* Agent ID */}
      <div className="text-gray-400 text-xs font-mono mb-2 truncate">
        {data.agentId}
      </div>

      {/* Consciousness Metrics */}
      {renderMetricsBar()}

      {/* Activity & Message Count */}
      <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
        <span>Active: {timeAgo(data.lastActivity)}</span>
        {data.messageCount !== undefined && (
          <span>💬 {data.messageCount}</span>
        )}
      </div>

      {/* Source Handle (output) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-gray-600 !border-2 !border-gray-500"
        id="output-main"
      />

      {/* Additional handle for multi-connection support */}
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-gray-600 !border-2 !border-gray-500 !w-3 !h-3"
        id="output-side"
        style={{ top: '50%', transform: 'translateY(-50%)' }}
      />
    </div>
  );
}

export default memo(AgentNode);
