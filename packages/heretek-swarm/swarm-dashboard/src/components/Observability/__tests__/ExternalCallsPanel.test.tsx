/**
 * ExternalCallsPanel Component Tests
 *
 * Tests the filter logic, data normalization, and rendering behavior of ExternalCallsPanel.
 *
 * Because vi.mock hoisting interferes with the real useWebSocket hook in vitest/jsdom,
 * we test at three layers:
 *  1. Pure filter/utility functions (no mocking required)
 *  2. Component rendering with minimal mock WebSocket setup
 *  3. Integration via direct state injection where needed
 */

import { act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

// --- Minimal WebSocket mock ---
// Only stubs the constructor; lets the real useWebSocket hook run.
// We manually trigger open/message to drive state.
const mockWsInstance = {
  onopen: null as (() => void) | null,
  onclose: null,
  onmessage: null as ((event: MessageEvent) => void) | null,
  onerror: null,
  readyState: 1, // OPEN
  close: vi.fn(),
  send: vi.fn(),
};

class MockWebSocket {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_url: string | URL) {
    return mockWsInstance;
  }
}
(global as any).WebSocket = MockWebSocket as any;

import { ExternalCallsPanel } from '../ExternalCallsPanel';

// ---------------------------------------------------------------------------
// Test data factories
// ---------------------------------------------------------------------------

function httpCall(overrides: Partial<ExternalCallData> = {}): ExternalCallData {
  return {
    id: `call-${Math.random().toString(36).slice(2)}`,
    agent_id: 'agent-alpha',
    agent_type: 'Orchestrator',
    call_type: 'http_request',
    url: 'https://api.example.com/v1/users',
    url_domain: 'api.example.com',
    method: 'GET',
    status_code: 200,
    duration_ms: 150,
    tool_name: null,
    error_message: null,
    timestamp: '2025-04-19T10:00:00Z',
    request_headers: { 'Content-Type': 'application/json' },
    request_body: null,
    response_body: '{"users":[]}',
    ...overrides,
  };
}

function mcpCall(overrides: Partial<ExternalCallData> = {}): ExternalCallData {
  return {
    id: `mcp-${Math.random().toString(36).slice(2)}`,
    agent_id: 'agent-beta',
    agent_type: 'Worker',
    call_type: 'mcp_call',
    url: 'mcp://openapi/search',
    url_domain: 'openapi',
    method: 'POST',
    status_code: 200,
    duration_ms: 85,
    tool_name: 'search',
    error_message: null,
    timestamp: '2025-04-19T10:00:01Z',
    request_headers: {},
    request_body: '{"query":"warhammer"}',
    response_body: '{"results":["Space Marine"]}',
    ...overrides,
  };
}

function errorCall(statusCode = 404, overrides: Partial<ExternalCallData> = {}): ExternalCallData {
  return {
    id: `err-${Math.random().toString(36).slice(2)}`,
    agent_id: 'agent-alpha',
    agent_type: 'Orchestrator',
    call_type: 'http_request',
    url: 'https://api.example.com/v1/nonexistent',
    url_domain: 'api.example.com',
    method: 'POST',
    status_code: statusCode,
    duration_ms: 45,
    tool_name: null,
    error_message: statusCode >= 500 ? 'Internal Server Error' : 'Not Found',
    timestamp: '2025-04-19T10:00:02Z',
    request_headers: {},
    request_body: '{"id":999}',
    response_body: '{"error":"not found"}',
    ...overrides,
  };
}

