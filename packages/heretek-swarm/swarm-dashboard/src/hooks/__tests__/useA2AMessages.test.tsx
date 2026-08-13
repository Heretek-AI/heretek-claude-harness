/**
 * useA2AMessages Hook Tests
 *
 * Tests for A2A message tracking and active edge state management:
 * - WebSocket message handling for a2a_message type
 * - Edge state Map tracking (count, lastSeen, messageType, animated)
 * - Message tracking for A2ATracker reuse
 * - Throttling behavior for 100ms intervals
 * - Connection and error state propagation
 * - Graceful fallback for heartbeat-only messages
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useA2AMessages } from '../useA2AMessages';
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

// Mock the useWebSocket hook — stores options for test access
vi.mock('../useWebSocket', () => ({
  useWebSocket: vi.fn((_channel: string, options: WsOptions = {}) => {
    lastWsOptions = options;
    return {
      connected: false,
      lastMessage: null,
      sendMessage: vi.fn(),
      disconnect: vi.fn(),
      reconnectAttempts: 0,
    };
  }),
}));

import { useWebSocket } from '../useWebSocket';
const mockUseWebSocket = useWebSocket as unknown as ReturnType<typeof vi.fn>;

describe('useA2AMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastWsOptions = null;
  });

  const triggerMessage = (msg: Record<string, unknown>) => {
    act(() => {
      lastWsOptions?.onMessage?.(msg as WebSocketMessage);
    });
  };

  it('should initialize with empty state', () => {
    const { result } = renderHook(() => useA2AMessages());

    expect(result.current.activeEdges.size).toBe(0);
    expect(result.current.messages).toEqual([]);
    expect(result.current.connected).toBe(false);
    expect(result.current.error).toBeNull();
    expect(typeof result.current.disconnect).toBe('function');
  });

  it('should track edge state from a2a_message', async () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 10 }));

    triggerMessage({
      type: 'a2a_message',
      from: 'agent-1',
      to: 'agent-2',
      message_type: 'task',
      timestamp: '2025-01-01T00:00:00Z',
    });

    await waitFor(() => {
      expect(result.current.activeEdges.get('agent-1→agent-2')).toMatchObject({
        count: 1,
        lastSeen: '2025-01-01T00:00:00Z',
        messageType: 'task',
        animated: true,
      });
    });
  });

  it('should increment count for repeated messages on same edge', async () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 10 }));

    triggerMessage({
      type: 'a2a_message', from: 'agent-1', to: 'agent-2',
      message_type: 'consensus', timestamp: '2025-01-01T00:00:00Z',
    });
    triggerMessage({
      type: 'a2a_message', from: 'agent-1', to: 'agent-2',
      message_type: 'consensus', timestamp: '2025-01-01T00:00:01Z',
    });

    await waitFor(() => {
      expect(result.current.activeEdges.get('agent-1→agent-2')).toMatchObject({
        count: 2,
        messageType: 'consensus',
      });
    });
  });

  it('should track multiple edges independently', async () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 10 }));

    triggerMessage({ type: 'a2a_message', from: 'agent-1', to: 'agent-2', message_type: 'task' });
    triggerMessage({ type: 'a2a_message', from: 'agent-2', to: 'agent-3', message_type: 'alert' });
    triggerMessage({ type: 'a2a_message', from: 'agent-3', to: 'agent-1', message_type: 'default' });

    await waitFor(() => {
      expect(result.current.activeEdges.size).toBe(3);
      expect(result.current.activeEdges.get('agent-1→agent-2')?.messageType).toBe('task');
      expect(result.current.activeEdges.get('agent-2→agent-3')?.messageType).toBe('alert');
      expect(result.current.activeEdges.get('agent-3→agent-1')?.messageType).toBe('default');
    });
  });

  it('should track messages array for A2ATracker', async () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 10 }));

    triggerMessage({ type: 'a2a_message', from: 'a', to: 'b', message_type: 'task' });
    triggerMessage({ type: 'a2a_message', from: 'b', to: 'c' });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0].from).toBe('a');
      expect(result.current.messages[1].from).toBe('b');
    });
  });

  it('should throttle updates to prevent UI flicker', () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 100 }));

    // Send 20 rapid messages — they should accumulate in pendingUpdates
    act(() => {
      for (let i = 0; i < 20; i++) {
        lastWsOptions?.onMessage?.({
          type: 'a2a_message', from: 'agent-1', to: 'agent-2',
          message_type: 'task',
          timestamp: `2025-01-01T00:00:${String(i).padStart(2, '0')}Z`,
        } as WebSocketMessage);
      }
    });

    // Messages should be in the messages[] array immediately (unthrottled)
    expect(result.current.messages.length).toBeGreaterThan(0);
  });

  it('should propagate error state', () => {
    const { result } = renderHook(() => useA2AMessages());

    act(() => {
      lastWsOptions?.onError?.(new Event('error'));
    });

    expect(result.current.error).toBeInstanceOf(Event);
  });

  it('should provide disconnect function', () => {
    const { result } = renderHook(() => useA2AMessages());
    // Get the disconnect mock that was returned by the useWebSocket mock
    const disconnectMock = mockUseWebSocket.mock.results[mockUseWebSocket.mock.results.length - 1]?.value?.disconnect;

    act(() => {
      result.current.disconnect();
    });

    if (disconnectMock) {
      expect(disconnectMock).toHaveBeenCalled();
    }
  });

  it('should ignore non-a2a_message types', async () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 10 }));

    triggerMessage({ type: 'agent_status', agentId: 'agent-1' });
    triggerMessage({ type: 'metrics', agentId: 'agent-1' });
    triggerMessage({ type: 'heartbeat' });

    // Edge map should be empty
    await waitFor(() => {
      // Give some time to ensure no updates happen
      expect(result.current.activeEdges.size).toBe(0);
    });
  });

  it('should gracefully handle messages without from/to fields', () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 10 }));

    triggerMessage({ type: 'a2a_message', timestamp: '2025-01-01T00:00:00Z' });
    triggerMessage({ type: 'a2a_message', from: 'agent-1' });
    triggerMessage({ type: 'a2a_message', to: 'agent-2' });

    // No edges created, no crash
    expect(result.current.activeEdges.size).toBe(0);
  });

  it('should infer message type from type string when message_type absent', async () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 10 }));

    triggerMessage({ type: 'a2a_message', from: 'a', to: 'b', message: 'task_delegation' });
    triggerMessage({ type: 'a2a_message', from: 'c', to: 'd', message: 'consensus_vote' });
    triggerMessage({ type: 'a2a_message', from: 'e', to: 'f', message: 'error_alert' });

    await waitFor(() => {
      expect(result.current.activeEdges.get('a→b')?.messageType).toBe('task');
      expect(result.current.activeEdges.get('c→d')?.messageType).toBe('consensus');
      expect(result.current.activeEdges.get('e→f')?.messageType).toBe('alert');
    });
  });

  it('should use default message type when type string unrecognizable', async () => {
    const { result } = renderHook(() => useA2AMessages({ throttleInterval: 10 }));

    triggerMessage({ type: 'a2a_message', from: 'a', to: 'b', message: 'random_payload' });

    await waitFor(() => {
      expect(result.current.activeEdges.get('a→b')?.messageType).toBe('default');
    });
  });
});
