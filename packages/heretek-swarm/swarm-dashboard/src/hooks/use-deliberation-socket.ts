// WebSocket hook. Connects, applies replay, then live-applies events.

import { useEffect, useRef } from 'react';
import { useDeliberationStore } from '../stores/deliberation-store';
import { getDeliberation } from '../api/deliberations';
import type { DeliberationEvent } from '../types/deliberation';

export function useDeliberationSocket(id: string | null): void {
  const applyEvent = useDeliberationStore((s) => s.applyEvent);
  const setReplayDone = useDeliberationStore((s) => s.setReplayDone);
  const setError = useDeliberationStore((s) => s.setError);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!id) return;

    // Hydrate from REST first.
    getDeliberation(id)
      .then((detail) => useDeliberationStore.getState().hydrate(detail))
      .catch((err) => setError(`Failed to load deliberation: ${err.message}`));

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}/ws/deliberations/${id}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        if (data.kind === 'event') {
          applyEvent(data.event as DeliberationEvent);
        } else if (data.kind === 'replay_done') {
          setReplayDone(data.count);
        } else if (data.kind === 'error') {
          setError(data.message ?? 'WebSocket error');
        }
      } catch (err) {
        console.error('ws parse error', err);
      }
    };

    ws.onerror = () => setError('WebSocket connection error');

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [id, applyEvent, setReplayDone, setError]);
}
