# partysocket spike — Phase 2B.5

## Purpose

Validate that **partysocket** (https://github.com/partykit/partysocket,
MIT, ~700 stars) is the integration target for the 5 hand-rolled
WebSocket hooks. partysocket is the maintained fork of the
`reconnecting-websocket` pattern with first-class partykit support
and modern reconnect/heartbeat primitives.

## Candidate files for cutover (~1,000 LOC combined)

| File | LOC | Replaced by |
|------|-----|-------------|
| `hooks/useWebSocket.ts` | 195 | `useWebSocket` from `partysocket/react` |
| `hooks/useConsensusWebSocket.ts` | 589 | `useWebSocket` + channel pattern |
| `hooks/useConsciousnessWebSocket.ts` | 215 | `useWebSocket` |
| `hooks/useA2AMessages.ts` | 189 | `useWebSocket` + message buffer hook |
| `hooks/useWorkflowProgress.ts` (WS portion) | 291 | `useWebSocket` |
| **Total** | **~1,479** | **net ~1,000 after adding partysocket** |

## Why this matters

The 5 hooks each re-implement the same WebSocket reconnect/heartbeat/
buffer plumbing. The plan's earlier finding (PRIME_DIRECTIVE F-010,
fixed 2026-06-03) was that the inline-callback instability caused
the WS to reconnect every render; a shared library prevents that
class of bug.

partysocket's `useWebSocket` hook provides:
- Automatic reconnect with backoff.
- Heartbeat / ping-pong.
- Stable callback refs (uses refs internally to avoid the F-010 bug).
- Party-mode multiplexing (one socket, many channels).

## Migration pattern

### Step 1: Install deps
```bash
cd swarm-dashboard
npm install partysocket
```

### Step 2: Replace each `useWebSocket` hook
Old pattern (per-hook reimplementation):
```tsx
function useConsensusWebSocket(onMessage: (m: any) => void) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  // ... 100+ lines of reconnect/heartbeat/buffer
  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onmessage = (e) => onMessage(JSON.parse(e.data));
    ws.onclose = () => { /* reconnect */ };
    // ... 50 more lines
    return () => ws.close();
  }, [url]);
  return { connected };
}
```

New pattern (partysocket):
```tsx
import { useWebSocket } from 'partysocket/react';

function useConsensusWebSocket(onMessage: (m: any) => void) {
  const ws = useWebSocket({
    url: '/ws/consensus',
    onMessage: (e) => onMessage(JSON.parse(e.data)),
  });
  return { connected: ws.readyState === ReadyState.OPEN };
}
```

### Step 3: Delete the 5 hook files

## Kill criteria

- If partysocket's reconnect strategy conflicts with the
  nginx-rewritten `/ws/` path (PRIME_DIRECTIVE F-002 fix), use
  the `partysocket.WSConnection` directly without the React hook.

## Result

- ~1,000 LOC reduction.
- Reconnect/heartbeat/buffer logic maintained by partysocket
  (no need to write it again).
- The F-010 inline-callback bug is structurally impossible with
  the library hooks.

## Migration PR plan

1. Add `partysocket` dep.
2. Migrate `useWebSocket.ts` (the base) to partysocket.
3. Migrate the 4 channel-specific hooks.
4. Delete the 5 old hook files.
5. Verify the 4 WS endpoints (`/api/ws/dashboard`, `/api/ws/agents`,
   `/api/ws/logs`, `/api/ws/consciousness`) all still connect via
   the partysocket library.

**Net:** ~1,000 LOC reduction + bug-class prevention.
