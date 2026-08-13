import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listDeliberations } from '../api/deliberations';
import type { DeliberationSummary } from '../types/deliberation';

export function DeliberationListPage() {
  const [items, setItems] = useState<DeliberationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDeliberations(50)
      .then(setItems)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div style={{ padding: 24, color: '#dc2626' }}>{error}</div>;

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20 }}>Deliberations</h1>
      {items.length === 0 ? (
        <p>No deliberations yet.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {items.map((it) => (
            <li
              key={it.id}
              style={{
                borderBottom: '1px solid #334155',
                padding: 12,
              }}
            >
              <Link to={`/deliberations/${it.id}`} style={{ color: '#fbbf24' }}>
                {it.id}
              </Link>
              <span style={{ marginLeft: 12, color: '#94a3b8' }}>{it.status}</span>
              <div style={{ fontFamily: 'monospace', fontSize: 13, color: '#cbd5e1' }}>
                {it.problem}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
