/**
 * Tool Node Component for Workflow Builder
 *
 * Displays a tool node in the visual workflow builder.
 * Handles tool configuration and execution.
 */

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import type { ToolType } from './types';

interface ToolData {
  toolId: string;
  toolName: string;
  toolType:
    | 'code_execution'
    | 'web_browser'
    | 'file_operations'
    | 'api_connector'
    | 'database'
    | 'vector_search'
    | 'custom';
  status: 'idle' | 'thinking' | 'acting' | 'error';
  lastActivity?: string;
}

const statusColors = {
  idle: { border: '#6B7280', bg: '#374151', text: '#9CA3AF' },
  thinking: { border: '#3B82F6', bg: '#1E3A5F', text: '#60A5FA' },
  acting: { border: '#22C55E', bg: '#14532D', text: '#4ADE80' },
  error: { border: '#EF4444', bg: '#7F1D1D', text: '#F87171' },
};

const toolIcons: Record<ToolData['toolType'], string> = {
  code_execution: '⚡',
  web_browser: '🌐',
  file_operations: '📁',
  api_connector: '🔌',
  database: '🗄️',
  vector_search: '🔍',
  custom: '🔧',
};

function ToolNode({ data, selected }: NodeProps<ToolData>) {
  const colors = statusColors[data.status] || statusColors.idle;
  const icon = toolIcons[data.toolType] || '🔧';

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
        minWidth: '220px',
        maxWidth: '280px',
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

      {/* Tool Info */}
      <div className="space-y-1">
        <div className="text-sm font-medium text-gray-900">
          {data.toolType.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())}
        </div>
        <div className="text-xs text-gray-600">ID: {data.toolId}</div>
        {data.toolName && <div className="text-xs text-gray-600">Name: {data.toolName}</div>}
        {data.lastActivity && (
          <div className="text-xs text-gray-500">{timeAgo(data.lastActivity)}</div>
        )}
      </div>

      {/* Source Handle (output) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-gray-600 !border-2 !border-gray-500"
      />
    </div>
  );
}

export default memo(ToolNode);
export { ToolNode };
