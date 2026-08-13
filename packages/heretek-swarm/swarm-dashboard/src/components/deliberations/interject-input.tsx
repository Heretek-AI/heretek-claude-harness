// InterjectInput — user can submit a mid-deliberation feedback.

import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { interject } from '../../api/deliberations';
import { useDeliberationStore } from '../../stores/deliberation-store';

export function InterjectInput() {
  const { id } = useParams<{ id: string }>();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const status = useDeliberationStore((s) => s.status);

  if (status !== 'running') return null;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!id || !text.trim() || submitting) return;
    setSubmitting(true);
    try {
      await interject(id, text.trim());
      setText('');
    } catch (err) {
      console.error('interject failed', err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ marginTop: 12 }}>
      <label style={{ display: 'block', marginBottom: 4, color: '#cbd5e1' }}>
        Interject (next round's agents will see this)
      </label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={2000}
        rows={3}
        style={{ width: '100%', padding: 8, borderRadius: 4, fontFamily: 'monospace' }}
      />
      <button
        type="submit"
        disabled={submitting || !text.trim()}
        style={{
          marginTop: 8,
          padding: '6px 14px',
          background: '#fbbf24',
          color: '#0f172a',
          border: 0,
          borderRadius: 4,
          fontWeight: 700,
          cursor: submitting ? 'wait' : 'pointer',
        }}
      >
        {submitting ? 'Sending…' : 'Send interjection'}
      </button>
    </form>
  );
}
