// ReasoningStream — per-agent live token stream.

import { useDeliberationStore } from '../../stores/deliberation-store';

function Panel({ agent, label }: { agent: 'alpha' | 'beta' | 'charlie'; label: string }) {
  const reasoning = useDeliberationStore((s) => s.reasoningByAgent[agent] ?? '');
  const activeAgent = useDeliberationStore((s) => s.activeAgent);
  const isActive = activeAgent === agent;

  return (
    <div
      style={{
        border: '1px solid #475569',
        borderRadius: 8,
        padding: 12,
        marginBottom: 8,
        background: isActive ? '#1e293b' : '#0f172a',
      }}
    >
      <div style={{ fontWeight: 700, color: '#fbbf24', marginBottom: 6 }}>
        {label} {isActive && '● LIVE'}
      </div>
      <pre
        style={{
          whiteSpace: 'pre-wrap',
          fontFamily: 'monospace',
          margin: 0,
          color: '#e2e8f0',
          fontSize: 13,
        }}
      >
        {reasoning || <em style={{ opacity: 0.5 }}>(waiting…)</em>}
      </pre>
    </div>
  );
}

export function ReasoningStream() {
  return (
    <div>
      <Panel agent="alpha" label="ALPHA — Analysis" />
      <Panel agent="beta" label="BETA — Validation" />
      <Panel agent="charlie" label="CHARLIE — Challenge" />
    </div>
  );
}
