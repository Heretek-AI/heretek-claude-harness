import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { InterjectInput } from '../../src/components/deliberations/interject-input';
import { useDeliberationStore } from '../../src/stores/deliberation-store';

vi.mock('../../src/api/deliberations', () => ({
  interject: vi.fn().mockResolvedValue(undefined),
}));

function renderWithRoute(id: string, status: 'running' | 'completed' | 'failed') {
  useDeliberationStore.setState({ status });
  return render(
    <MemoryRouter initialEntries={[`/d/${id}`]}>
      <Routes>
        <Route path="/d/:id" element={<InterjectInput />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('InterjectInput', () => {
  it('renders when status is running', () => {
    renderWithRoute('abc', 'running');
    expect(screen.getByText(/Interject \(next round/i)).toBeDefined();
  });

  it('does not render when status is completed', () => {
    renderWithRoute('abc', 'completed');
    expect(screen.queryByText(/Interject \(next round/i)).toBeNull();
  });
});
