/**
 * Agent Node Component for Workflow Builder
 *
 * Displays an agent node in the visual workflow builder.
 * Handles agent selection and configuration.
 *
 * Features:
 * - Click on agent node → opens configuration panel
 * - Double-click for detailed configuration
 * - Visual status indicators
 * - Dynamic handles based on channel subscriptions
 */

import React, { memo, useCallback } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { useAgentHandles, getHandleColor, type AgentHandle } from '../../hooks/useAgentHandles';
import DynamicHandles from './DynamicHandles';

interface AgentData {
  agentId: string;
  agentType:
    | 'steward'
    | 'alpha'
    | 'beta'
    | 'charlie'
    | 'explorer'
    | 'examiner'
    | 'coder'
    | 'dreamer'
    | 'empath'
    | 'historian'
    | 'sentinel'
    | 'sentinel-prime'
    | 'metis'
    | 'nexus'
    | 'perceiver'
    | 'chronos'
    | 'catalyst'
    | 'coordinator'
    | 'arbiter'
    | 'prism'
    | 'habit-forge';
  status: 'idle' | 'thinking' | 'acting' | 'error';
  lastActivity?: string;
  onOpenConfig?: (nodeId: string) => void;
  enableDynamicHandles?: boolean;
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

const agentIcons: Record<AgentData['agentType'], string> = {
  steward: '🎯',
  alpha: '🧠',
  beta: '✅',
  charlie: '🔍',
  explorer: '🗺️',
  examiner: '🔬',
  coder: '💻',
  dreamer: '💭',
  empath: '💜',
  historian: '📚',
  sentinel: '🛡️',
  'sentinel-prime': '🛡️',
  metis: '🧘',
  nexus: '🌐',
  perceiver: '👁️',
  chronos: '⏰',
  catalyst: '⚗️',
  coordinator: '📊',
  arbiter: '⚖️',
  prism: '🔮',
  'habit-forge': '🔨',
};

function AgentNode({ data, selected }: NodeProps<AgentData>) {
  const colors = statusColors[data.status] || statusColors.idle;
  const icon = agentIcons[data.agentType] || '🤖';

  // Use dynamic handles hook
  const { handles, subscriptions, isLoading, error } = useAgentHandles({
    agentId: data.agentId,
    enabled: data.enableDynamicHandles ?? true,
  });

  const timeAgo = (timestamp: string) => {
    const now = new Date();
    const past = new Date(timestamp);
    const diff = Math.floor((now.getTime() - past.getTime()) / 1000);

    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  // Handle click to open configuration panel
  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (data.onOpenConfig) {
        data.onOpenConfig(data.agentId);
      }
    },
    [data],
  );

  // Handle double-click for quick edit
  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (data.onOpenConfig) {
        data.onOpenConfig(data.agentId);
      }
    },
    [data],
  );

  // Handle click on a specific handle
  const handleHandleClick = useCallback((handleId: string) => {
    // Could open channel configuration or show channel details
  }, []);

  // Derive visual state: execution status overrides agent status when present
  const execStatus = data.executionStatus;
  const isRunning = execStatus === 'running';
  const isCompleted = execStatus === 'completed';
  const isFailed = execStatus === 'failed';

  // Compute border/glow based on execution status
  const executionBorder = isRunning
    ? 'border-blue-500 shadow-blue-500/40 shadow-[0_0_12px_rgba(59,130,246,0.5)]'
    : isCompleted
      ? 'border-green-500 shadow-green-500/30'
      : isFailed
        ? 'border-red-500 shadow-red-500/30'
        : '';

  return (
    <div
      className={`
        px-4 py-3 rounded-lg shadow-lg border-2 transition-all duration-200
        ${selected ? 'ring-2 ring-white ring-offset-2 ring-offset-gray-900' : ''}
        hover:shadow-xl hover:scale-105
        cursor-pointer
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
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      title={
        isFailed ? `Failed: ${data.executionError || 'Unknown error'}` : 'Click to configure agent'
      }
    >
      {/* Dynamic Handles or Static Fallback */}
      {handles.length > 0 ? (
        <DynamicHandles handles={handles} onHandleClick={handleHandleClick} />
      ) : (
        <>
          {/* Target Handle (input) - Static fallback */}
          <Handle
            type="target"
            position={Position.Top}
            className="!bg-gray-600 !border-2 !border-gray-500"
            onClick={(e) => e.stopPropagation()}
          />

          {/* Source Handle (output) - Static fallback */}
          <Handle
            type="source"
            position={Position.Bottom}
            className="!bg-gray-600 !border-2 !border-gray-500"
            onClick={(e) => e.stopPropagation()}
          />
        </>
      )}

      {/* Header with config indicator */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        <div className="flex items-center gap-2">
          {/* Execution status badge takes priority over agent status */}
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
          <span className="text-xs" title="Click to configure">
            ⚙️
          </span>
        </div>
      </div>

      {/* Agent Info */}
      <div className="space-y-1">
        <div className="text-sm font-medium text-gray-900">
          {data.agentType.charAt(0).toUpperCase() + data.agentType.slice(1)}
        </div>
        <div className="text-xs text-gray-600">ID: {data.agentId}</div>
        {data.lastActivity && (
          <div className="text-xs text-gray-500">{timeAgo(data.lastActivity)}</div>
        )}
        {/* Execution results */}
        {execStatus === 'completed' && data.executionDuration !== undefined && (
          <div className="text-xs text-green-400">✓ {data.executionDuration}ms</div>
        )}
        {isFailed && data.executionError && (
          <div className="text-xs text-red-400 truncate max-w-[200px]" title={data.executionError}>
            ✗ {data.executionError}
          </div>
        )}
        {/* Channel subscription count */}
        {subscriptions.length > 0 && (
          <div className="text-xs text-gray-400 flex items-center gap-1">
            <span>📡</span>
            <span>{subscriptions.length} channels</span>
          </div>
        )}
        {isLoading && <div className="text-xs text-blue-400">Loading channels...</div>}
        {error && (
          <div className="text-xs text-red-400" title={error.message}>
            ⚠️ Channel error
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(AgentNode);
export { AgentNode };
