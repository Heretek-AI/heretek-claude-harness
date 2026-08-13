/**
 * Real-Time Agent Updates Hook
 *
 * Provides WebSocket-based real-time updates for agent status, workflow progress, and metrics.
 * Replaces polling-based updates with push-based WebSocket communication.
 *
 * Features:
 * - Real-time agent status updates
 * - Workflow progress tracking
 * - Metrics streaming
 * - Connection status monitoring
 * - Automatic reconnection with exponential backoff
 * - Update throttling to prevent UI flicker
 *
 * @packageDocumentation
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useWebSocket, WebSocketMessage } from './useWebSocket';

// ============================================================================
// Message Types
// ============================================================================

/**
 * Agent status update message
 */
export interface AgentStatusUpdate {
  type: 'agent_status';
  agentId: string;
  status: 'active' | 'idle' | 'processing' | 'error';
  currentTask?: string;
  lastHeartbeat: string;
}

/**
 * Workflow progress update message
 */
export interface WorkflowProgressUpdate {
  type: 'workflow_progress';
  workflowId: string;
  currentNode: string;
  phase: 'plan' | 'analyze' | 'execute' | 'validate' | 'report';
  progress: number; // 0-100
}

/**
 * Metrics update message
 */
export interface MetricsUpdate {
  type: 'metrics';
  agentId: string;
  metrics: {
    phi?: number;
    coherence?: number;
    load?: number;
    queueSize?: number;
  };
}

/**
 * Union type for all update messages
 */
export type RealTimeUpdate = AgentStatusUpdate | WorkflowProgressUpdate | MetricsUpdate;

// ============================================================================
// Hook Options and State
// ============================================================================

/**
 * Options for the useRealTimeAgentUpdates hook
 */
export interface UseRealTimeAgentUpdatesOptions {
  /** Enable agent status updates */
  enableAgentStatus?: boolean;
  /** Enable workflow progress updates */
  enableWorkflowProgress?: boolean;
  /** Enable metrics updates */
  enableMetrics?: boolean;
  /** Throttle interval in milliseconds (default: 100ms) */
  throttleInterval?: number;
  /** Custom WebSocket URL (optional) */
  wsUrl?: string;
}

/**
 * State returned by the useRealTimeAgentUpdates hook
 */
export interface UseRealTimeAgentUpdatesState {
  /** Map of agent statuses by agent ID */
  agentStatuses: Record<string, AgentStatusUpdate>;
  /** Map of workflow progress by workflow ID */
  workflowProgress: Record<string, WorkflowProgressUpdate>;
  /** Map of agent metrics by agent ID */
  agentMetrics: Record<string, MetricsUpdate>;
  /** WebSocket connection status */
  connected: boolean;
  /** Connection error if any */
  error: Error | null;
  /** Number of reconnection attempts */
  reconnectAttempts: number;
  /** Last update timestamp */
  lastUpdate: Date | null;
  /** Send a message through the WebSocket */
  sendMessage: (message: WebSocketMessage) => boolean;
  /** Disconnect from WebSocket */
  disconnect: () => void;
}

// ============================================================================
// Throttle Utility
// ============================================================================

/**
 * Creates a throttled function that limits execution to once per interval.
 * Uses trailing edge invocation (executes at end of interval).
 */
function createThrottledCallback<T extends (...args: unknown[]) => void>(
  callback: T,
  interval: number
): T {
  let lastCall = 0;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let pendingArgs: Parameters<T> | null = null;

  const throttled = ((...args: Parameters<T>) => {
    const now = Date.now();

    if (now - lastCall >= interval) {
      // Execute immediately if interval has passed
      lastCall = now;
      callback(...args);
    } else {
      // Schedule for later execution
      pendingArgs = args;

      if (!timeoutId) {
        timeoutId = setTimeout(() => {
          timeoutId = null;
          if (pendingArgs) {
            lastCall = Date.now();
            callback(...pendingArgs);
            pendingArgs = null;
          }
        }, interval - (now - lastCall));
      }
    }
  }) as T;

  // Add cancel method for cleanup
  (throttled as any).cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    pendingArgs = null;
  };

  return throttled;
}

// ============================================================================
// Main Hook
// ============================================================================

/**
 * Hook for real-time agent updates via WebSocket
 *
 * @param options - Configuration options
 * @returns State and control functions
 *
 * @example
 * ```typescript
 * const {
 *   agentStatuses,
 *   workflowProgress,
 *   connected,
 *   error
 * } = useRealTimeAgentUpdates({
 *   enableAgentStatus: true,
 *   enableMetrics: true,
 *   throttleInterval: 100
 * });
 * ```
 */
