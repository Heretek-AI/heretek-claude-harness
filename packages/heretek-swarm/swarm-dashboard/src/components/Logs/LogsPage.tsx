/**
 * Terminal/Logs Page
 *
 * Real-time system logs and terminal-like interface.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket, WebSocketMessage } from '../../hooks/useWebSocket';
import { StatusBadge } from '../UI/StatusBadge';
import { EmptyState } from '../UI/EmptyState';
import { useToast } from '../UI/Toast';
import { getHistorianEvents, HistorianEvent } from '../../api/events';

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'debug' | 'info' | 'warning' | 'error' | 'critical';
  source: string;
  message: string;
  context?: Record<string, unknown>;
}

const logLevelColors: Record<string, string> = {
  debug: 'text-gray-500',
  info: 'text-blue-400',
  warning: 'text-yellow-400',
  error: 'text-red-400',
  critical: 'text-red-600 bg-red-900/20',
};

const logLevelIcons: Record<string, string> = {
  debug: '🔍',
  info: 'ℹ',
  warning: '⚠',
  error: '✕',
  critical: '🔥',
};

/** Return Tailwind classes for an event type badge pill. */
function eventTypeBadge(eventType: string): string {
  switch (eventType) {
    case 'deliberation':
      return 'bg-blue-900/40 text-blue-300';
    case 'heartbeat':
      return 'bg-green-900/40 text-green-300';
    case 'steward_pulse':
      return 'bg-purple-900/40 text-purple-300';
    case 'routed_task':
      return 'bg-cyan-900/40 text-cyan-300';
    case 'scheduled_task':
      return 'bg-orange-900/40 text-orange-300';
    case 'agent_spawn':
      return 'bg-yellow-900/40 text-yellow-300';
    case 'agent_death':
      return 'bg-red-900/40 text-red-300';
    default:
      return 'bg-gray-700/40 text-gray-400';
  }
}

/** Map a historian event type to a log level for the terminal view. */
function inferLogLevel(eventType: string): LogEntry['level'] {
  if (eventType.includes('error') || eventType.includes('death') || eventType.includes('fail')) {
    return 'error';
  }
  if (eventType.includes('warn')) {
    return 'warning';
  }
  if (eventType.includes('debug') || eventType.includes('heartbeat') || eventType.includes('pulse')) {
    return 'debug';
  }
  return 'info';
}