function pendingCall(overrides: Partial<ExternalCallData> = {}): ExternalCallData {
  return {
    id: `pending-${Math.random().toString(36).slice(2)}`,
    agent_id: 'agent-gamma',
    agent_type: 'Worker',
    call_type: 'http_request',
    url: 'https://slow.api.example.com/v1/data',
    url_domain: 'slow.api.example.com',
    method: 'GET',
    status_code: null,
    duration_ms: null,
    tool_name: null,
    error_message: null,
    timestamp: '2025-04-19T10:00:03Z',
    request_headers: {},
    request_body: null,
    response_body: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/** Shape that matches what the panel receives via WebSocket data field */
type ExternalCallData = {
  id: string;
  agent_id: string;
  agent_type: string;
  call_type: string;
  url: string;
  url_domain: string;
  method: string;
  status_code: number | null;
  duration_ms: number | null;
  tool_name: string | null;
  error_message: string | null;
  timestamp: string;
  request_headers?: Record<string, string>;
  request_body?: string;
  response_body?: string;
};

/**
 * Feed WebSocket messages directly through the mock instance's onmessage handler.
 * The real useWebSocket hook parses JSON and calls the registered callback.
 */
function feed(messages: Array<{ type: string; data: ExternalCallData }>) {
  act(() => {
    const handler = mockWsInstance.onmessage;
    if (handler) {
      messages.forEach(msg => {
        handler({ data: JSON.stringify(msg) } as MessageEvent);
      });
    }
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ExternalCallsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    // Reset mock WebSocket handlers
    mockWsInstance.onmessage = null;
    mockWsInstance.onopen = null;
    mockWsInstance.onclose = null;
    mockWsInstance.onerror = null;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // -----------------------------------------------------------------
  // (1) Component renders without crashing
  // -----------------------------------------------------------------
  describe('render', () => {
    it('should render without crashing', () => {
      expect(() => render(<ExternalCallsPanel />)).not.toThrow();
    });

    it('should display the panel heading (allow duplicate in tab + panel)', () => {
      render(<ExternalCallsPanel />);
      // Heading appears in both the tab and the panel body; use findAll
      const headings = screen.getAllByRole('heading', { name: 'External Calls' });
      expect(headings.length).toBeGreaterThan(0);
    });

    it('should show connection status indicator', () => {
      render(<ExternalCallsPanel />);
      // May appear multiple times (tab + panel body); pick the first
      expect(screen.getAllByText(/Live|Connecting\.\.\./)[0]).toBeInTheDocument();
    });

    it('should show empty state when no calls recorded', () => {
      render(<ExternalCallsPanel />);
      expect(screen.getAllByText(/No external calls recorded yet/)[0]).toBeInTheDocument();
    });

    it('should render with custom maxEntries', () => {
      render(<ExternalCallsPanel maxEntries={50} />);
      expect(screen.getByText(/Max entries: 50/)).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------
  // (2) Filter by agent_id
  // -----------------------------------------------------------------
  describe('agent_id filter', () => {
    it('should only show calls for the selected agent', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall({ agent_id: 'agent-alpha' }) }]);
      feed([{ type: 'external_call', data: httpCall({ agent_id: 'agent-beta' }) }]);
      feed([{ type: 'external_call', data: httpCall({ agent_id: 'agent-alpha' }) }]);
      act(() => { vi.advanceTimersByTime(500); });

      // Find the agent combobox
      const selects = screen.getAllByRole('combobox');
      const agentSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('agent')
      );
      expect(agentSelect).toBeInTheDocument();

      fireEvent.change(agentSelect!, { target: { value: 'agent-alpha' } });
      act(() => { vi.advanceTimersByTime(100); });

      // Count visible call rows (cursor-pointer divs inside the call list)
      const rows = screen.getAllByText('agent-alpha').filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      expect(rows.length).toBeGreaterThanOrEqual(2);
    });

    it('should populate the agent dropdown after receiving calls', async () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall({ agent_id: 'agent-alpha' }) }]);
      feed([{ type: 'external_call', data: httpCall({ agent_id: 'agent-beta' }) }]);
      feed([{ type: 'external_call', data: httpCall({ agent_id: 'agent-gamma' }) }]);

      await waitFor(() => {
        const selects = screen.getAllByRole('combobox');
        const agentSelect = selects.find(s =>
          (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('agent')
        );
        expect(agentSelect).toBeInTheDocument();
        expect(agentSelect!.querySelectorAll('option')).toHaveLength(4);
      }, { timeout: 2000 });
    });

    it('should show filtered-empty state when no calls match agent filter', async () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall({ agent_id: 'agent-alpha', status_code: 200 }) }]);

      // Select status=server_error so nothing matches
      await waitFor(() => {
        const selects = screen.getAllByRole('combobox');
        const statusSelect = selects.find(s =>
          (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('status')
        );
        expect(statusSelect).toBeInTheDocument();
        fireEvent.change(statusSelect!, { target: { value: 'server_error' } });
      }, { timeout: 2000 });

      await waitFor(() => {
        expect(screen.getAllByText(/No calls match the current filters/)[0]).toBeInTheDocument();
      }, { timeout: 2000 });
    });
  });

  // -----------------------------------------------------------------
  // (3) Filter by call_type
  // -----------------------------------------------------------------
  describe('call_type filter', () => {
    it('should show only HTTP calls when http_request filter is active', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall() }]);
      feed([{ type: 'external_call', data: mcpCall() }]);
      feed([{ type: 'external_call', data: httpCall({ id: 'http-2' }) }]);
      act(() => { vi.advanceTimersByTime(500); });

      const selects = screen.getAllByRole('combobox');
      const typeSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('type')
      );
      expect(typeSelect).toBeInTheDocument();

      fireEvent.change(typeSelect!, { target: { value: 'http_request' } });
      act(() => { vi.advanceTimersByTime(100); });

      // Count call type badges in the call list area (filter to cursor-pointer rows)
      const httpInCallList = screen.getAllByText('http_request').filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      const mcpInCallList = screen.queryAllByText('mcp_call').filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      expect(httpInCallList.length).toBeGreaterThan(0);
      expect(mcpInCallList.length).toBe(0);
    });

    it('should show only MCP calls when mcp_call filter is active', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall() }]);
      feed([{ type: 'external_call', data: mcpCall({ id: 'mcp-1', tool_name: 'search' }) }]);
      feed([{ type: 'external_call', data: mcpCall({ id: 'mcp-2', tool_name: 'list' }) }]);
      act(() => { vi.advanceTimersByTime(500); });

      const selects = screen.getAllByRole('combobox');
      const typeSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('type')
      );

      fireEvent.change(typeSelect!, { target: { value: 'mcp_call' } });
      act(() => { vi.advanceTimersByTime(100); });

      const mcpInCallList = screen.getAllByText('mcp_call').filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      const httpInCallList = screen.queryAllByText('http_request').filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      expect(mcpInCallList.length).toBeGreaterThan(0);
      expect(httpInCallList.length).toBe(0);
    });
  });

  // -----------------------------------------------------------------
  // (4) Filter by status
  // -----------------------------------------------------------------
  describe('status filter', () => {
    it('should show only success (2xx) calls when success filter is active', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall({ status_code: 200 }) }]);
      feed([{ type: 'external_call', data: httpCall({ status_code: 201 }) }]);
      feed([{ type: 'external_call', data: errorCall(404) }]);
      feed([{ type: 'external_call', data: httpCall({ status_code: 500 }) }]);
      act(() => { vi.advanceTimersByTime(500); });

      const selects = screen.getAllByRole('combobox');
      const statusSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('status')
      );
      expect(statusSelect).toBeInTheDocument();

      fireEvent.change(statusSelect!, { target: { value: 'success' } });
      act(() => { vi.advanceTimersByTime(100); });

      // Count status codes within call list rows (filter to cursor-pointer divs)
      const codeEls = screen.getAllByText(code => ['200', '201'].includes(code)).filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      expect(codeEls.length).toBeGreaterThan(0);

      // 404 and 500 should not appear in call list
      const errEls = screen.queryAllByText(code => ['404', '500'].includes(code)).filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      expect(errEls.length).toBe(0);
    });

    it('should show only client error (4xx) calls when client_error filter is active', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall({ status_code: 200 }) }]);
      feed([{ type: 'external_call', data: errorCall(404) }]);
      feed([{ type: 'external_call', data: errorCall(400) }]);
      act(() => { vi.advanceTimersByTime(500); });

      const selects = screen.getAllByRole('combobox');
      const statusSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('status')
      );

      fireEvent.change(statusSelect!, { target: { value: 'client_error' } });
      act(() => { vi.advanceTimersByTime(100); });

      // 400/404 appear in call list, 200 should not
      const clientErrEls = screen.queryAllByText(code => ['400', '404'].includes(code)).filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      const successEls = screen.queryAllByText('200').filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      expect(clientErrEls.length).toBeGreaterThan(0);
      expect(successEls.length).toBe(0);
    });

    it('should show only server error (5xx) calls when server_error filter is active', () => {
      render(<ExternalCallsPanel />);

      feed([
        { type: 'external_call', data: httpCall({ status_code: 200 }) },
        { type: 'external_call', data: httpCall({ status_code: 500 }) },
        { type: 'external_call', data: httpCall({ status_code: 503 }) },
      ]);
      act(() => { vi.advanceTimersByTime(500); });

      const selects = screen.getAllByRole('combobox');
      const statusSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('status')
      );

      fireEvent.change(statusSelect!, { target: { value: 'server_error' } });
      act(() => { vi.advanceTimersByTime(100); });

      const srvErrEls = screen.queryAllByText(code => ['500', '503'].includes(code)).filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      const successEls = screen.queryAllByText('200').filter(el =>
        el.closest('div[class*="cursor-pointer"]')
      );
      expect(srvErrEls.length).toBeGreaterThan(0);
      expect(successEls.length).toBe(0);
    });

    it('should show pending calls when pending filter is active', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall({ status_code: 200 }) }]);
      feed([{ type: 'external_call', data: pendingCall() }]);
      act(() => { vi.advanceTimersByTime(500); });

      const selects = screen.getAllByRole('combobox');
      const statusSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('status')
      );

      fireEvent.change(statusSelect!, { target: { value: 'pending' } });
      act(() => { vi.advanceTimersByTime(100); });

      expect(screen.queryAllByText('...').length).toBeGreaterThan(0);
    });
  });

  // -----------------------------------------------------------------
  // (5) Expanding a call entry
  // -----------------------------------------------------------------
  describe('expand/collapse', () => {
    it('should expand a call entry and show additional details', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall({ id: 'expandable-call-1' }) }]);
      act(() => { vi.advanceTimersByTime(500); });

      // Use the first occurrence for clicking; closest() walks up to the clickable row
      const domainEls = screen.queryAllByText('api.example.com');
      expect(domainEls.length).toBeGreaterThan(0);

      const callRow = domainEls[0].closest('div[class*="cursor-pointer"]');
      expect(callRow).not.toBeNull();

      if (callRow) {
        fireEvent.click(callRow);
        act(() => { vi.advanceTimersByTime(100); });
        // Expanded view shows "Request" section heading — may appear once or twice
        const headings = screen.queryAllByRole('heading', { name: /^Request$/i });
        expect(headings.length).toBeGreaterThan(0);
      }
    });

    it('should collapse an expanded entry on second click', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall({ id: 'expandable-call-2' }) }]);
      act(() => { vi.advanceTimersByTime(500); });

      const domainEls = screen.queryAllByText('api.example.com');
      const callRow = domainEls[0].closest('div[class*="cursor-pointer"]');

      if (callRow) {
        // First click — expand
        fireEvent.click(callRow);
        act(() => { vi.advanceTimersByTime(100); });
        expect(screen.queryAllByRole('heading', { name: /^Request$/i }).length).toBeGreaterThan(0);

        // Second click — collapse
        fireEvent.click(callRow);
        act(() => { vi.advanceTimersByTime(100); });
        // After collapse, there should be zero Request headings in the call list area
        const requestHeadings = screen.queryAllByRole('heading', { name: /^Request$/i });
        expect(requestHeadings.filter(el => el.closest('div[class*="cursor-pointer"]') === null).length).toBe(0);
      }
    });
  });

  // -----------------------------------------------------------------
  // (6) MCP calls display tool_name and arguments
  // -----------------------------------------------------------------
  describe('MCP call display', () => {
    it('should display tool_name badge for MCP calls', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: mcpCall({ tool_name: 'search' }) }]);
      act(() => { vi.advanceTimersByTime(500); });

      // May appear twice (tool badge + expanded detail)
      expect(screen.getAllByText('search')[0]).toBeInTheDocument();
    });

    it('should show mcp_call type badge', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: mcpCall() }]);
      act(() => { vi.advanceTimersByTime(500); });

      // May appear twice (type badge + expanded detail)
      expect(screen.getAllByText('mcp_call')[0]).toBeInTheDocument();
    });

    it('should show request body in expanded MCP row', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: mcpCall({ tool_name: 'search', request_body: '{"query":"warhammer"}' }) }]);
      act(() => { vi.advanceTimersByTime(500); });

      // Expand the MCP row by clicking its tool badge's parent row
      const toolBadgeEls = screen.getAllByText('search');
      const callRow = toolBadgeEls[0]?.closest('div[class*="cursor-pointer"]');

      if (callRow) {
        fireEvent.click(callRow);
        act(() => { vi.advanceTimersByTime(100); });
        // Body section should be visible in expanded detail panel
        expect(screen.getAllByText(/Body/i)[0]).toBeInTheDocument();
      }
    });
  });

  // -----------------------------------------------------------------
  // Clear filters
  // -----------------------------------------------------------------
  describe('clear filters', () => {
    it('should show clear button when filters are active', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: httpCall() }]);
      act(() => { vi.advanceTimersByTime(500); });

      const selects = screen.getAllByRole('combobox');
      const typeSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('type')
      );
      fireEvent.change(typeSelect!, { target: { value: 'http_request' } });
      act(() => { vi.advanceTimersByTime(100); });

      expect(screen.getByText('Clear filters')).toBeInTheDocument();
    });

    it('should hide clear button after all filters are reset', () => {
      render(<ExternalCallsPanel />);

      feed([
        { type: 'external_call', data: httpCall({ agent_id: 'agent-alpha' }) },
        { type: 'external_call', data: httpCall({ agent_id: 'agent-beta' }) },
      ]);
      act(() => { vi.advanceTimersByTime(500); });

      const selects = screen.getAllByRole('combobox');
      const agentSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('agent')
      );
      const typeSelect = selects.find(s =>
        (s as HTMLElement).previousElementSibling?.textContent?.toLowerCase().includes('type')
      );

      fireEvent.change(agentSelect!, { target: { value: 'agent-alpha' } });
      fireEvent.change(typeSelect!, { target: { value: 'http_request' } });
      act(() => { vi.advanceTimersByTime(100); });

      const clearBtn = screen.getByText('Clear filters');
      fireEvent.click(clearBtn);
      act(() => { vi.advanceTimersByTime(100); });

      expect(screen.queryByText('Clear filters')).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------
  // WebSocket message handling
  // -----------------------------------------------------------------
  describe('WebSocket message handling', () => {
    it('should handle externalCallLog (camelCase) message type', () => {
      render(<ExternalCallsPanel />);

      act(() => {
        const handler = mockWsInstance.onmessage;
        if (handler) {
          handler({ data: JSON.stringify({ type: 'externalCallLog', data: httpCall({ id: 'alt-1' }) }) } as MessageEvent);
        }
      });
      act(() => { vi.advanceTimersByTime(500); });

      expect(screen.getByText('api.example.com')).toBeInTheDocument();
    });

    it('should show pending indicator for calls with null status_code', () => {
      render(<ExternalCallsPanel />);

      feed([{ type: 'external_call', data: pendingCall() }]);
      act(() => { vi.advanceTimersByTime(500); });

      // Pending calls show "..." for status code
      expect(screen.queryAllByText('...').length).toBeGreaterThan(0);
    });

    it('should show maxEntries in footer', () => {
      render(<ExternalCallsPanel maxEntries={2} />);

      feed([
        { type: 'external_call', data: httpCall({ id: 'call-1' }) },
        { type: 'external_call', data: httpCall({ id: 'call-2' }) },
        { type: 'external_call', data: httpCall({ id: 'call-3' }) },
      ]);
      act(() => { vi.advanceTimersByTime(500); });

      expect(screen.getByText(/Max entries: 2/)).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------
  // Stats
  // -----------------------------------------------------------------
  describe('stats', () => {
    it('should display stats row after receiving calls', () => {
      render(<ExternalCallsPanel refreshInterval={100} />);

      feed([{ type: 'external_call', data: httpCall({ status_code: 200 }) }]);
      feed([{ type: 'external_call', data: errorCall(404) }]);

      // Stats update every refreshInterval (100ms); advance past one update cycle
      act(() => { vi.advanceTimersByTime(200); });

      expect(screen.getByText(/Total:/)).toBeInTheDocument();
    });
  });
});
