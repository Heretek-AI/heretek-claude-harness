import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createDeliberation } from '../api/deliberations';

export function HomePage() {
  const [problem, setProblem] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!problem.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const id = await createDeliberation(problem.trim());
      navigate(`/deliberations/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create deliberation');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 700, margin: '0 auto' }}>
      <h1>New Deliberation</h1>
      <form onSubmit={onSubmit}>
        <label style={{ display: 'block', marginBottom: 8 }}>Problem</label>
        <textarea
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          maxLength={5000}
          rows={6}
          required
          style={{ width: '100%', padding: 8, fontFamily: 'monospace' }}
        />
        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>{problem.length} / 5000</div>
        <button
          type="submit"
          disabled={submitting || !problem.trim()}
          style={{
            marginTop: 12,
            padding: '8px 18px',
            background: '#fbbf24',
            color: '#0f172a',
            border: 0,
            borderRadius: 4,
            fontWeight: 700,
          }}
        >
          {submitting ? 'Starting…' : 'Start deliberation'}
        </button>
        {error && <div style={{ color: '#dc2626', marginTop: 12 }}>{error}</div>}
      </form>
    </div>
  );
}
