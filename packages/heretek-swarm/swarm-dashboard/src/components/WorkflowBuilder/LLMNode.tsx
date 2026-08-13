/**
 * LLM Node Component for Workflow Builder
 *
 * Displays an LLM node in visual workflow builder.
 * Handles LLM model configuration.
 */

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';

interface LLMData {
  model: string;
  provider: 'openai' | 'anthropic' | 'google' | 'azure' | 'litellm' | 'custom';
  status: 'idle' | 'thinking' | 'acting' | 'error';
  lastActivity?: string;
  /** Execution status from useWorkflowProgress: pending | running | completed | failed */
  executionStatus?: 'pending' | 'running' | 'completed' | 'failed';
  executionOutput?: unknown;
  executionError?: string;
  executionDuration?: number;
}

const statusColors = {
  idle: { border: '#6B7280', bg: '#374151', text: '#9CA3AF' },
  thinking: { border: '#3B82F6', bg: '#1E3A5F', text: '#60A5FA' },
  acting: { border: '#22C55E', bg: '#14532D', text: '#4ADE80' },
  error: { border: '#EF4444', bg: '#7F1D1D', text: '#F87171' },
};

const providerIcons: Record<LLMData['provider'], string> = {
  openai: '🤖',
  anthropic: '🧠',
  google: '🔮',
  azure: '☁️',
  litellm: '⚡',
  custom: '🎯',
};

function LLMNode({ data, selected }: NodeProps<LLMData>) {
  const colors = statusColors[data.status] || statusColors.idle;
  const icon = providerIcons[data.provider] || '🎯';

  // Derive visual state: execution status overrides model status when present
  const execStatus = data.executionStatus;
  const isRunning = execStatus === 'running';
  const isCompleted = execStatus === 'completed';
  const isFailed = execStatus === 'failed';

  const executionBorder = isRunning
    ? 'shadow-blue-500/40 shadow-[0_0_12px_rgba(59,130,246,0.5)]'
    : isCompleted
      ? 'shadow-green-500/30'
      : isFailed
        ? 'shadow-red-500/30'
        : '';

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
        ${executionBorder}
      `}
      style={{
        backgroundColor: colors.bg,
        borderColor: isRunning
          ? '#3B82F6'
          : isCompleted
            ? '#22C55E'
            : isFailed
              ? '#EF4444'
              : colors.border,
        minWidth: '220px',
        maxWidth: '280px',
        ...(isRunning ? { animation: 'pulse 2s ease-in-out infinite' } : {}),
      }}
      title={isFailed ? `Failed: ${data.executionError || 'Unknown error'}` : undefined}
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
        {execStatus ? (
          <span
            className="text-xs font-semibold px-2 py-1 rounded uppercase"
            style={{
              backgroundColor: isRunning
                ? '#3B82F6'
                : isCompleted
                  ? '#22C55E'
                  : isFailed
                    ? '#EF4444'
                    : '#6B7280',
              color: '#FFFFFF',
            }}
          >
            {execStatus === 'running'
              ? '⏳ Running'
              : execStatus === 'completed'
                ? '✓ Done'
                : execStatus === 'failed'
                  ? '✗ Failed'
                  : execStatus}
          </span>
        ) : (
          <span
            className="text-xs font-semibold px-2 py-1 rounded uppercase"
            style={{
              backgroundColor: colors.border,
              color: '#FFFFFF',
            }}
          >
            {data.status}
          </span>
        )}
      </div>

      {/* LLM Info */}
      <div className="space-y-1">
        <div className="text-sm font-medium text-gray-900">
          {data.provider.charAt(0).toUpperCase() + data.provider.slice(1)}
        </div>
        <div className="text-xs text-gray-600">Model: {data.model}</div>
        {data.lastActivity && (
          <div className="text-xs text-gray-500">{timeAgo(data.lastActivity)}</div>
        )}
        {/* Execution results */}
        {isCompleted && data.executionDuration !== undefined && (
          <div className="text-xs text-green-400">✓ {data.executionDuration}ms</div>
        )}
        {isFailed && data.executionError && (
          <div className="text-xs text-red-400 truncate max-w-[200px]" title={data.executionError}>
            ✗ {data.executionError}
          </div>
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

export default memo(LLMNode);
export { LLMNode };
