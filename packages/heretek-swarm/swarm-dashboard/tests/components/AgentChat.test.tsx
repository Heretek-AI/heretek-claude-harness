import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('@ai-sdk/react', () => ({
  useChat: vi.fn(() => ({
    messages: [],
    sendMessage: vi.fn(),
    status: 'ready',
    error: null,
    stop: vi.fn(),
  })),
}));

vi.mock('ai', () => ({
  TextStreamChatTransport: vi.fn(),
}));

import { AgentChat } from '../../src/components/Chat/AgentChat';

describe('AgentChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders chat interface with input', () => {
    render(<AgentChat />);
    expect(screen.getByPlaceholderText(/ask the swarm/i)).toBeInTheDocument();
  });

  it('renders send button', () => {
    render(<AgentChat />);
    expect(screen.getByText('Send')).toBeInTheDocument();
  });

  it('renders empty state message', () => {
    render(<AgentChat />);
    expect(screen.getByText(/send a message to start a chat/i)).toBeInTheDocument();
  });
});
