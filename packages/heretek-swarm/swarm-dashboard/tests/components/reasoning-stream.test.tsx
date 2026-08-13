import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReasoningStream } from '../../src/components/deliberations/reasoning-stream';
import { useDeliberationStore } from '../../src/stores/deliberation-store';

describe('ReasoningStream', () => {
  it('shows three agent panels', () => {
    useDeliberationStore.setState({
      reasoningByAgent: { alpha: 'alpha thinking', beta: 'beta thinking', charlie: '' },
      activeAgent: 'alpha',
    });
    render(<ReasoningStream />);
    expect(screen.getByText(/ALPHA/)).toBeDefined();
    expect(screen.getByText(/BETA/)).toBeDefined();
    expect(screen.getByText(/CHARLIE/)).toBeDefined();
    expect(screen.getByText('alpha thinking')).toBeDefined();
  });

  it('marks active agent as LIVE', () => {
    useDeliberationStore.setState({
      reasoningByAgent: { alpha: '', beta: '', charlie: '' },
      activeAgent: 'beta',
    });
    render(<ReasoningStream />);
    expect(screen.getByText(/LIVE/i)).toBeDefined();
  });
});
