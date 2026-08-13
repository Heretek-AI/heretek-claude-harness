/**
 * useConsciousnessWebSocket Hook Tests
 *
 * Tests for consciousness metric tracking via WebSocket:
 * - WebSocket message handling for phi_update, fep_update, agency_update types
 * - Per-agent state Map tracking (phi_score, free_energy, agency_score, etc.)
 * - Partial updates merge correctly across event types
 * - Throttling behavior for 100ms intervals to prevent UI flicker
 * - Connection and error state propagation
 * - Non-consciousness event types are ignored
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';
import { useConsciousnessWebSocket } from '../useConsciousnessWebSocket';

// Mock the useWebSocket hook using Vitest
const mockUseWebSocket = vi.fn(() => ({
  connected: false,
  lastMessage: null,
  sendMessage: vi.fn(),
  disconnect: vi.fn(),
  reconnectAttempts: 0,
}));

vi.mock('../useWebSocket', () => ({
  useWebSocket: (...args: unknown[]) => mockUseWebSocket(...args),
}));

describe('useConsciousnessWebSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should initialize with empty agentStates Map', () => {
    const { result } = renderHook(() => useConsciousnessWebSocket());

    expect(result.current.agentStates.size).toBe(0);
    expect(result.current.connected).toBe(false);
    expect(result.current.error).toBeNull();
    expect(typeof result.current.disconnect).toBe('function');
  });

  it('should create agent state with phi_score from phi_update', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    const phiUpdate = {
      type: 'phi_update',
      agent_id: 'agent-1',
      phi_score: 0.85,
      state: 'active',
      timestamp: '2025-01-01T00:00:00Z',
    };

    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) callback(phiUpdate);
    });

    // Advance timers to flush throttled updates
    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      const state = result.current.agentStates.get('agent-1');
      expect(state).toMatchObject({
        phi_score: 0.85,
        state: 'active',
      });
    });
  });

  it('should update FEP fields from fep_update event', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    // First send a phi_update to create initial state
    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({
          type: 'phi_update',
          agent_id: 'agent-1',
          phi_score: 0.7,
          state: 'active',
          timestamp: '2025-01-01T00:00:00Z',
        });
      }
    });

    // Then send an fep_update
    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({
          type: 'fep_update',
          agent_id: 'agent-1',
          free_energy: 12.5,
          prediction_accuracy: 0.92,
          surprise: 0.08,
          belief_precision: 0.88,
          timestamp: '2025-01-01T00:00:01Z',
        });
      }
    });

    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      const state = result.current.agentStates.get('agent-1');
      expect(state).toMatchObject({
        phi_score: 0.7,
        free_energy: 12.5,
        prediction_accuracy: 0.92,
        surprise: 0.08,
        belief_precision: 0.88,
      });
    });
  });

  it('should update agency fields from agency_update event', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({
          type: 'agency_update',
          agent_id: 'nexus',
          agency_score: 0.95,
          autonomy_score: 0.78,
          timestamp: '2025-01-01T00:00:00Z',
        });
      }
    });

    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      const state = result.current.agentStates.get('nexus');
      expect(state).toMatchObject({
        agency_score: 0.95,
        autonomy_score: 0.78,
      });
    });
  });

  it('should merge partial updates correctly - phi then fep', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    // First: phi_update
    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({
          type: 'phi_update',
          agent_id: 'catalyst',
          phi_score: 0.9,
          state: 'processing',
          timestamp: '2025-01-01T00:00:00Z',
        });
      }
    });

    // Second: fep_update (separate event)
    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({
          type: 'fep_update',
          agent_id: 'catalyst',
          free_energy: 8.3,
          prediction_accuracy: 0.95,
          surprise: 0.05,
          belief_precision: 0.91,
          timestamp: '2025-01-01T00:00:01Z',
        });
      }
    });

    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      const state = result.current.agentStates.get('catalyst');
      // Both phi and FEP fields should be present
      expect(state).toMatchObject({
        phi_score: 0.9,
        state: 'processing',
        free_energy: 8.3,
        prediction_accuracy: 0.95,
      });
    });
  });

  it('should ignore non-consciousness event types', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({ type: 'agent_status', agent_id: 'agent-1', status: 'active' });
        callback({ type: 'heartbeat', agent_id: 'agent-1' });
        callback({ type: 'metrics', agent_id: 'agent-1', cpu: 45 });
      }
    });

    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      expect(result.current.agentStates.size).toBe(0);
    });
  });

  it('should ignore events without agent_id', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({ type: 'phi_update', phi_score: 0.8 });
        callback({ type: 'fep_update', free_energy: 10.0 });
      }
    });

    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      expect(result.current.agentStates.size).toBe(0);
    });
  });

  it('should throttle updates to prevent excessive re-renders', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    // Send 20 rapid phi_updates
    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        for (let i = 0; i < 20; i++) {
          callback({
            type: 'phi_update',
            agent_id: 'agent-1',
            phi_score: 0.5 + i * 0.02,
            state: 'active',
            timestamp: `2025-01-01T00:00:${String(i).padStart(2, '0')}Z`,
          });
        }
      }
    });

    // Only one state update should have occurred (after throttle)
    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      // Only one entry in the map (agent-1)
      expect(result.current.agentStates.size).toBe(1);
      // The last phi_score value should be set
      const state = result.current.agentStates.get('agent-1');
      expect(state?.phi_score).toBe(0.5 + 19 * 0.02);
    });
  });

  it('should initialize with disconnected state', () => {
    const { result } = renderHook(() => useConsciousnessWebSocket());
    expect(result.current.connected).toBe(false);
  });

  it('should propagate error state from WebSocket', () => {
    const mockError = new Event('error');
    mockUseWebSocket.mockReturnValueOnce({
      connected: false,
      lastMessage: null,
      sendMessage: vi.fn(),
      disconnect: vi.fn(),
      reconnectAttempts: 0,
    });

    const { result } = renderHook(() => useConsciousnessWebSocket());

    act(() => {
      const onError = mockUseWebSocket.mock.calls[0][1]?.onError;
      if (onError) onError(mockError);
    });

    expect(result.current.error).toBe(mockError);
  });

  it('should provide callable disconnect function', () => {
    const mockDisconnect = vi.fn();
    mockUseWebSocket.mockReturnValueOnce({
      connected: true,
      lastMessage: null,
      sendMessage: vi.fn(),
      disconnect: mockDisconnect,
      reconnectAttempts: 0,
    });

    const { result } = renderHook(() => useConsciousnessWebSocket());

    act(() => {
      result.current.disconnect();
    });

    expect(mockDisconnect).toHaveBeenCalled();
  });

  it('should track multiple agents independently', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({
          type: 'phi_update',
          agent_id: 'nexus',
          phi_score: 0.95,
          state: 'active',
          timestamp: '2025-01-01T00:00:00Z',
        });
        callback({
          type: 'phi_update',
          agent_id: 'catalyst',
          phi_score: 0.88,
          state: 'processing',
          timestamp: '2025-01-01T00:00:01Z',
        });
        callback({
          type: 'phi_update',
          agent_id: 'steward',
          phi_score: 0.92,
          state: 'active',
          timestamp: '2025-01-01T00:00:02Z',
        });
      }
    });

    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      expect(result.current.agentStates.size).toBe(3);
      expect(result.current.agentStates.get('nexus')?.phi_score).toBe(0.95);
      expect(result.current.agentStates.get('catalyst')?.phi_score).toBe(0.88);
      expect(result.current.agentStates.get('steward')?.phi_score).toBe(0.92);
    });
  });

  it('should merge agency_update with existing phi state', async () => {
    const { result } = renderHook(() => useConsciousnessWebSocket({ throttleInterval: 100 }));

    // First: phi_update
    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({
          type: 'phi_update',
          agent_id: 'nexus',
          phi_score: 0.95,
          state: 'active',
          timestamp: '2025-01-01T00:00:00Z',
        });
      }
    });

    // Then: agency_update
    act(() => {
      const callback = mockUseWebSocket.mock.calls[0][1]?.onMessage;
      if (callback) {
        callback({
          type: 'agency_update',
          agent_id: 'nexus',
          agency_score: 0.88,
          autonomy_score: 0.72,
          timestamp: '2025-01-01T00:00:01Z',
        });
      }
    });

    act(() => {
      vi.advanceTimersByTime(150);
    });

    await waitFor(() => {
      const state = result.current.agentStates.get('nexus');
      // Both phi and agency fields should be present
      expect(state).toMatchObject({
        phi_score: 0.95,
        agency_score: 0.88,
        autonomy_score: 0.72,
      });
    });
  });
});