export function useRealTimeAgentUpdates(
  options: UseRealTimeAgentUpdatesOptions = {}
): UseRealTimeAgentUpdatesState {
  const {
    enableAgentStatus = true,
    enableWorkflowProgress = false,
    enableMetrics = true,
    throttleInterval = 100,
  } = options;

  // State
  const [agentStatuses, setAgentStatuses] = useState<Record<string, AgentStatusUpdate>>({});
  const [workflowProgress, setWorkflowProgress] = useState<Record<string, WorkflowProgressUpdate>>({});
  const [agentMetrics, setAgentMetrics] = useState<Record<string, MetricsUpdate>>({});
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Refs for tracking
  const messageQueue = useRef<RealTimeUpdate[]>([]);
  const lastMessageTime = useRef<Record<string, number>>({});

  // Process incoming message
  const processMessage = useCallback((message: WebSocketMessage) => {
    const now = Date.now();

    // Validate message has type field
    if (!message || typeof message !== 'object' || !('type' in message)) {
      console.warn('Invalid WebSocket message received:', message);
      return;
    }

    const messageType = message.type as string;

    // Throttle check per message type
    const messageKey = `${messageType}-${(message as any).agentId || (message as any).workflowId}`;
    const lastTime = lastMessageTime.current[messageKey] || 0;

    if (now - lastTime < throttleInterval) {
      // Queue message for later processing
      messageQueue.current.push(message as unknown as RealTimeUpdate);
      return;
    }

    lastMessageTime.current[messageKey] = now;
    setLastUpdate(new Date());

    // Process based on message type
    switch (messageType) {
      case 'agent_status': {
        const statusUpdate = message as unknown as AgentStatusUpdate;
        setAgentStatuses(prev => ({
          ...prev,
          [statusUpdate.agentId]: statusUpdate,
        }));
        break;
      }

      case 'workflow_progress': {
        const progressUpdate = message as unknown as WorkflowProgressUpdate;
        setWorkflowProgress(prev => ({
          ...prev,
          [progressUpdate.workflowId]: progressUpdate,
        }));
        break;
      }

      case 'metrics': {
        const metricsUpdate = message as unknown as MetricsUpdate;
        setAgentMetrics(prev => ({
          ...prev,
          [metricsUpdate.agentId]: metricsUpdate,
        }));
        break;
      }

      default:
        // Unknown message type - ignore
        break;
    }

    // Process any queued messages
    if (messageQueue.current.length > 0) {
      const queued = messageQueue.current.shift();
      if (queued) {
        setTimeout(() => processMessage(queued as unknown as WebSocketMessage), throttleInterval);
      }
    }
  }, [throttleInterval]);

  // Create throttled message processor
  const throttledProcessMessage = useRef(
    createThrottledCallback(processMessage as (...args: unknown[]) => void, throttleInterval)
  );

  // Update throttled processor when dependencies change
  useEffect(() => {
    (throttledProcessMessage.current as { cancel?: () => void }).cancel?.();
    throttledProcessMessage.current = createThrottledCallback(
      processMessage as (...args: unknown[]) => void,
      throttleInterval
    );
  }, [processMessage, throttleInterval]);

  // Use base WebSocket hook
  const {
    connected,
    lastMessage,
    sendMessage,
    disconnect,
    reconnectAttempts,
  } = useWebSocket('dashboard', {
    onMessage: throttledProcessMessage.current,
    onOpen: () => {
      // Subscribe to enabled channels
      const subscriptions: string[] = [];
      if (enableAgentStatus) subscriptions.push('agent_status');
      if (enableWorkflowProgress) subscriptions.push('workflow_progress');
      if (enableMetrics) subscriptions.push('metrics');

      subscriptions.forEach(channel => {
        sendMessage({
          type: 'subscribe',
          channel,
        });
      });
    },
    onClose: () => {
    },
    onError: (error) => {
      console.error('Real-time updates error:', error);
    },
    reconnectInterval: 1000,
    maxReconnectAttempts: 10,
  });

  // Process last message through throttled handler
  useEffect(() => {
    if (lastMessage && connected) {
      throttledProcessMessage.current(lastMessage);
    }
  }, [lastMessage, connected]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      (throttledProcessMessage.current as any).cancel?.();
      messageQueue.current = [];
    };
  }, []);

  return {
    agentStatuses,
    workflowProgress,
    agentMetrics,
    connected,
    error: null,
    reconnectAttempts,
    lastUpdate,
    sendMessage,
    disconnect,
  };
}

// ============================================================================
// Convenience Hooks
// ============================================================================

/**
 * Hook for agent status updates only
 */
export function useAgentStatus(options?: { throttleInterval?: number }) {
  const { agentStatuses, connected, error } = useRealTimeAgentUpdates({
    enableAgentStatus: true,
    enableWorkflowProgress: false,
    enableMetrics: false,
    throttleInterval: options?.throttleInterval || 100,
  });

  return { agentStatuses, connected, error };
}

/**
 * Hook for workflow progress updates only
 */
export function useWorkflowProgress(options?: { throttleInterval?: number }) {
  const { workflowProgress, connected, error } = useRealTimeAgentUpdates({
    enableAgentStatus: false,
    enableWorkflowProgress: true,
    enableMetrics: false,
    throttleInterval: options?.throttleInterval || 100,
  });

  return { workflowProgress, connected, error };
}

/**
 * Hook for metrics updates only
 */
export function useAgentMetrics(options?: { throttleInterval?: number }) {
  const { agentMetrics, connected, error } = useRealTimeAgentUpdates({
    enableAgentStatus: false,
    enableWorkflowProgress: false,
    enableMetrics: true,
    throttleInterval: options?.throttleInterval || 100,
  });

  return { agentMetrics, connected, error };
}

export default useRealTimeAgentUpdates;
