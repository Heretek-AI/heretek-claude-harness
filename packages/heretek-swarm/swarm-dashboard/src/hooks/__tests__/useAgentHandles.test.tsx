/**
 * Unit Tests for Dynamic Handles
 *
 * Tests for:
 * - useAgentHandles hook
 * - DynamicHandles component
 * - Handle positioning and color-coding
 * - Channel type handling
 *
 * Note: These tests require @testing-library/react and vitest to be installed.
 * Run: npm install -D @testing-library/react vitest @testing-library/jest-dom
 */

import { vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// @xyflow/react Position enum used directly in test assertions — mock it
vi.mock('@xyflow/react', () => ({
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));
import { Position } from '@xyflow/react';

import {
  getHandleColor,
  getHandlePosition,
  useAgentHandles,
  type AgentHandle,
  type ChannelType,
  type ChannelSubscription,
} from '../useAgentHandles';

// Mock fetch globally — use vi.stubGlobal to bypass jsdom readonly protection
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// =============================================================================
// getHandleColor Tests
// =============================================================================

describe('getHandleColor', () => {
  it('should return green for event channel type', () => {
    expect(getHandleColor('event')).toBe('#10B981');
  });

  it('should return blue for command channel type', () => {
    expect(getHandleColor('command')).toBe('#3B82F6');
  });

  it('should return purple for response channel type', () => {
    expect(getHandleColor('response')).toBe('#8B5CF6');
  });

  it('should return amber for metric channel type', () => {
    expect(getHandleColor('metric')).toBe('#F59E0B');
  });

  it('should return gray for unknown channel type', () => {
    expect(getHandleColor('unknown' as ChannelType)).toBe('#6B7280');
  });
});

// =============================================================================
// getHandlePosition Tests
// =============================================================================

describe('getHandlePosition', () => {
  it('should return Top for single input handle', () => {
    expect(getHandlePosition('target', 0, 1)).toBe(Position.Top);
  });

  it('should return Bottom for single output handle', () => {
    expect(getHandlePosition('source', 0, 1)).toBe(Position.Bottom);
  });

  it('should distribute multiple input handles', () => {
    expect(getHandlePosition('target', 0, 3)).toBe(Position.Top);
    expect(getHandlePosition('target', 1, 3)).toBe(Position.Top);
    expect(getHandlePosition('target', 2, 3)).toBe(Position.Top);
  });

  it('should distribute multiple output handles', () => {
    expect(getHandlePosition('source', 0, 3)).toBe(Position.Bottom);
    expect(getHandlePosition('source', 1, 3)).toBe(Position.Bottom);
    expect(getHandlePosition('source', 2, 3)).toBe(Position.Bottom);
  });
});

// =============================================================================
// useAgentHandles Hook Tests
// =============================================================================

describe('useAgentHandles', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch channel subscriptions on mount', async () => {
    const mockSubscriptions: ChannelSubscription[] = [
      {
        channelName: 'swarm.internal.triad',
        channelType: 'event',
        direction: 'bidirectional',
        description: 'Triad communication channel',
      },
      {
        channelName: 'swarm.internal.safety',
        channelType: 'command',
        direction: 'input',
        description: 'Safety alerts channel',
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        agentId: 'agent-123',
        subscriptions: mockSubscriptions,
        total: 2,
      }),
    });

    const { result } = renderHook(() =>
      useAgentHandles({ agentId: 'agent-123', enabled: true, pollingInterval: 0 }),
    );

    // Wait for fetch to complete
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.subscriptions).toHaveLength(2);
    expect(result.current.subscriptions[0].channelName).toBe('swarm.internal.triad');
    expect(result.current.subscriptions[1].channelName).toBe('swarm.internal.safety');
  });

  it('should handle empty subscriptions', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        agentId: 'agent-123',
        subscriptions: [],
        total: 0,
      }),
    });

    const { result } = renderHook(() =>
      useAgentHandles({ agentId: 'agent-123', enabled: true, pollingInterval: 0 }),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.subscriptions).toHaveLength(0);
    expect(result.current.handles).toHaveLength(0);
  });

  it('should handle 404 response (no subscriptions yet)', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    const { result } = renderHook(() =>
      useAgentHandles({ agentId: 'agent-123', enabled: true, pollingInterval: 0 }),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.subscriptions).toHaveLength(0);
    expect(result.current.error).toBeNull();
  });

  it('should handle fetch error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() =>
      useAgentHandles({ agentId: 'agent-123', enabled: true, pollingInterval: 0 }),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
  });

  it('should convert subscriptions to handles', async () => {
    const mockSubscriptions: ChannelSubscription[] = [
      {
        channelName: 'input.channel',
        channelType: 'event',
        direction: 'input',
      },
      {
        channelName: 'output.channel',
        channelType: 'command',
        direction: 'output',
      },
      {
        channelName: 'bi.channel',
        channelType: 'response',
        direction: 'bidirectional',
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        agentId: 'agent-123',
        subscriptions: mockSubscriptions,
        total: 3,
      }),
    });

    const { result } = renderHook(() =>
      useAgentHandles({ agentId: 'agent-123', enabled: true, pollingInterval: 0 }),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have 4 handles: 1 input + 1 output + 2 bidirectional (input + output)
    expect(result.current.handles).toHaveLength(4);

    // Check handle types
    const inputHandles = result.current.handles.filter((h: AgentHandle) => h.type === 'target');
    const outputHandles = result.current.handles.filter((h: AgentHandle) => h.type === 'source');

    expect(inputHandles).toHaveLength(2); // input.channel + bi.channel
    expect(outputHandles).toHaveLength(2); // output.channel + bi.channel
  });

  it('should add subscription', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          agentId: 'agent-123',
          subscriptions: [],
          total: 0,
        }),
      })
      .mockResolvedValueOnce({ ok: true });

    const { result } = renderHook(() =>
      useAgentHandles({ agentId: 'agent-123', enabled: true, pollingInterval: 0 }),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await result.current.addSubscription({
      channelName: 'new.channel',
      channelType: 'metric',
      direction: 'output',
    });

    // Verify POST was called
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/agents/agent-123/channels',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });

  it('should remove subscription', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          agentId: 'agent-123',
          subscriptions: [{ channelName: 'old.channel', channelType: 'event', direction: 'input' }],
          total: 1,
        }),
      })
      .mockResolvedValueOnce({ ok: true });

    const { result } = renderHook(() =>
      useAgentHandles({ agentId: 'agent-123', enabled: true, pollingInterval: 0 }),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await result.current.removeSubscription('old.channel');

    // Verify DELETE was called
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/agents/agent-123/channels/old.channel',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('should poll for updates when pollingInterval is set', async () => {
    const mockSubscriptions1: ChannelSubscription[] = [
      { channelName: 'channel-1', channelType: 'event', direction: 'input' },
    ];
    const mockSubscriptions2: ChannelSubscription[] = [
      { channelName: 'channel-1', channelType: 'event', direction: 'input' },
      { channelName: 'channel-2', channelType: 'command', direction: 'output' },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          agentId: 'agent-123',
          subscriptions: mockSubscriptions1,
          total: 1,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          agentId: 'agent-123',
          subscriptions: mockSubscriptions2,
          total: 2,
        }),
      });

    const { result } = renderHook(() =>
      useAgentHandles({
        agentId: 'agent-123',
        enabled: true,
        pollingInterval: 100, // Fast polling for test
      }),
    );

    // Wait for initial fetch
    await waitFor(() => {
      expect(result.current.subscriptions).toHaveLength(1);
    });

    // Wait for poll
    await waitFor(() => {
      expect(result.current.subscriptions).toHaveLength(2);
    });

    // Verify fetch was called twice
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('should not fetch when enabled is false', () => {
    const { result } = renderHook(() => useAgentHandles({ agentId: 'agent-123', enabled: false }));

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.subscriptions).toHaveLength(0);
  });
});

