// AgentGraph — xyflow diagram: Steward at center, Alpha/Beta/Charlie around it.
// Active node pulses.

import { useMemo } from 'react';
import { ReactFlow, Background, Controls, Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useDeliberationStore } from '../../stores/deliberation-store';

const POSITIONS: Record<string, { x: number; y: number }> = {
  steward: { x: 250, y: 50 },
  alpha: { x: 50, y: 200 },
  beta: { x: 250, y: 250 },
  charlie: { x: 450, y: 200 },
};

function verdictLabel(position: string | undefined): string {
  switch (position) {
    case 'approve':
      return '✓ approve';
    case 'reject':
      return '✗ reject';
    case 'challenge':
      return '! challenge';
    case 'abstain':
      return '— abstain';
    default:
      return '—';
  }
}

export function AgentGraph() {
  const activeAgent = useDeliberationStore((s) => s.activeAgent);
  const events = useDeliberationStore((s) => s.events);

  const verdictByAgent = useMemo(() => {
    const m: Record<string, string | undefined> = {};
    for (const e of events) {
      if (e.kind === 'alpha_verdict') m.alpha = e.payload.position as string;
      if (e.kind === 'beta_verdict') m.beta = e.payload.position as string;
      if (e.kind === 'charlie_verdict') m.charlie = e.payload.position as string;
    }
    return m;
  }, [events]);

  const nodes: Node[] = useMemo(
    () =>
      ['steward', 'alpha', 'beta', 'charlie'].map((name) => ({
        id: name,
        position: POSITIONS[name]!,
        data: {
          label:
            name === 'steward'
              ? 'STEWARD'
              : `${name.toUpperCase()} — ${verdictLabel(verdictByAgent[name])}`,
        },
        style: {
          background:
            name === 'steward'
              ? '#1e293b'
              : name === activeAgent
                ? '#fbbf24'
                : verdictByAgent[name]
                  ? '#16a34a'
                  : '#94a3b8',
          color: name === 'steward' || name === activeAgent ? '#fff' : '#000',
          padding: 10,
          borderRadius: 8,
          fontFamily: 'monospace',
          fontWeight: 600,
          minWidth: 140,
          textAlign: 'center',
        },
      })),
    [activeAgent, verdictByAgent],
  );

  const edges: Edge[] = useMemo(
    () => [
      { id: 's-a', source: 'steward', target: 'alpha', label: 'dispatch' },
      { id: 'a-b', source: 'alpha', target: 'beta', label: 'verdict' },
      { id: 'b-c', source: 'beta', target: 'charlie', label: 'verdict' },
      { id: 'c-s', source: 'charlie', target: 'steward', label: 'verdict' },
    ],
    [],
  );

  return (
    <div style={{ height: 360, width: '100%' }}>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
