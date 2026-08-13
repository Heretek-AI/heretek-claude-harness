/**
 * Decision Node Component for Workflow Builder
 *
 * Displays a decision node in visual workflow builder.
 * Handles conditional branching logic.
 */

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import type { DecisionNodeData } from './types';

interface DecisionData {
  condition: string;
  branches: Array<{ id: string; label: string; condition: string }>;
  status: 'idle' | 'thinking' | 'acting' | 'error';
  lastActivity?: string;
}

const statusColors = {
  idle: { border: '#6B7280', bg: '#374151', text: '#9CA3AF' },
  thinking: { border: '#3B82F6', bg: '#1E3A5F', text: '#60A5FA' },
  acting: { border: '#22C55E', bg: '#14532D', text: '#4ADE80' },
  error: { border: '#EF4444', bg: '#7F1D1D', text: '#F87171' },
};

function DecisionNode({ data, selected }: NodeProps<DecisionData>) {
  const colors = statusColors[data.status] || statusColors.idle;

  const timeAgo = (timestamp: string) => {
    const now = new Date();
    const past = new Date(timestamp);
    const diff = Math.floor((now.getTime() - past.getTime()) / 1000);

    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
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
        minWidth: '280px',
        maxWidth: '320px',
      }}
    >
      {/* Target Handle (input) */}
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-gray-600 !border-2 !border-gray-500"
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">🔀</span>
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

      {/* Decision Info */}
      <div className="space-y-2">
        <div className="text-sm font-medium text-gray-900">Condition: {data.condition}</div>
        {data.branches && data.branches.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-gray-700">Branches:</div>
            {data.branches.map((branch, index) => (
              <div key={branch.id} className="px-2 py-1 rounded border border-gray-300 text-xs">
                <div className="font-medium">{branch.label}</div>
                <div className="text-gray-600">{branch.condition}</div>
              </div>
            ))}
          </div>
        )}
        {data.lastActivity && (
          <div className="text-xs text-gray-500">{timeAgo(data.lastActivity)}</div>
        )}
      </div>

      {/* Source Handles (one per branch) */}
      {data.branches &&
        data.branches.map((branch, index) => (
          <Handle
            key={branch.id}
            type="source"
            position={Position.Bottom}
            id={branch.id}
            style={{
              left: `${((index + 1) / (data.branches!.length + 1)) * 100}%`,
            }}
            className="!bg-gray-600 !border-2 !border-gray-500"
          />
        ))}
    </div>
  );
}

export default memo(DecisionNode);
export { DecisionNode };
