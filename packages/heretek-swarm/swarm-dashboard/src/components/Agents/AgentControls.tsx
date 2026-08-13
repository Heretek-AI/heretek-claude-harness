/**
 * AgentControls Component
 *
 * Start/Stop/Restart controls for agent instances.
 */

import React, { useState, useCallback } from 'react';
import { StatusBadge } from '../UI/StatusBadge';

export type AgentState = 'available' | 'deployed' | 'running' | 'stopped' | 'suspended' | 'error';

interface AgentControlsProps {
  instanceId: string;
  state: AgentState;
  onStart?: (instanceId: string) => Promise<void>;
  onStop?: (instanceId: string) => Promise<void>;
  onSuspend?: (instanceId: string) => Promise<void>;
  onResume?: (instanceId: string) => Promise<void>;
  onRemove?: (instanceId: string) => Promise<void>;
  compact?: boolean;
}

export function AgentControls({
  instanceId,
  state,
  onStart,
  onStop,
  onSuspend,
  onResume,
  onRemove,
  compact = false,
}: AgentControlsProps) {
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [showConfirmRemove, setShowConfirmRemove] = useState(false);

  const getStateLabel = (s: AgentState): string => {
    const labels: Record<AgentState, string> = {
      available: 'Available',
      deployed: 'Deployed',
      running: 'Running',
      stopped: 'Stopped',
      suspended: 'Suspended',
      error: 'Error',
    };
    return labels[s] || s;
  };

  const getStateBadgeStatus = (s: AgentState): 'healthy' | 'active' | 'warning' | 'error' | 'inactive' | 'pending' => {
    const statusMap: Record<AgentState, 'healthy' | 'active' | 'warning' | 'error' | 'inactive' | 'pending'> = {
      running: 'healthy',
      deployed: 'active',
      suspended: 'active',
      stopped: 'inactive',
      error: 'error',
      available: 'pending',
    };
    return statusMap[s] || 'inactive';
  };

  const handleAction = useCallback(async (action: string, handler?: (id: string) => Promise<void>) => {
    if (!handler || actionInProgress) return;

    setActionInProgress(action);
    try {
      await handler(instanceId);
    } finally {
      setActionInProgress(null);
    }
  }, [instanceId, actionInProgress]);

  const handleRemove = useCallback(async () => {
    if (!onRemove || actionInProgress) return;

    setActionInProgress('remove');
    try {
      await onRemove(instanceId);
    } finally {
      setActionInProgress(null);
      setShowConfirmRemove(false);
    }
  }, [instanceId, onRemove, actionInProgress]);

  const isRunning = state === 'running';
  const isStopped = state === 'stopped';
  const isSuspended = state === 'suspended';
  const isDeployed = state === 'deployed';

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <StatusBadge status={getStateBadgeStatus(state)} size="sm" />
        <span className="text-xs text-gray-400">{getStateLabel(state)}</span>

        {isRunning && onStop && (
          <button
            onClick={() => handleAction('stop', onStop)}
            disabled={!!actionInProgress}
            className="text-xs text-red-400 hover:text-red-300 disabled:text-gray-600 transition-colors"
          >
            Stop
          </button>
        )}

        {(isStopped || isDeployed) && onStart && (
          <button
            onClick={() => handleAction('start', onStart)}
            disabled={!!actionInProgress}
            className="text-xs text-green-400 hover:text-green-300 disabled:text-gray-600 transition-colors"
          >
            Start
          </button>
        )}

        {isRunning && onSuspend && (
          <button
            onClick={() => handleAction('suspend', onSuspend)}
            disabled={!!actionInProgress}
            className="text-xs text-yellow-400 hover:text-yellow-300 disabled:text-gray-600 transition-colors"
          >
            Suspend
          </button>
        )}

        {isSuspended && onResume && (
          <button
            onClick={() => handleAction('resume', onResume)}
            disabled={!!actionInProgress}
            className="text-xs text-green-400 hover:text-green-300 disabled:text-gray-600 transition-colors"
          >
            Resume
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      {/* Status Indicator */}
      <div className="flex items-center gap-2 min-w-[120px]">
        <StatusBadge status={getStateBadgeStatus(state)} size="md" />
        <span className="text-sm text-gray-300">{getStateLabel(state)}</span>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        {/* Start Button */}
        {(isStopped || isDeployed) && onStart && (
          <button
            onClick={() => handleAction('start', onStart)}
            disabled={!!actionInProgress}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm font-medium transition-colors"
          >
            {actionInProgress === 'start' ? (
              <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            ) : (
              '▶'
            )}
            Start
          </button>
        )}

        {/* Stop Button */}
        {isRunning && onStop && (
          <button
            onClick={() => handleAction('stop', onStop)}
            disabled={!!actionInProgress}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm font-medium transition-colors"
          >
            {actionInProgress === 'stop' ? (
              <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            ) : (
              '⏹'
            )}
            Stop
          </button>
        )}

        {/* Suspend Button */}
        {isRunning && onSuspend && (
          <button
            onClick={() => handleAction('suspend', onSuspend)}
            disabled={!!actionInProgress}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm font-medium transition-colors"
          >
            ⏸ Suspend
          </button>
        )}

        {/* Resume Button */}
        {isSuspended && onResume && (
          <button
            onClick={() => handleAction('resume', onResume)}
            disabled={!!actionInProgress}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm font-medium transition-colors"
          >
            ▶ Resume
          </button>
        )}

        {/* Remove Button */}
        {onRemove && state !== 'running' && (
          <>
            {!showConfirmRemove ? (
              <button
                onClick={() => setShowConfirmRemove(true)}
                disabled={!!actionInProgress}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 rounded text-sm font-medium transition-colors"
              >
                🗑 Remove
              </button>
            ) : (
              <div className="flex items-center gap-2 bg-red-900/30 border border-red-700 rounded px-3 py-1.5">
                <span className="text-xs text-red-400">Sure?</span>
                <button
                  onClick={handleRemove}
                  disabled={!!actionInProgress}
                  className="text-xs px-2 py-1 bg-red-600 hover:bg-red-700 rounded transition-colors"
                >
                  Yes
                </button>
                <button
                  onClick={() => setShowConfirmRemove(false)}
                  disabled={!!actionInProgress}
                  className="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                >
                  No
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Loading Overlay */}
      {actionInProgress && (
        <div className="absolute inset-0 bg-black/20 backdrop-blur-[1px] rounded-lg flex items-center justify-center">
          <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 flex items-center gap-2">
            <svg className="animate-spin h-4 w-4 text-blue-400" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span className="text-sm text-white capitalize">{actionInProgress}ing...</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentControls;
