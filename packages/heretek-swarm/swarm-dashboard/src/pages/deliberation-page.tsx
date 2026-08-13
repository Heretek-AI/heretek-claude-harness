import { useParams } from 'react-router-dom';
import { useEffect } from 'react';
import { useDeliberationStore } from '../stores/deliberation-store';
import { useDeliberationSocket } from '../hooks/use-deliberation-socket';
import { AgentGraph } from '../components/deliberations/agent-graph';
import { ReasoningStream } from '../components/deliberations/reasoning-stream';
import { InterjectInput } from '../components/deliberations/interject-input';
import { VerdictCard } from '../components/deliberations/verdict-card';

export function DeliberationPage() {
  const { id } = useParams<{ id: string }>();
  const reset = useDeliberationStore((s) => s.reset);
  const problem = useDeliberationStore((s) => s.problem);

  useEffect(() => {
    if (id) reset(id, '');
  }, [id, reset]);

  useDeliberationSocket(id ?? null);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Deliberation {id}</h1>
      <p style={{ color: '#94a3b8', fontFamily: 'monospace' }}>{problem || '(loading…)'}</p>
      <VerdictCard />
      <AgentGraph />
      <ReasoningStream />
      <InterjectInput />
    </div>
  );
}
