import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ToastProvider } from '../../src/components/UI/Toast';

vi.mock('../../src/api/agents', () => ({
  getAgents: vi.fn(),
  getAgentInstances: vi.fn(),
  getAvailableAgentTypes: vi.fn(),
  startAgent: vi.fn(),
  stopAgent: vi.fn(),
  suspendAgent: vi.fn(),
  resumeAgent: vi.fn(),
  removeAgent: vi.fn(),
  deployAgent: vi.fn(),
  updateAgentConfig: vi.fn(),
  getRegistryStats: vi.fn(),
}));

import { AgentsPage } from '../../src/components/Agents/AgentsPage';
import { getAgents, getAgentInstances, getAvailableAgentTypes } from '../../src/api/agents';

function renderWithProviders(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

describe('AgentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    (getAgents as any).mockReturnValue(new Promise(() => {})); // never resolves
    (getAgentInstances as any).mockReturnValue(new Promise(() => {}));
    (getAvailableAgentTypes as any).mockReturnValue(new Promise(() => {}));
    renderWithProviders(<AgentsPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders agents header when data loads', async () => {
    (getAgents as any).mockResolvedValue({ agents: [], total: 0 });
    (getAgentInstances as any).mockResolvedValue({ instances: [], total: 0 });
    (getAvailableAgentTypes as any).mockResolvedValue({ available_agents: [], total: 0 });
    renderWithProviders(<AgentsPage />);
    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument();
    });
  });

  it('renders error toast on failure', async () => {
    (getAgents as any).mockRejectedValue(new Error('Network error'));
    (getAgentInstances as any).mockResolvedValue({ instances: [], total: 0 });
    (getAvailableAgentTypes as any).mockResolvedValue({ available_agents: [], total: 0 });
    renderWithProviders(<AgentsPage />);
    await waitFor(() => {
      expect(screen.getByText('Failed to fetch agents')).toBeInTheDocument();
    });
    // Verify the error message is shown in the toast
    expect(screen.getByText('Network error')).toBeInTheDocument();
    // Verify the toast has the alert role
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
