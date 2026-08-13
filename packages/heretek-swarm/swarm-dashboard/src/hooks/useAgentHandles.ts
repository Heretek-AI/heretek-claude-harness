/**
 * useAgentHandles - Hook for managing dynamic handles based on channel subscriptions
 *
 * Fetches agent channel subscriptions from API and creates dynamic handles
 * for input/output connections based on channel types.
 *
 * Features:
 * - Fetch channel subscriptions from /api/agents/{agentId}/channels
 * - Create input handles for subscribed input channels
 * - Create output handles for published output channels
 * - Color-code handles by channel type (event, command, response, metric)
 * - Show channel name on hover tooltip
 */

import { useState, useEffect, useCallback } from 'react';
import { Position } from '@xyflow/react';

/**
 * Channel types for handle color-coding
 */
export type ChannelType = 'event' | 'command' | 'response' | 'metric';

/**
 * Agent handle interface for dynamic handle creation
 */
export interface AgentHandle {
  id: string;
  type: 'source' | 'target';
  position: Position;
  channelName: string;
  channelType: ChannelType;
  dataType?: string;
  description?: string;
}

/**
 * Channel subscription interface
 */
export interface ChannelSubscription {
  channelName: string;
  channelType: ChannelType;
  direction: 'input' | 'output' | 'bidirectional';
  dataType?: string;
  description?: string;
  subscribedAt?: string;
}

/**
 * API response for channel subscriptions
 */
interface ChannelSubscriptionsResponse {
  agentId: string;
  subscriptions: ChannelSubscription[];
  total: number;
}

/**
 * Hook options for useAgentHandles
 */
interface UseAgentHandlesOptions {
  agentId: string;
  enabled?: boolean;
  pollingInterval?: number;
  apiUrl?: string;
}

/**
 * Hook result for useAgentHandles
 */
interface UseAgentHandlesResult {
  handles: AgentHandle[];
  subscriptions: ChannelSubscription[];
  isLoading: boolean;
  error: Error | null;
  addSubscription: (subscription: Omit<ChannelSubscription, 'subscribedAt'>) => Promise<void>;
  removeSubscription: (channelName: string) => Promise<void>;
  refresh: () => Promise<void>;
}

/**
 * Map channel type to handle color
 */
export function getHandleColor(channelType: ChannelType): string {
  const colors: Record<ChannelType, string> = {
    event: '#10B981', // Green
    command: '#3B82F6', // Blue
    response: '#8B5CF6', // Purple
    metric: '#F59E0B', // Amber
  };
  return colors[channelType] || '#6B7280';
}

/**
 * Map channel type to handle position offset
 */
export function getHandlePosition(
  type: 'source' | 'target',
  index: number,
  total: number,
): Position {
  if (type === 'target') {
    // Input handles on top, distributed horizontally
    if (total === 1) return Position.Top;
    const offset = (index / (total - 1)) * 100;
    return Position.Top;
  } else {
    // Output handles on bottom, distributed horizontally
    if (total === 1) return Position.Bottom;
    return Position.Bottom;
  }
}

/**
 * Hook for managing dynamic agent handles
 */
export function useAgentHandles({
  agentId,
  enabled = true,
  pollingInterval = 30000, // 30 seconds
  apiUrl = '',
}: UseAgentHandlesOptions): UseAgentHandlesResult {
  const [handles, setHandles] = useState<AgentHandle[]>([]);
  const [subscriptions, setSubscriptions] = useState<ChannelSubscription[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  /**
   * Fetch channel subscriptions from API
   */
  const fetchSubscriptions = useCallback(async () => {
    if (!agentId || !enabled) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/api/agents/${agentId}/channels`);

      if (!response.ok) {
        if (response.status === 404) {
          // Agent has no subscriptions yet, use defaults
          setSubscriptions([]);
          setHandles([]);
          return;
        }
        throw new Error(`Failed to fetch subscriptions: ${response.statusText}`);
      }

      const data: ChannelSubscriptionsResponse = await response.json();
      setSubscriptions(data.subscriptions || []);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      setError(error);
      console.error('Failed to fetch channel subscriptions:', error);
    } finally {
      setIsLoading(false);
    }
  }, [agentId, enabled, apiUrl]);

  /**
   * Add a new channel subscription
   */
  const addSubscription = useCallback(
    async (subscription: Omit<ChannelSubscription, 'subscribedAt'>) => {
      if (!agentId) return;

      try {
        const response = await fetch(`${apiUrl}/api/agents/${agentId}/channels`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(subscription),
        });

        if (!response.ok) {
          throw new Error(`Failed to add subscription: ${response.statusText}`);
        }

        await fetchSubscriptions();
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Unknown error');
        setError(error);
        throw error;
      }
    },
    [agentId, apiUrl, fetchSubscriptions],
  );

  /**
   * Remove a channel subscription
   */
  const removeSubscription = useCallback(
    async (channelName: string) => {
      if (!agentId) return;

      try {
        const response = await fetch(
          `${apiUrl}/api/agents/${agentId}/channels/${encodeURIComponent(channelName)}`,
          { method: 'DELETE' },
        );

        if (!response.ok) {
          throw new Error(`Failed to remove subscription: ${response.statusText}`);
        }

        await fetchSubscriptions();
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Unknown error');
        setError(error);
        throw error;
      }
    },
    [agentId, apiUrl, fetchSubscriptions],
  );

  /**
   * Convert subscriptions to handles
   */
  useEffect(() => {
    const newHandles: AgentHandle[] = [];

    subscriptions.forEach((sub, index) => {
      const isInput = sub.direction === 'input' || sub.direction === 'bidirectional';
      const isOutput = sub.direction === 'output' || sub.direction === 'bidirectional';

      // Calculate position based on total count
      const totalInputs = subscriptions.filter(
        (s) => s.direction === 'input' || s.direction === 'bidirectional',
      ).length;
      const totalOutputs = subscriptions.filter(
        (s) => s.direction === 'output' || s.direction === 'bidirectional',
      ).length;

      if (isInput) {
        const inputIndex =
          subscriptions.filter(
            (s, i) => (s.direction === 'input' || s.direction === 'bidirectional') && i <= index,
          ).length - 1;

        newHandles.push({
          id: `input-${sub.channelName}`,
          type: 'target',
          position: Position.Top,
          channelName: sub.channelName,
          channelType: sub.channelType,
          dataType: sub.dataType,
          description: sub.description,
        });
      }

      if (isOutput) {
        newHandles.push({
          id: `output-${sub.channelName}`,
          type: 'source',
          position: Position.Bottom,
          channelName: sub.channelName,
          channelType: sub.channelType,
          dataType: sub.dataType,
          description: sub.description,
        });
      }
    });

    setHandles(newHandles);
  }, [subscriptions]);

  /**
   * Initial fetch and polling
   */
  useEffect(() => {
    if (!enabled) return;

    fetchSubscriptions();

    if (pollingInterval > 0) {
      const interval = setInterval(fetchSubscriptions, pollingInterval);
      return () => clearInterval(interval);
    }
  }, [enabled, pollingInterval, fetchSubscriptions]);

  return {
    handles,
    subscriptions,
    isLoading,
    error,
    addSubscription,
    removeSubscription,
    refresh: fetchSubscriptions,
  };
}

export default useAgentHandles;
