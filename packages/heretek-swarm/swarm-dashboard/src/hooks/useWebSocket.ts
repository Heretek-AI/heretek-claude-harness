/**
 * WebSocket Hook - Real-time communication
 */

import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: string;
  data?: unknown;
  timestamp?: string;
  agent_id?: string;
  [key: string]: unknown;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket(
  channel: string,
  options: UseWebSocketOptions = {}
) {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // F-010: store callback identities in refs so `connect`'s useCallback
  // dep array stays stable across re-renders. See tests/e2e/m030-f010-*.
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onMessageRef.current = onMessage;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
    onErrorRef.current = onError;
  });

  // Use environment variable or current hostname (nginx proxies /ws to api:8000)
  const API_URL = import.meta.env.VITE_API_HOST || `http://${window.location.host}`;
  const apiHost = (() => {
    try {
      const stored = localStorage.getItem('swarm_api_host');
      return stored || API_URL;
    } catch {
      return API_URL;
    }
  })();

  const connect = useCallback(() => {
    // Use API host for WebSocket URL (backend runs on port 8000)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Extract hostname and port from apiHost (e.g. "http://localhost:8000" -> "localhost:8000")
    const url = new URL(apiHost.startsWith('http') ? apiHost : `http://${apiHost}`);
    const apiKey = localStorage.getItem('api_key');
    const wsUrl = apiKey
      ? `${protocol}//${url.host}/ws/${channel}?token=${encodeURIComponent(apiKey)}`
      : `${protocol}//${url.host}/ws/${channel}`;

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        setConnected(true);
        reconnectAttempts.current = 0;
        onOpenRef.current?.();
      };

      wsRef.current.onclose = () => {
        setConnected(false);
        onCloseRef.current?.();

        // Attempt reconnection with function reference (safe, not string eval)
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1;
          reconnectTimeout.current = setTimeout(connect, reconnectInterval);
        }
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          onMessageRef.current?.(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        onErrorRef.current?.(error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      onErrorRef.current?.(error as Event);
    }
  }, [channel, apiHost, reconnectInterval, maxReconnectAttempts]);

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    console.warn('WebSocket not connected, message not sent');
    return false;
  }, []);

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

  // Connect on mount. The dependency array is now stable: `connect`
  // and `disconnect` only change when channel/apiHost/reconnect-
  // Interval/maxReconnectAttempts change, not on every render. This
  // is the F-010 fix: the effect runs once per mount, the WS stays
  // open across re-renders, and reconnection only happens on real
  // disconnect events.
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connected,
    lastMessage,
    sendMessage,
    disconnect,
    reconnectAttempts: reconnectAttempts.current,
  };
}

/**
 * Hook for agent events WebSocket
 */
export function useAgentEvents(onMessage?: (message: WebSocketMessage) => void) {
  return useWebSocket('agents', {
    onMessage,
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
  });
}

/**
 * Hook for metrics stream WebSocket
 */
export function useMetricsStream(onMessage?: (message: WebSocketMessage) => void) {
  return useWebSocket('metrics', {
    onMessage,
    reconnectInterval: 5000,
    maxReconnectAttempts: 10,
  });
}

/**
 * Hook for execution updates WebSocket
 */
export function useExecutionStream(
  executionId: string,
  onMessage?: (message: WebSocketMessage) => void
) {
  return useWebSocket(`executions/${executionId}`, {
    onMessage,
    reconnectInterval: 2000,
    maxReconnectAttempts: 5,
  });
}
