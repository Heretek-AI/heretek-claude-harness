/**
 * DebugPanel Component
 *
 * Comprehensive debug panel for developers with:
 * - Raw JSON viewer for API responses
 * - API response times display
 * - State transitions log (Zustand state changes)
 * - Network request waterfall
 * - Log viewer with filtering
 *
 * Only visible when Developer Mode is enabled.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useDeveloperMode } from '../Settings/DeveloperModeToggle';
import { getLogHistory, clearLogHistory, type LogEntry, type LogLevel } from '../../utils/logger';

export interface DebugPanelProps {
  className?: string;
}

export interface ApiRequestLog {
  id: string;
  method: string;
  url: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  status?: number;
  requestData?: unknown;
  responseData?: unknown;
  error?: string;
}

export interface StateTransition {
  timestamp: string;
  actionType: string;
  previousState?: Record<string, unknown>;
  nextState?: Record<string, unknown>;
}

interface NetworkRequest {
  id: string;
  name: string;
  type: 'fetch' | 'websocket' | 'other';
  startTime: number;
  endTime?: number;
  duration?: number;
  status: 'pending' | 'success' | 'error';
}

const LOG_LEVEL_FILTERS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

export function DebugPanel({ className = '' }: DebugPanelProps) {
  const isDeveloperMode = useDeveloperMode();
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'logs' | 'api' | 'state' | 'network'>('logs');
  const [logFilter, setLogFilter] = useState<LogLevel>('debug');
  const [apiLogs, setApiLogs] = useState<ApiRequestLog[]>([]);
  const [stateTransitions, setStateTransitions] = useState<StateTransition[]>([]);
  const [networkRequests, setNetworkRequests] = useState<NetworkRequest[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Listen for log entries
  useEffect(() => {
    const handleLogEntry = (event: CustomEvent) => {
      setLogs((prev) => [...prev.slice(-499), event.detail]);
    };

    window.addEventListener('log-entry', handleLogEntry as EventListener);
    return () => window.removeEventListener('log-entry', handleLogEntry as EventListener);
  }, []);

  // Listen for API requests
  useEffect(() => {
    const handleApiRequest = (event: CustomEvent) => {
      const log = event.detail as ApiRequestLog;
      setApiLogs((prev) => [...prev.slice(-99), log]);
    };

    window.addEventListener('api-request', handleApiRequest as EventListener);
    return () => window.removeEventListener('api-request', handleApiRequest as EventListener);
  }, []);

  // Listen for state transitions
  useEffect(() => {
    const handleStateTransition = (event: CustomEvent) => {
      const transition = event.detail as StateTransition;
      setStateTransitions((prev) => [...prev.slice(-99), transition]);
    };

    window.addEventListener('state-transition', handleStateTransition as EventListener);
    return () => window.removeEventListener('state-transition', handleStateTransition as EventListener);
  }, []);

  // Listen for network requests
  useEffect(() => {
    const handleNetworkRequest = (event: CustomEvent) => {
      const request = event.detail as NetworkRequest;
      setNetworkRequests((prev) => {
        const existing = prev.findIndex((r) => r.id === request.id);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = request;
          return updated;
        }
        return [...prev.slice(-99), request];
      });
    };

    window.addEventListener('network-request', handleNetworkRequest as EventListener);
    return () => window.removeEventListener('network-request', handleNetworkRequest as EventListener);
  }, []);

  // Auto-scroll logs to bottom
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Keyboard shortcut to toggle panel (Ctrl/Cmd + Shift + D)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const filteredLogs = logs.filter((log) => LOG_LEVEL_FILTERS[log.level] >= LOG_LEVEL_FILTERS[logFilter]);

  const handleClearLogs = useCallback(() => {
    clearLogHistory();
    setLogs([]);
  }, []);

  const handleClearApiLogs = useCallback(() => {
    setApiLogs([]);
  }, []);

  const handleClearStateTransitions = useCallback(() => {
    setStateTransitions([]);
  }, []);

  const handleClearNetwork = useCallback(() => {
    setNetworkRequests([]);
  }, []);

  const formatDuration = (ms?: number): string => {
    if (ms === undefined) return '...';
    if (ms < 1) return `${Math.round(ms * 1000)}μs`;
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatTime = (timestamp: number | string): string => {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      // @ts-ignore - fractionalSecondDigits not in all TypeScript lib versions
      fractionalSecondDigits: 3
    });
  };

  if (!isDeveloperMode) return null;

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-4 right-4 z-50 p-3 rounded-full shadow-lg transition-all duration-200 ${
          isOpen
            ? 'bg-gray-700 hover:bg-gray-600'
            : 'bg-purple-600 hover:bg-purple-700 animate-pulse-slow'
        }`}
        aria-label="Toggle debug panel"
        aria-expanded={isOpen}
      >
        <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
      </button>

      {/* Panel */}
      {isOpen && (
        <div
          ref={panelRef}
          className={`fixed bottom-20 right-4 z-50 w-[800px] max-w-[calc(100vw-2rem)] bg-gray-900 border border-gray-700 rounded-xl shadow-2xl flex flex-col ${className}`}
          style={{ maxHeight: 'calc(100vh - 12rem)' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
            <div className="flex items-center gap-3">
              <h3 className="text-white font-semibold">Debug Panel</h3>
              <span className="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-full border border-purple-500/30">
                DEV MODE
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Ctrl+Shift+D to toggle</span>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-gray-800 rounded transition-colors"
                aria-label="Close panel"
              >
                <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-gray-700">
            {[
              { id: 'logs', label: 'Logs', count: logs.length },
              { id: 'api', label: 'API', count: apiLogs.length },
              { id: 'state', label: 'State', count: stateTransitions.length },
              { id: 'network', label: 'Network', count: networkRequests.length },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-purple-500 text-purple-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300'
                }`}
              >
                {tab.label}
                <span className="ml-2 text-xs px-1.5 py-0.5 bg-gray-800 rounded-full">
                  {tab.count}
                </span>
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-hidden flex flex-col min-h-[300px]">
            {/* Logs Tab */}
            {activeTab === 'logs' && (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex items-center gap-2 p-2 border-b border-gray-700">
                  <select
                    value={logFilter}
                    onChange={(e) => setLogFilter(e.target.value as LogLevel)}
                    className="px-2 py-1 bg-gray-800 border border-gray-600 rounded text-sm text-gray-300 focus:outline-none focus:border-purple-500"
                  >
                    <option value="debug">Debug</option>
                    <option value="info">Info</option>
                    <option value="warn">Warn</option>
                    <option value="error">Error</option>
                  </select>
                  <button
                    onClick={handleClearLogs}
                    className="px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition-colors"
                  >
                    Clear
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 font-mono text-xs space-y-1">
                  {filteredLogs.length === 0 ? (
                    <div className="text-gray-500 text-center py-8">No logs yet</div>
                  ) : (
                    filteredLogs.map((log, index) => (
                      <div
                        key={index}
                        className={`p-2 rounded border-l-2 ${
                          log.level === 'error'
                            ? 'bg-red-900/20 border-red-500'
                            : log.level === 'warn'
                            ? 'bg-yellow-900/20 border-yellow-500'
                            : log.level === 'info'
                            ? 'bg-blue-900/20 border-blue-500'
                            : 'bg-gray-800/50 border-gray-500'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-gray-500">{formatTime(log.timestamp)}</span>
                          <span className={`font-bold ${
                            log.level === 'error' ? 'text-red-400' :
                            log.level === 'warn' ? 'text-yellow-400' :
                            log.level === 'info' ? 'text-blue-400' :
                            'text-gray-400'
                          }`}>
                            {log.level.toUpperCase()}
                          </span>
                          <span className="text-purple-400">[{log.component}]</span>
                        </div>
                        <div className="text-gray-300 mt-1">{log.message}</div>
                        {log.context && (
                          <pre className="mt-1 text-gray-500 overflow-x-auto">
                            {JSON.stringify(log.context, null, 2)}
                          </pre>
                        )}
                      </div>
                    ))
                  )}
                  <div ref={logsEndRef} />
                </div>
              </div>
            )}

            {/* API Tab */}
            {activeTab === 'api' && (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex items-center justify-between p-2 border-b border-gray-700">
                  <span className="text-xs text-gray-500">API Request History</span>
                  <button
                    onClick={handleClearApiLogs}
                    className="px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition-colors"
                  >
                    Clear
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 font-mono text-xs space-y-2">
                  {apiLogs.length === 0 ? (
                    <div className="text-gray-500 text-center py-8">No API requests yet</div>
                  ) : (
                    [...apiLogs].reverse().map((log) => (
                      <div key={log.id} className="p-3 bg-gray-800/50 rounded border border-gray-700">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                            log.method === 'GET' ? 'bg-green-900/50 text-green-400' :
                            log.method === 'POST' ? 'bg-blue-900/50 text-blue-400' :
                            log.method === 'PUT' ? 'bg-yellow-900/50 text-yellow-400' :
                            log.method === 'DELETE' ? 'bg-red-900/50 text-red-400' :
                            'bg-gray-700 text-gray-400'
                          }`}>
                            {log.method}
                          </span>
                          <span className="text-gray-300 truncate flex-1">{log.url}</span>
                          {log.status && (
                            <span className={`px-2 py-0.5 rounded text-xs ${
                              log.status >= 200 && log.status < 300 ? 'bg-green-900/50 text-green-400' :
                              log.status >= 400 ? 'bg-red-900/50 text-red-400' :
                              'bg-yellow-900/50 text-yellow-400'
                            }`}>
                              {log.status}
                            </span>
                          )}
                          <span className="text-gray-500">{formatDuration(log.duration)}</span>
                        </div>
                        {log.error && (
                          <div className="text-red-400 mt-1">{log.error}</div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* State Tab */}
            {activeTab === 'state' && (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex items-center justify-between p-2 border-b border-gray-700">
                  <span className="text-xs text-gray-500">Zustand State Transitions</span>
                  <button
                    onClick={handleClearStateTransitions}
                    className="px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition-colors"
                  >
                    Clear
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 font-mono text-xs space-y-2">
                  {stateTransitions.length === 0 ? (
                    <div className="text-gray-500 text-center py-8">No state transitions yet</div>
                  ) : (
                    [...stateTransitions].reverse().map((transition, index) => (
                      <div key={index} className="p-3 bg-gray-800/50 rounded border border-gray-700">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-gray-500">{formatTime(transition.timestamp)}</span>
                          <span className="text-purple-400 font-bold">{transition.actionType}</span>
                        </div>
                        {transition.previousState && (
                          <details className="mb-1">
                            <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">Previous State</summary>
                            <pre className="mt-1 text-gray-400 overflow-x-auto bg-gray-900 p-2 rounded">
                              {JSON.stringify(transition.previousState, null, 2)}
                            </pre>
                          </details>
                        )}
                        {transition.nextState && (
                          <details>
                            <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">Next State</summary>
                            <pre className="mt-1 text-green-400 overflow-x-auto bg-gray-900 p-2 rounded">
                              {JSON.stringify(transition.nextState, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Network Tab */}
            {activeTab === 'network' && (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex items-center justify-between p-2 border-b border-gray-700">
                  <span className="text-xs text-gray-500">Network Requests</span>
                  <button
                    onClick={handleClearNetwork}
                    className="px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded transition-colors"
                  >
                    Clear
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 font-mono text-xs space-y-2">
                  {networkRequests.length === 0 ? (
                    <div className="text-gray-500 text-center py-8">No network requests</div>
                  ) : (
                    [...networkRequests].reverse().map((request) => (
                      <div key={request.id} className="p-3 bg-gray-800/50 rounded border border-gray-700">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${
                            request.status === 'pending' ? 'bg-yellow-400 animate-pulse' :
                            request.status === 'success' ? 'bg-green-400' :
                            'bg-red-400'
                          }`} />
                          <span className="text-gray-300 truncate flex-1">{request.name}</span>
                          <span className="text-xs text-gray-500">{request.type}</span>
                          <span className="text-gray-500">{formatDuration(request.duration)}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default DebugPanel;
