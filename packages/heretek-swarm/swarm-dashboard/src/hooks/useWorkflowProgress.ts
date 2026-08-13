/**
 * useWorkflowProgress - Real-time workflow execution via WebSocket
 *
 * Connects to the backend WebSocket at /ws/workflows/progress and exposes
 * execution state (idle/running/completed/failed), current node, progress,
 * and per-node results. Handles reconnection with exponential backoff.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

// =============================================================================
// Types
// =============================================================================

export type ExecutionState = 'idle' | 'running' | 'completed' | 'failed';

export interface NodeResult {
  status: 'pending' | 'running' | 'completed' | 'failed';
  output?: unknown;
  error?: string;
  duration?: number;
}

/** Incoming message shape from the /ws/workflows/progress WebSocket channel (type: 'workflow_progress'). */
export interface WorkflowProgressMessage {
  type: string;
  workflowId?: string;
  currentNode?: string | null;
  phase?: string;
  progress?: number;
  status?: string;
  nodeResults?: Record<string, { status: string; output?: unknown; error?: string; duration?: number }>;
  error?: string;
  [key: string]: unknown;
}

interface UseWorkflowProgressReturn {
  executionState: ExecutionState;
  currentNode: string | null;
  progress: number;
  nodeResults: Map<string, NodeResult>;
  error: string | null;
  connected: boolean;
  executeWorkflow: (workflowId: string) => Promise<void>;
  reExecuteWorkflow: () => Promise<void>;
}

// =============================================================================
// Hook
// =============================================================================

export function useWorkflowProgress(): UseWorkflowProgressReturn {
  const [executionState, setExecutionState] = useState<ExecutionState>('idle');
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [nodeResults, setNodeResults] = useState<Map<string, NodeResult>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastWorkflowId = useRef<string | null>(null);
  const mountedRef = useRef(true);

  // Resolve API host for WebSocket URL construction (mirrors useWebSocket.ts)
  const getApiHost = useCallback((): string => {
    const envHost = import.meta.env.VITE_API_HOST || `http://${window.location.host}`;
    try {
      return localStorage.getItem('swarm_api_host') || envHost;
    } catch {
      return envHost;
    }
  }, []);

  /**
   * Build the WebSocket URL for the workflow progress channel.
   * Authenticates via api_key stored in localStorage.
   */
  const buildWsUrl = useCallback((workflowId?: string): string => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = new URL(getApiHost().startsWith('http') ? getApiHost() : `http://${getApiHost()}`).host;
    const apiKey = localStorage.getItem('api_key');
    const params = new URLSearchParams();
    if (apiKey) params.set('token', apiKey);
    if (workflowId) params.set('workflow_id', workflowId);
    const qs = params.toString();
    return `${protocol}//${host}/ws/workflows/progress${qs ? `?${qs}` : ''}`;
  }, [getApiHost]);

  /**
   * Subscribe to a specific workflow on the connected socket.
   */
  const subscribe = useCallback((workflowId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'subscribe', workflowId }));
    }
  }, []);

  /**
   * Unsubscribe from a workflow.
   */
  const unsubscribe = useCallback((workflowId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'unsubscribe', workflowId }));
    }
  }, []);

  /**
   * Connect to the workflow progress WebSocket and optionally subscribe.
   */
  const connect = useCallback((workflowId?: string) => {
    // Tear down existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const wsUrl = buildWsUrl(workflowId);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        reconnectAttempts.current = 0;

        // Subscribe once connected
        if (workflowId) {
          ws.send(JSON.stringify({ action: 'subscribe', workflowId }));
        }
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const msg: WorkflowProgressMessage = JSON.parse(event.data);

          // Ignore heartbeats
          if (msg.type === 'heartbeat') return;

          // Handle workflow_progress messages
          if (msg.type === 'workflow_progress') {
            if (msg.currentNode !== undefined) setCurrentNode(msg.currentNode ?? null);
            if (msg.progress !== undefined) setProgress(msg.progress);
            if (msg.status !== undefined) {
              const status = msg.status;
              if (status === 'completed') {
                setExecutionState('completed');
              } else if (status === 'failed') {
                setExecutionState('failed');
                if (msg.error) setError(msg.error);
              } else if (status === 'running' || status === 'started') {
                setExecutionState('running');
              }
            }
            // Merge node results
            if (msg.nodeResults) {
              setNodeResults((prev) => {
                const next = new Map(prev);
                for (const [nodeId, result] of Object.entries(msg.nodeResults!)) {
                  next.set(nodeId, result as NodeResult);
                }
                return next;
              });
            }
          }

          // Handle error messages from the server
          if (msg.type === 'error') {
            setError(msg.error || 'Unknown WebSocket error');
          }
        } catch (parseErr) {
          console.error('Failed to parse workflow progress message:', parseErr);
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);

        // Exponential backoff: 3s, 6s, 12s, max 30s
        if (reconnectAttempts.current < 10) {
          const delay = Math.min(3000 * Math.pow(2, reconnectAttempts.current), 30000);
          reconnectAttempts.current += 1;
          reconnectTimeout.current = setTimeout(() => {
            if (mountedRef.current) connect(lastWorkflowId.current ?? undefined);
          }, delay);
        }
      };

      ws.onerror = (err) => {
        console.error('Workflow progress WebSocket error:', err);
      };
    } catch (err) {
      console.error('Failed to create workflow progress WebSocket:', err);
    }
  }, [buildWsUrl]);

  /**
   * Disconnect and clean up.
   */
  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  /**
   * Execute a workflow: POST to the execute API, then subscribe via WebSocket.
   */
  const executeWorkflow = useCallback(async (workflowId: string) => {
    lastWorkflowId.current = workflowId;
    setError(null);
    setExecutionState('running');
    setCurrentNode(null);
    setProgress(0);
    setNodeResults(new Map());

    // If already connected, just (re)subscribe; otherwise connect first
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Unsubscribe from old workflow if different
      unsubscribe(workflowId);
      subscribe(workflowId);
    } else {
      connect(workflowId);
    }

    // POST to the execute endpoint
    try {
      const apiKey = localStorage.getItem('api_key');
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;

      const resp = await fetch(`${getApiHost()}/api/workflows/${workflowId}/execute`, {
        method: 'POST',
        headers,
      });

      if (!resp.ok) {
        const body = await resp.text().catch(() => '');
        throw new Error(`Execute failed (${resp.status}): ${body}`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setExecutionState('failed');
    }
  }, [connect, subscribe, unsubscribe, getApiHost]);

  /**
   * Re-execute the last executed workflow.
   */
  const reExecuteWorkflow = useCallback(async () => {
    if (!lastWorkflowId.current) {
      setError('No workflow has been executed yet');
      return;
    }
    await executeWorkflow(lastWorkflowId.current);
  }, [executeWorkflow]);

  // Connect on mount (lazy — only establishes socket, doesn't subscribe)
  // Do NOT auto-connect; the consumer calls executeWorkflow which triggers connect.
  // Cleanup on unmount.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [disconnect]);

  return {
    executionState,
    currentNode,
    progress,
    nodeResults,
    error,
    connected,
    executeWorkflow,
    reExecuteWorkflow,
  };
}