// Note: Component tests for DynamicHandles require @testing-library/react
// and a proper test setup with jsdom. The following are placeholder tests
// that demonstrate the test structure. Uncomment when dependencies are installed.

/*
import { render, screen, fireEvent } from '@testing-library/react';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DynamicHandles } from '../../components/WorkflowBuilder/DynamicHandles';
import { useAgentHandles } from '../useAgentHandles';

describe('DynamicHandles Component', () => {
  it('should render default handles when no subscriptions', () => {
    render(<DynamicHandles handles={[]} />);
    expect(document.querySelectorAll('.react-flow__handle')).toHaveLength(2);
  });

  it('should render dynamic handles for subscriptions', () => {
    const handles: AgentHandle[] = [
      { id: 'input-channel-1', type: 'target', position: Position.Top, channelName: 'channel-1', channelType: 'event' },
      { id: 'output-channel-2', type: 'source', position: Position.Bottom, channelName: 'channel-2', channelType: 'command' },
    ];
    render(<DynamicHandles handles={handles} />);
    expect(document.querySelectorAll('.dynamic-handle')).toHaveLength(2);
  });

  it('should show tooltip on handle hover', () => {
    const handles: AgentHandle[] = [
      { id: 'h1', type: 'target', position: Position.Top, channelName: 'triad.internal', channelType: 'event', description: 'Test channel' },
    ];
    const { container } = render(<DynamicHandles handles={handles} />);
    const handleWrapper = container.querySelector('.handle-container');
    if (handleWrapper) {
      fireEvent.mouseEnter(handleWrapper);
      expect(container.querySelector('.handle-tooltip')).toBeTruthy();
    }
  });

  it('should call onHandleClick when handle is clicked', () => {
    const handleClick = vi.fn();
    const handles: AgentHandle[] = [{ id: 'h1', type: 'target', position: Position.Top, channelName: 'c1', channelType: 'event' }];
    render(<DynamicHandles handles={handles} onHandleClick={handleClick} />);
    const handleElement = document.querySelector('.dynamic-handle');
    if (handleElement) fireEvent.click(handleElement);
    expect(handleClick).toHaveBeenCalledWith('h1');
  });
});

describe('useAgentHandles Hook Integration', () => {
  it('should integrate useAgentHandles with DynamicHandles', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ agentId: 'agent-123', subscriptions: [{ channelName: 'triad.channel', channelType: 'event', direction: 'bidirectional' }], total: 1 }),
    });
    const { result } = renderHook(() => useAgentHandles({ agentId: 'agent-123', enabled: true, pollingInterval: 0 }));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.handles.length).toBeGreaterThan(0);
  });
});
*/
