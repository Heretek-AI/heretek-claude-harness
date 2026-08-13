import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ToastProvider } from '../../src/components/UI/Toast';

vi.mock('../../src/components/Settings/DeveloperModeToggle', () => ({
  DeveloperModeToggle: () => <div data-testid="dev-mode-toggle">Developer Mode</div>,
}));

vi.mock('../../src/components/Settings/SystemConfigSection', () => ({
  SystemConfigSection: () => <div>System Config</div>,
}));

vi.mock('../../src/components/Settings/ModelGarage', () => ({
  ModelGarage: () => <div>Model Garage</div>,
}));

vi.mock('../../src/components/Settings/AgentDefaultsSection', () => ({
  AgentDefaultsSection: () => <div>Agent Defaults</div>,
}));

vi.mock('../../src/components/Settings/MCPToolsSection', () => ({
  MCPToolsSection: () => <div>MCP Tools</div>,
}));

vi.mock('../../src/components/Settings/ImportExportSection', () => ({
  ImportExportSection: () => <div>Import Export</div>,
}));

import { SettingsPage } from '../../src/components/Settings/SettingsPage';

function renderWithProviders(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

describe('SettingsPage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders settings page heading', () => {
    renderWithProviders(<SettingsPage onRerunSetup={() => {}} />);
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders connection settings section', () => {
    renderWithProviders(<SettingsPage onRerunSetup={() => {}} />);
    expect(screen.getByText('Connection Settings')).toBeInTheDocument();
  });

  it('saves API key to localStorage', async () => {
    renderWithProviders(<SettingsPage onRerunSetup={() => {}} />);
    const input = screen.getByPlaceholderText(/enter your api key/i);
    fireEvent.change(input, { target: { value: 'test-key-123' } });
    const saveButtons = screen.getAllByText('Save');
    fireEvent.click(saveButtons[0]); // first Save is for API Key
    await waitFor(() => {
      expect(localStorage.getItem('api_key')).toBe('test-key-123');
    });
  });

  it('renders tab navigation', () => {
    renderWithProviders(<SettingsPage onRerunSetup={() => {}} />);
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('Providers')).toBeInTheDocument();
  });

  it('renders developer mode toggle', () => {
    renderWithProviders(<SettingsPage onRerunSetup={() => {}} />);
    expect(screen.getByTestId('dev-mode-toggle')).toBeInTheDocument();
  });

  it('renders about section with version', () => {
    renderWithProviders(<SettingsPage onRerunSetup={() => {}} />);
    expect(screen.getByText('About')).toBeInTheDocument();
    expect(screen.getByText('0.2.0')).toBeInTheDocument();
  });
});
