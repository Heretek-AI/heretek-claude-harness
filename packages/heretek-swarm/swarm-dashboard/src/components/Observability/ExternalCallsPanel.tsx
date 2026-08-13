/**
 * External Calls Panel
 *
 * Real-time dashboard for monitoring external API calls made by agents.
 * Visualizes HTTP calls, MCP tool invocations, and other external communications.
 *
 * Features:
 * - Real-time call stream via WebSocket
 * - Filter by agent_id, call_type, and status
 * - Color-coded HTTP methods and status codes
 * - Expandable rows showing request/response details
 * - MCP call support with tool_name and arguments/result views
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useWebSocket, WebSocketMessage } from '../../hooks/useWebSocket';

// Types
interface ExternalCallEntry {
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
}

interface ExternalCallsPanelProps {
  maxEntries?: number;
  refreshInterval?: number;
}

// Extract domain from URL
function extractDomain(url: string): string {
  if (!url) return '';
  let result = url;
  const protocolIndex = result.indexOf('://');
  if (protocolIndex !== -1) {
    result = result.substring(protocolIndex + 3);
  }
  const separators = ['/', '?', '#'];
  for (const sep of separators) {
    const sepIndex = result.indexOf(sep);
    if (sepIndex !== -1) {
      result = result.substring(0, sepIndex);
    }
  }
  return result;
}

// HTTP method colors
function getMethodColor(method: string): string {
  switch (method.toUpperCase()) {
    case 'GET': return 'bg-blue-500/20 text-blue-400 border-blue-500';
    case 'POST': return 'bg-green-500/20 text-green-400 border-green-500';
    case 'PUT': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500';
    case 'PATCH': return 'bg-orange-500/20 text-orange-400 border-orange-500';
    case 'DELETE': return 'bg-red-500/20 text-red-400 border-red-500';
    case 'HEAD': return 'bg-purple-500/20 text-purple-400 border-purple-500';
    case 'OPTIONS': return 'bg-gray-500/20 text-gray-400 border-gray-500';
    default: return 'bg-gray-500/20 text-gray-400 border-gray-500';
  }
}

// Status code colors
function getStatusColor(statusCode: number | null): string {
  if (statusCode === null) return 'text-gray-400';
  if (statusCode >= 200 && statusCode < 300) return 'text-green-400';
  if (statusCode >= 300 && statusCode < 400) return 'text-yellow-400';
  if (statusCode >= 400 && statusCode < 500) return 'text-orange-400';
  if (statusCode >= 500) return 'text-red-400';
  return 'text-gray-400';
}

function getStatusBgColor(statusCode: number | null): string {
  if (statusCode === null) return 'bg-gray-500/20';
  if (statusCode >= 200 && statusCode < 300) return 'bg-green-500/20';
  if (statusCode >= 300 && statusCode < 400) return 'bg-yellow-500/20';
  if (statusCode >= 400 && statusCode < 500) return 'bg-orange-500/20';
  if (statusCode >= 500) return 'bg-red-500/20';
  return 'bg-gray-500/20';
}

// Call type badge colors
function getCallTypeColor(callType: string): string {
  switch (callType.toLowerCase()) {
    case 'http_request': return 'bg-blue-500';
    case 'mcp_call': return 'bg-purple-500';
    case 'tool_call': return 'bg-green-500';
    case 'api_call': return 'bg-cyan-500';
    default: return 'bg-gray-500';
  }
}

// Format duration
function formatDuration(ms: number | null): string {
  if (ms === null) return '-';
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}


// Call Entry Row Component
const CallEntryRow: React.FC<{
  entry: ExternalCallEntry;
  isExpanded: boolean;
  onToggle: () => void;
}> = ({ entry, isExpanded, onToggle }) => {
  return (
    <div className="border-b border-gray-800">
      <div
        className="flex items-center gap-3 p-3 hover:bg-gray-800/50 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        {/* Expand indicator */}
        <div className="text-gray-500 w-4 text-center">
          {isExpanded ? '▼' : '▶'}
        </div>

        {/* Agent ID badge */}
        <div className="px-2 py-1 bg-gray-700 rounded text-xs font-mono text-blue-400 whitespace-nowrap">
          {entry.agent_id}
        </div>

        {/* Call type badge */}
        <div className={`px-2 py-1 rounded text-xs text-white whitespace-nowrap ${getCallTypeColor(entry.call_type)}`}>
          {entry.call_type}
        </div>

        {/* Tool name (if MCP) */}
        {entry.tool_name && (
          <div className="px-2 py-1 bg-purple-900/30 border border-purple-500/30 rounded text-xs text-purple-400 whitespace-nowrap">
            {entry.tool_name}
          </div>
        )}

        {/* URL domain */}
        <div className="flex-1 min-w-0">
          <span className="text-sm text-gray-300 truncate block" title={entry.url}>
            {entry.url_domain}
          </span>
        </div>

        {/* HTTP Method badge */}
        <div className={`px-2 py-1 rounded text-xs font-mono border ${getMethodColor(entry.method)}`}>
          {entry.method}
        </div>

        {/* Status code */}
        <div className={`px-2 py-1 rounded text-xs font-mono w-12 text-center ${getStatusBgColor(entry.status_code)} ${getStatusColor(entry.status_code)}`}>
          {entry.status_code ?? '...'}
        </div>

        {/* Duration */}
        <div className="text-xs text-gray-400 w-16 text-right font-mono">
          {formatDuration(entry.duration_ms)}
        </div>

        {/* Timestamp */}
        <div className="text-xs text-gray-500 w-20 text-right whitespace-nowrap">
          {new Date(entry.timestamp).toLocaleTimeString()}
        </div>
      </div>

      {/* Expanded details */}
      {isExpanded && (
        <div className="bg-gray-850 p-4 border-t border-gray-800">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Left column: Request details */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-400 uppercase">Request</h4>

              {/* URL */}
              <div>
                <div className="text-xs text-gray-500 mb-1">URL</div>
                <div className="bg-gray-900 rounded p-2 text-xs font-mono text-gray-300 break-all">
                  {entry.url}
                </div>
              </div>

              {/* Headers */}
              {entry.request_headers && Object.keys(entry.request_headers).length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">Headers</div>
                  <div className="bg-gray-900 rounded p-2 text-xs font-mono text-gray-300 overflow-auto max-h-32">
                    <pre className="whitespace-pre-wrap">
                      {JSON.stringify(entry.request_headers, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* Request body */}
              {entry.request_body && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">Body</div>
                  <div className="bg-gray-900 rounded p-2 text-xs font-mono text-gray-300 overflow-auto max-h-40">
                    <pre className="whitespace-pre-wrap">
                      {entry.request_body}
                    </pre>
                  </div>
                </div>
              )}

              {/* Error message */}
              {entry.error_message && (
                <div>
                  <div className="text-xs text-red-400 mb-1">Error</div>
                  <div className="bg-red-900/20 border border-red-500/30 rounded p-2 text-xs text-red-300">
                    {entry.error_message}
                  </div>
                </div>
              )}
            </div>

            {/* Right column: Response details */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-400 uppercase">Response</h4>

              {/* Status */}
              <div className="flex items-center gap-4">
                <div>
                  <div className="text-xs text-gray-500 mb-1">Status</div>
                  <div className={`text-lg font-mono ${getStatusColor(entry.status_code)}`}>
                    {entry.status_code ?? 'Pending'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Duration</div>
                  <div className="text-lg font-mono text-gray-300">
                    {formatDuration(entry.duration_ms)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Tool</div>
                  <div className="text-sm text-purple-400">
                    {entry.tool_name ?? '-'}
                  </div>
                </div>
              </div>

              {/* Response body */}
              {entry.response_body && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">Body</div>
                  <div className="bg-gray-900 rounded p-2 text-xs font-mono text-gray-300 overflow-auto max-h-60">
                    <pre className="whitespace-pre-wrap">
                      {entry.response_body}
                    </pre>
                  </div>
                </div>
              )}

              {/* No response body placeholder */}
              {!entry.response_body && (
                <div className="bg-gray-900/50 rounded p-4 text-center text-xs text-gray-500">
                  No response body captured
                </div>
              )}
            </div>
          </div>

          {/* Metadata footer */}
          <div className="mt-4 pt-3 border-t border-gray-700/50 flex items-center gap-6 text-xs text-gray-500">
            <div>
              <span className="text-gray-600">Agent:</span>{' '}
              <span className="text-gray-400">{entry.agent_id}</span>
            </div>
            <div>
              <span className="text-gray-600">Type:</span>{' '}
              <span className="text-gray-400">{entry.agent_type}</span>
            </div>
            <div>
              <span className="text-gray-600">Call ID:</span>{' '}
              <span className="text-gray-400 font-mono">{entry.id.slice(0, 8)}</span>
            </div>
            <div className="ml-auto">
              {new Date(entry.timestamp).toLocaleString()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Filter Bar Component
const FilterBar: React.FC<{
  agentFilter: string;
  setAgentFilter: (v: string) => void;
  callTypeFilter: string;
  setCallTypeFilter: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  uniqueAgents: string[];
  uniqueCallTypes: string[];
  onClearFilters: () => void;
  hasActiveFilters: boolean;
}> = ({
  agentFilter,
  setAgentFilter,
  callTypeFilter,
  setCallTypeFilter,
  statusFilter,
  setStatusFilter,
  uniqueAgents,
  uniqueCallTypes,
  onClearFilters,
  hasActiveFilters,
}) => {
  return (
    <div className="flex flex-wrap items-center gap-3 p-3 bg-gray-800/50 rounded-lg mb-4">
      {/* Agent filter */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-500">Agent:</label>
        <select
          value={agentFilter}
          onChange={e => setAgentFilter(e.target.value)}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white focus:border-blue-500 focus:outline-none"
        >
          <option value="">All agents</option>
          {uniqueAgents.map(agent => (
            <option key={agent} value={agent}>{agent}</option>
          ))}
        </select>
      </div>

      {/* Call type filter */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-500">Type:</label>
        <select
          value={callTypeFilter}
          onChange={e => setCallTypeFilter(e.target.value)}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white focus:border-blue-500 focus:outline-none"
        >
          <option value="">All types</option>
          {uniqueCallTypes.map(ct => (
            <option key={ct} value={ct}>{ct}</option>
          ))}
        </select>
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-500">Status:</label>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white focus:border-blue-500 focus:outline-none"
        >
          <option value="">All</option>
          <option value="success">2xx Success</option>
          <option value="redirect">3xx Redirect</option>
          <option value="client_error">4xx Client Error</option>
          <option value="server_error">5xx Server Error</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      {/* Clear filters */}
      {hasActiveFilters && (
        <button
          onClick={onClearFilters}
          className="ml-auto text-xs text-gray-400 hover:text-white transition-colors"
        >
          Clear filters
        </button>
      )}
    </div>
  );
};

// Main Component
export function ExternalCallsPanel({
  maxEntries = 100,
  refreshInterval = 2000,
}: ExternalCallsPanelProps) {
  const [calls, setCalls] = useState<ExternalCallEntry[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [stats, setStats] = useState({
    total: 0,
    success: 0,
    error: 0,
    avgDuration: 0,
  });

  // Filter state
  const [agentFilter, setAgentFilter] = useState('');
  const [callTypeFilter, setCallTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // WebSocket connection
  const handleMessage = useCallback((message: WebSocketMessage) => {
    // Handle external_call events from dashboard channel
    // Backend broadcasts 'external_call' and 'externalCallLog' (see main.py external_call_handler)
    if (message.type === 'external_call' || message.type === 'externalCallLog') {
      const data = message.data as Partial<ExternalCallEntry> | undefined;
      if (data) {
        const entry: ExternalCallEntry = {
          id: data.id ?? crypto.randomUUID(),
          agent_id: data.agent_id ?? message.agent_id ?? 'unknown',
          agent_type: data.agent_type ?? 'unknown',
          call_type: data.call_type ?? 'api_call',
          url: data.url ?? '',
          url_domain: data.url_domain ?? extractDomain(data.url ?? ''),
          method: data.method ?? 'GET',
          status_code: data.status_code ?? null,
          duration_ms: data.duration_ms ?? null,
          tool_name: data.tool_name ?? null,
          error_message: data.error_message ?? null,
          timestamp: data.timestamp ?? new Date().toISOString(),
          request_headers: data.request_headers,
          request_body: data.request_body,
          response_body: data.response_body,
        };

        setCalls(prev => {
          const updated = [entry, ...prev];
          return updated.slice(0, maxEntries);
        });
      }
    }
  }, [maxEntries]);

  const { connected } = useWebSocket('dashboard', {
    onMessage: handleMessage,
    onOpen: () => setIsConnected(true),
    onClose: () => setIsConnected(false),
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
  });

  // Update connection state
  useEffect(() => {
    setIsConnected(connected);
  }, [connected]);

  // Update stats periodically
  useEffect(() => {
    const interval = setInterval(() => {
      setStats(prev => {
        const total = calls.length;
        const success = calls.filter(c => c.status_code && c.status_code >= 200 && c.status_code < 300).length;
        const error = calls.filter(c => c.status_code && c.status_code >= 400).length;
        const durations = calls.filter(c => c.duration_ms !== null).map(c => c.duration_ms!);
        const avgDuration = durations.length > 0
          ? durations.reduce((a, b) => a + b, 0) / durations.length
          : prev.avgDuration;

        return { total, success, error, avgDuration };
      });
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [calls, refreshInterval]);

  // Extract unique values for filter dropdowns
  // Added calls.length as dep so useMemo recomputes when calls array changes
  const uniqueAgents = useMemo(() => {
    return [...new Set(calls.map(c => c.agent_id))].sort();
  }, [calls, calls.length]);

  const uniqueCallTypes = useMemo(() => {
    return [...new Set(calls.map(c => c.call_type))].sort();
  }, [calls, calls.length]);

  // Check if any filters are active
  const hasActiveFilters = agentFilter !== '' || callTypeFilter !== '' || statusFilter !== '';

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    setAgentFilter('');
    setCallTypeFilter('');
    setStatusFilter('');
  }, []);

  // Apply filters
  const filteredCalls = useMemo(() => {
    return calls.filter(call => {
      // Agent filter
      if (agentFilter && call.agent_id !== agentFilter) return false;

      // Call type filter
      if (callTypeFilter && call.call_type !== callTypeFilter) return false;

      // Status filter
      if (statusFilter) {
        const code = call.status_code;
        switch (statusFilter) {
          case 'success':
            if (!code || code < 200 || code >= 300) return false;
            break;
          case 'redirect':
            if (!code || code < 300 || code >= 400) return false;
            break;
          case 'client_error':
            if (!code || code < 400 || code >= 500) return false;
            break;
          case 'server_error':
            if (!code || code < 500) return false;
            break;
          case 'pending':
            if (code !== null) return false;
            break;
        }
      }

      return true;
    });
  }, [calls, agentFilter, callTypeFilter, statusFilter]);

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-white">External Calls</h2>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'} animate-pulse`} />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Live' : 'Connecting...'}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div>
            <span className="text-gray-500">Total:</span>
            <span className="ml-1 text-white font-mono">{stats.total}</span>
          </div>
          <div>
            <span className="text-gray-500">Success:</span>
            <span className="ml-1 text-green-400 font-mono">{stats.success}</span>
          </div>
          <div>
            <span className="text-gray-500">Errors:</span>
            <span className="ml-1 text-red-400 font-mono">{stats.error}</span>
          </div>
          <div>
            <span className="text-gray-500">Avg:</span>
            <span className="ml-1 text-gray-400 font-mono">{formatDuration(stats.avgDuration)}</span>
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <FilterBar
        agentFilter={agentFilter}
        setAgentFilter={setAgentFilter}
        callTypeFilter={callTypeFilter}
        setCallTypeFilter={setCallTypeFilter}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        uniqueAgents={uniqueAgents}
        uniqueCallTypes={uniqueCallTypes}
        onClearFilters={handleClearFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {/* Column headers */}
      <div className="flex items-center gap-3 px-3 py-2 text-xs text-gray-500 uppercase border-b border-gray-800">
        <div className="w-4" />
        <div className="w-20">Agent</div>
        <div className="w-24">Type</div>
        <div className="w-20">Tool</div>
        <div className="flex-1">URL</div>
        <div className="w-14 text-center">Method</div>
        <div className="w-12 text-center">Status</div>
        <div className="w-16 text-right">Duration</div>
        <div className="w-20 text-right">Time</div>
      </div>

      {/* Call list */}
      <div className="max-h-[500px] overflow-y-auto">
        {filteredCalls.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            {calls.length === 0
              ? 'No external calls recorded yet'
              : 'No calls match the current filters'
            }
          </div>
        ) : (
          filteredCalls.map(entry => (
            <CallEntryRow
              key={entry.id}
              entry={entry}
              isExpanded={expandedId === entry.id}
              onToggle={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
            />
          ))
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-700 flex items-center justify-between text-xs text-gray-500">
        <div>
          Showing {filteredCalls.length} of {calls.length} calls
          {hasActiveFilters && ' (filtered)'}
        </div>
        <div>
          Max entries: {maxEntries}
        </div>
      </div>
    </div>
  );
}

export default ExternalCallsPanel;
