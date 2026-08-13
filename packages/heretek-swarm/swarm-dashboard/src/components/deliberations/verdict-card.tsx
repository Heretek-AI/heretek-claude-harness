// VerdictCard — final verdict banner.

import { useDeliberationStore } from '../../stores/deliberation-store';

const COLORS: Record<string, string> = {
  approved: '#16a34a',
  rejected: '#dc2626',
  'needs-revision': '#f59e0b',
  'no-consensus': '#6b7280',
};

export function VerdictCard() {
  const finalVerdict = useDeliberationStore((s) => s.finalVerdict);
  const status = useDeliberationStore((s) => s.status);

  if (status !== 'completed' || !finalVerdict) return null;

  return (
    <div
      style={{
        background: COLORS[finalVerdict.decision] ?? '#6b7280',
        color: '#fff',
        padding: 16,
        borderRadius: 8,
        marginBottom: 16,
      }}
    >
      <div style={{ fontSize: 12, opacity: 0.8 }}>FINAL VERDICT</div>
      <div style={{ fontSize: 24, fontWeight: 800, marginTop: 4 }}>
        {finalVerdict.decision.toUpperCase()}
      </div>
      <div style={{ marginTop: 8, fontFamily: 'monospace', fontSize: 13, whiteSpace: 'pre-wrap' }}>
        {finalVerdict.summary}
      </div>
      <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>Rounds: {finalVerdict.rounds}</div>
    </div>
  );
}
