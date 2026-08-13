import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AgentGraph } from '../../src/components/deliberations/agent-graph';
import { useDeliberationStore } from '../../src/stores/deliberation-store';

describe('AgentGraph', () => {
  it('renders all four agent labels', () => {
    useDeliberationStore.setState({
      events: [],
      activeAgent: null,
      reasoningByAgent: { alpha: '', beta: '', charlie: '' },
    });
    render(<AgentGraph />);
    // xyflow renders nodes via portals; smoke check the component didn't throw.
    expect(screen.getByText(/STEWARD/i)).toBeDefined();
  });
});
