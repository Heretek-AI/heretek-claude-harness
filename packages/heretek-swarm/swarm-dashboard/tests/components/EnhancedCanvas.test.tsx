import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('@xyflow/react', () => {
  const React = require('react');
  return {
    ReactFlow: ({ children, ...props }: any) => (
      <div data-testid="react-flow" data-nodes={props.nodes?.length || 0}>
        {children}
      </div>
    ),
    Node: {},
    Edge: {},
    Controls: () => null,
    Background: () => null,
    MiniMap: () => null,
    useNodesState: () => [[], vi.fn(), vi.fn()],
    useEdgesState: () => [[], vi.fn(), vi.fn()],
    addEdge: vi.fn(),
    Panel: ({ children }: any) => <div>{children}</div>,
    Connection: {},
    XYPosition: {},
  };
});

vi.mock('../../src/components/Canvas/AgentNode', () => ({
  default: () => <div data-testid="agent-node" />,
}));

// Stub global fetch to avoid real network calls
beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ agents: [] }),
    }),
  );
});

import { EnhancedCanvas } from '../../src/components/Canvas/EnhancedCanvas';

describe('EnhancedCanvas', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the canvas with node palette', () => {
    render(<EnhancedCanvas />);
    expect(screen.getByText('Node Palette')).toBeInTheDocument();
  });

  it('renders toolbar buttons', () => {
    render(<EnhancedCanvas />);
    expect(screen.getByTitle('Toggle Metrics Overlay')).toBeInTheDocument();
    expect(screen.getByTitle('Toggle Node Palette')).toBeInTheDocument();
    expect(screen.getByTitle('Save Workflow')).toBeInTheDocument();
  });

  it('renders ReactFlow canvas', () => {
    render(<EnhancedCanvas />);
    expect(screen.getByTestId('react-flow')).toBeInTheDocument();
  });
});
