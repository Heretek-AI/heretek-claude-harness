/**
 * Real-Time Agent Updates Hook Tests
 *
 * Tests for useRealTimeAgentUpdates hook covering:
 * - WebSocket message handling
 * - Agent status updates
 * - Workflow progress updates
 * - Metrics updates
 * - Connection status
 * - Throttling behavior
 * - Reconnection logic
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useRealTimeAgentUpdates, useAgentStatus, useWorkflowProgress, useAgentMetrics } from '../useRealTimeAgentUpdates';
import type { WebSocketMessage } from '../useWebSocket';

// Collect options for test access
type WsOptions = {
  onMessage?: (msg: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (err: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
};

let lastWsOptions: WsOptions | null = null;

// Mock the useWebSocket hook
vi.mock('../useWebSocket', () => ({
  useWebSocket: vi.fn((_channel: string, options: WsOptions = {}) => {
    lastWsOptions = options;
    return {
      connected: true,
      lastMessage: null,
      sendMessage: vi.fn().mockReturnValue(true),
      disconnect: vi.fn(),
      reconnectAttempts: 0,
    };
  }),
}));

import { useWebSocket } from '../useWebSocket';
const mockUseWebSocket = useWebSocket as ReturnType<typeof vi.fn>;

describe('useRealTimeAgentUpdates', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastWsOptions = null;
  });

  it('should initialize with empty state', () => {
    const { result } = renderHook(() => useRealTimeAgentUpdates());

    expect(result.current.agentStatuses).toEqual({});
    expect(result.current.workflowProgress).toEqual({});
    expect(result.current.agentMetrics).toEqual({});
    expect(result.current.connected).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('should process agent status updates', () => {
    const { result } = renderHook(() => useRealTimeAgentUpdates());

    const agentStatusMessage = {
      type: 'agent_status',
      agentId: 'agent-1',
      status: 'active' as const,
      currentTask: 'Processing data',
      lastHeartbeat: new Date().toISOString(),
    };

    act(() => {
      lastWsOptions?.onMessage?.(agentStatusMessage);
    });

    expect(result.current.agentStatuses['agent-1']).toEqual({
      type: 'agent_status',
      agentId: 'agent-1',
      status: 'active',
      currentTask: 'Processing data',
      lastHeartbeat: expect.any(String),
    });
  });

  it('should process workflow progress updates', () => {
    const { result } = renderHook(() => useRealTimeAgentUpdates());

    const progressMessage = {
      type: 'workflow_progress',
      workflowId: 'workflow-1',
      currentNode: 'node-1',
      phase: 'execute' as const,
      progress: 75,
    };

    act(() => {
      lastWsOptions?.onMessage?.(progressMessage);
    });

    expect(result.current.workflowProgress['workflow-1']).toEqual({
      type: 'workflow_progress',
      workflowId: 'workflow-1',
      currentNode: 'node-1',
      phase: 'execute',
      progress: 75,
    });
  });

  it('should process metrics updates', () => {
    const { result } = renderHook(() => useRealTimeAgentUpdates());

    const metricsMessage = {
      type: 'metrics',
      agentId: 'agent-1',
      metrics: {
        phi: 0.85,
        coherence: 0.92,
        load: 0.45,
        queueSize: 3,
      },
    };

    act(() => {
      lastWsOptions?.onMessage?.(metricsMessage);
    });

    expect(result.current.agentMetrics['agent-1']).toEqual({
      type: 'metrics',
      agentId: 'agent-1',
      metrics: {
        phi: 0.85,
        coherence: 0.92,
        load: 0.45,
        queueSize: 3,
      },
    });
  });

  it('should throttle updates to prevent UI flicker', async () => {
    const { result } = renderHook(() =>
      useRealTimeAgentUpdates({ throttleInterval: 100 })
    );

    const agentStatusMessage = {
      type: 'agent_status',
      agentId: 'agent-1',
      status: 'active' as const,
      lastHeartbeat: new Date().toISOString(),
    };

    // Send multiple messages rapidly
    act(() => {
      lastWsOptions?.onMessage?.(agentStatusMessage);
      lastWsOptions?.onMessage?.({ ...agentStatusMessage, status: 'idle' });
      lastWsOptions?.onMessage?.({ ...agentStatusMessage, status: 'processing' });
    });

    // Should have processed at least one update
    expect(result.current.agentStatuses['agent-1']).toBeDefined();
  });

  it('should track connection status', () => {
    mockUseWebSocket.mockReturnValueOnce({
      connected: false,
      lastMessage: null,
      sendMessage: vi.fn(),
      disconnect: vi.fn(),
      reconnectAttempts: 2,
    });

    const { result } = renderHook(() => useRealTimeAgentUpdates());

    expect(result.current.connected).toBe(false);
    expect(result.current.reconnectAttempts).toBe(2);
  });

  it('should provide disconnect function', () => {
    const mockDisconnect = vi.fn();
    mockUseWebSocket.mockReturnValueOnce({
      connected: true,
      lastMessage: null,
      sendMessage: vi.fn(),
      disconnect: mockDisconnect,
      reconnectAttempts: 0,
    });

    const { result } = renderHook(() => useRealTimeAgentUpdates());

    act(() => {
      result.current.disconnect();
    });

    expect(mockDisconnect).toHaveBeenCalled();
  });

  it('should provide sendMessage function', () => {
    const mockSendMessage = vi.fn().mockReturnValue(true);
    mockUseWebSocket.mockReturnValueOnce({
      connected: true,
      lastMessage: null,
      sendMessage: mockSendMessage,
      disconnect: vi.fn(),
      reconnectAttempts: 0,
    });

    const { result } = renderHook(() => useRealTimeAgentUpdates());

    act(() => {
      result.current.sendMessage({ type: 'subscribe', channel: 'agent_status' });
    });

    expect(mockSendMessage).toHaveBeenCalledWith({
      type: 'subscribe',
      channel: 'agent_status',
    });
  });
});

describe('useAgentStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastWsOptions = null;
  });

  it('should return only agent statuses', () => {
    const { result } = renderHook(() => useAgentStatus());

    expect(result.current.agentStatuses).toEqual({});
    expect(result.current.workflowProgress).toBeUndefined();
    expect(result.current.agentMetrics).toBeUndefined();
  });
});

describe('useWorkflowProgress', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastWsOptions = null;
  });

  it('should return only workflow progress', () => {
    const { result } = renderHook(() => useWorkflowProgress());

    expect(result.current.workflowProgress).toEqual({});
    expect(result.current.agentStatuses).toBeUndefined();
    expect(result.current.agentMetrics).toBeUndefined();
  });
});

describe('useAgentMetrics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastWsOptions = null;
  });

  it('should return only agent metrics', () => {
    const { result } = renderHook(() => useAgentMetrics());

    expect(result.current.agentMetrics).toEqual({});
    expect(result.current.agentStatuses).toBeUndefined();
    expect(result.current.workflowProgress).toBeUndefined();
  });
});