export function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filterLevel, setFilterLevel] = useState<string>('all');
  const [filterSource, setFilterSource] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [historianEvents, setHistorianEvents] = useState<HistorianEvent[]>([]);
  const [historianMode, setHistorianMode] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  // Fetch historian events on mount
  const fetchHistorianEvents = useCallback(() => {
    getHistorianEvents({ limit: 50 }).then((response) => {
      setHistorianEvents(response.events);
      setHistorianMode(response.mode);
      // Tier 1.2: seed the terminal with mapped historian events when
      // the WebSocket channel is empty. The api doesn't push
      // `log_entry` messages on `ws/logs`, so without this the
      // terminal shows the empty state forever.
      setLogs((prev) => {
        if (prev.length > 0) return prev;
        return response.events.map((event) => ({
          id: event.event_id,
          timestamp: event.timestamp,
          level: inferLogLevel(event.type),
          source: event.agent_id || 'system',
          message: `${event.type}: ${JSON.stringify(event.payload).slice(0, 200)}`,
        }));
      });
    }).catch(() => {
      setHistorianMode('error');
    });
  }, []);

  useEffect(() => {
    fetchHistorianEvents();
  }, [fetchHistorianEvents]);

  // WebSocket for real-time logs
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { connected: _connected, lastMessage: _lastMessage } = useWebSocket('logs', {
    onMessage: useCallback((message: WebSocketMessage) => {
      if (message.type === 'log_entry' && message.data) {
        const logEntry: LogEntry = message.data as LogEntry;
        setLogs((prev) => [...prev.slice(-999), logEntry]); // Keep last 1000 logs
      }
    }, []),
    onOpen: useCallback(() => {
      setIsConnected(true);
      toast.success('Logs Connected', 'Real-time log streaming enabled');
    }, [toast]),
    onClose: useCallback(() => {
      setIsConnected(false);
    }, []),
  });

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Filter logs
  const filteredLogs = logs.filter((log) => {
    const matchesLevel = filterLevel === 'all' || log.level === filterLevel;
    const matchesSource = filterSource === 'all' || log.source === filterSource;
    const matchesSearch = searchTerm === '' ||
      log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.source.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesLevel && matchesSource && matchesSearch;
  });

  // Get unique sources for filter
  const sources = Array.from(new Set(logs.map((log) => log.source)));

  const handleClearLogs = useCallback(() => {
    setLogs([]);
    toast.info('Logs Cleared', 'All logs have been removed');
  }, [toast]);

  const handleExportLogs = useCallback(() => {
    const blob = new Blob([JSON.stringify(filteredLogs, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('Logs Exported', 'Log file has been downloaded');
  }, [filteredLogs, toast]);

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Terminal / Logs</h1>
          <p className="text-gray-400 text-sm mt-1">
            Real-time system logs and events
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={isConnected ? 'active' : 'inactive'} size="sm" />
          <button
            onClick={handleClearLogs}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors"
          >
            Clear
          </button>
          <button
            onClick={handleExportLogs}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
          >
            Export
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-3 p-3 bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-lg">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Level:</label>
          <select
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
            className="px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Levels</option>
            <option value="debug">Debug</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="critical">Critical</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Source:</label>
          <select
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
            className="px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Sources</option>
            {sources.map((source) => (
              <option key={source} value={source}>{source}</option>
            ))}
          </select>
        </div>

        <div className="flex-1">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search logs..."
            className="w-full px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Auto-scroll:</label>
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              autoScroll ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-400'
            }`}
          >
            {autoScroll ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      {/* Event History Section */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between p-3 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
              Event History
            </h2>
            {historianMode && (
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                historianMode === 'error' || historianMode === 'unavailable'
                  ? 'bg-red-900/30 text-red-400'
                  : historianMode === 'jsonl'
                    ? 'bg-yellow-900/30 text-yellow-400'
                    : 'bg-green-900/30 text-green-400'
              }`}>
                {historianMode}
              </span>
            )}
            <span className="text-xs text-gray-500">
              {historianEvents.length} event{historianEvents.length !== 1 ? 's' : ''}
            </span>
          </div>
          <button
            onClick={fetchHistorianEvents}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium transition-colors"
            title="Refresh event history"
          >
            Refresh History
          </button>
        </div>

        <div className="max-h-48 overflow-auto">
          {historianEvents.length > 0 ? (
            <div className="divide-y divide-gray-700/50">
              {historianEvents.map((event) => (
                <div
                  key={event.event_id}
                  className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-700/30 transition-colors"
                >
                  <span className="text-gray-500 shrink-0 font-mono text-xs w-20">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium ${eventTypeBadge(event.type)}`}>
                    {event.type}
                  </span>
                  <span className="text-gray-400 shrink-0 font-mono text-xs w-24 truncate">
                    {event.agent_id}
                  </span>
                  <span className="flex-1 text-gray-600 text-xs truncate font-mono">
                    {JSON.stringify(event.payload).slice(0, 100)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center">
              <p className="text-sm text-gray-500">
                {historianMode === 'error'
                  ? 'Failed to load historical events — historian may be unavailable'
                  : historianMode === 'unavailable'
                    ? 'Historian is not available in this deployment mode'
                    : 'No historical events recorded'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Stats Bar */}
      <div className="flex items-center gap-4 text-sm text-gray-400">
        <span>Total: <span className="text-white font-mono">{logs.length}</span></span>
        <span>Filtered: <span className="text-white font-mono">{filteredLogs.length}</span></span>
        <span className="flex-1" />
        <span>Debug: <span className="text-gray-500 font-mono">{logs.filter(l => l.level === 'debug').length}</span></span>
        <span>Info: <span className="text-blue-400 font-mono">{logs.filter(l => l.level === 'info').length}</span></span>
        <span>Warning: <span className="text-yellow-400 font-mono">{logs.filter(l => l.level === 'warning').length}</span></span>
        <span>Error: <span className="text-red-400 font-mono">{logs.filter(l => l.level === 'error').length}</span></span>
      </div>

      {/* Logs Terminal */}
      <div className="flex-1 bg-gray-950 border border-gray-700 rounded-lg overflow-hidden flex flex-col">
        <div className="flex-1 overflow-auto font-mono text-sm p-4">
          {filteredLogs.length > 0 ? (
            <div className="space-y-1">
              {filteredLogs.map((log) => (
                <div
                  key={log.id}
                  className={`flex items-start gap-3 py-1 px-2 rounded hover:bg-gray-900 ${
                    logLevelColors[log.level] || 'text-gray-400'
                  }`}
                >
                  <span className="text-gray-600 shrink-0">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="shrink-0">{logLevelIcons[log.level]}</span>
                  <span className="text-gray-500 shrink-0 w-32 truncate">
                    [{log.source}]
                  </span>
                  <span className="flex-1 break-all">{log.message}</span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          ) : historianEvents.length > 0 ? (
            <div className="flex items-center justify-center h-full p-6">
              <p className="text-sm text-gray-500">
                Real-time log streaming will appear here
              </p>
            </div>
          ) : (
            <EmptyState
              icon="📟"
              title="No logs to display"
              description="Logs will appear here as they are generated by the system"
              size="sm"
            />
          )}
        </div>

        {/* Quick Actions */}
        <div className="border-t border-gray-800 p-2 flex items-center gap-2">
          <button
            onClick={() => setFilterLevel('error')}
            className="px-2 py-1 bg-red-900/30 text-red-400 rounded text-xs hover:bg-red-900/50 transition-colors"
          >
            Show Errors Only
          </button>
          <button
            onClick={() => {
              setFilterLevel('all');
              setFilterSource('all');
              setSearchTerm('');
            }}
            className="px-2 py-1 bg-gray-800 text-gray-400 rounded text-xs hover:bg-gray-700 transition-colors"
          >
            Reset Filters
          </button>
        </div>
      </div>
    </div>
  );
}

export default LogsPage;
