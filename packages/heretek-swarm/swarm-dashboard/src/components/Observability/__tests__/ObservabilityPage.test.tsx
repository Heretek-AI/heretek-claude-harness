/**
 * Tests for the ObservabilityPage component.
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mock the child components
vi.mock('../A2ATracker', () => ({
  A2ATracker: () => <div data-testid="a2a-tracker">A2A Tracker Mock</div>,
}));

vi.mock('../ExternalCallsPanel', () => ({
  ExternalCallsPanel: () => <div data-testid="external-calls-panel">External Calls Mock</div>,
}));

import { ObservabilityPage } from '../ObservabilityPage';

describe('ObservabilityPage', () => {
  it('renders the page title', () => {
    render(<ObservabilityPage />);
    expect(screen.getByText('Observability')).toBeDefined();
  });

  it('renders the subtitle', () => {
    render(<ObservabilityPage />);
    expect(
      screen.getByText('Agent-to-agent message flow and external service calls'),
    ).toBeDefined();
  });

  it('renders the A2A Tracker component', () => {
    render(<ObservabilityPage />);
    expect(screen.getByTestId('a2a-tracker')).toBeDefined();
  });

  it('renders the External Calls Panel component', () => {
    render(<ObservabilityPage />);
    expect(screen.getByTestId('external-calls-panel')).toBeDefined();
  });
});
