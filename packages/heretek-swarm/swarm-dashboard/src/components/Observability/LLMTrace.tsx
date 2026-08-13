/**
 * LLM Trace Component - Display LLM call traces with timeline
 *
 * Shows LLM calls, tool calls, and agent interactions over time.
 * Inspired by RagaAI-Catalyst tracing patterns.
 */

import React, { useEffect, useState } from 'react';

interface LLMTraceEvent {
  id: string;
  type: 'llm_call' | 'tool_call' | 'agent_message';
  timestamp: number;
  duration: number;
  data: {
    agentId?: string;
    model?: string;
    prompt?: string;
    response?: string;
    toolName?: string;
    toolInput?: any;
    toolOutput?: any;
    fromAgent?: string;
    toAgent?: string;
    message?: string;
  };
}

interface LLMTraceProps {
  agentId: string;
  timeRange?: { start: number; end: number };
}

// Use relative path (nginx proxies /api to api:8000)
const API_URL = '';

export function LLMTrace({ agentId, timeRange }: LLMTraceProps) {
  const [events, setEvents] = useState<LLMTraceEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTraces = async () => {
      try {
        const params = new URLSearchParams();
        params.append('agent_id', agentId);
        if (timeRange) {
          params.append('start_time', timeRange.start.toString());
          params.append('end_time', timeRange.end.toString());
        }

        const response = await fetch(`${API_URL}/api/observability/traces?${params}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('api_key') || ''}` },
        });

        if (!response.ok) throw new Error('Failed to fetch traces');

        const data = await response.json();
        setEvents(data.events || []);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchTraces();

    // Poll for updates every 5 seconds
    const interval = setInterval(fetchTraces, 5000);
    return () => clearInterval(interval);
  }, [agentId, timeRange]);

  const getEventColor = (type: string) => {
    switch (type) {
      case 'llm_call': return '#3B82F6'; // blue
      case 'tool_call': return '#22C55E'; // green
      case 'agent_message': return '#8B5CF6'; // purple
      default: return '#6B7280'; // gray
    }
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'llm_call': return '🤖';
      case 'tool_call': return '🔧';
      case 'agent_message': return '💬';
      default: return '📌';
    }
  };

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  const formatDuration = (duration: number) => {
    if (duration < 1000) return `${duration}ms`;
    return `${(duration / 1000).toFixed(2)}s`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-900">
        <div className="text-white text-xl">Loading traces...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-900">
        <div className="text-red-500 text-xl">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 text-white p-4 rounded-lg">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">LLM Trace</h2>
        <div className="text-sm text-gray-400">
          {events.length} events
        </div>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {events.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            No trace events found
          </div>
        ) : (
          events.map((event) => (
            <div
              key={event.id}
              className="flex items-start space-x-3 p-3 bg-gray-800 rounded border-l-2"
              style={{ borderColor: getEventColor(event.type) }}
            >
              <div className="flex-shrink-0 text-2xl">
                {getEventIcon(event.type)}
              </div>

              <div className="flex-grow">
                <div className="flex items-center space-x-2 mb-1">
                  <span className="text-xs font-mono bg-gray-700 px-2 py-1 rounded">
                    {formatTimestamp(event.timestamp)}
                  </span>
                  <span className="text-xs text-gray-400">
                    {formatDuration(event.duration)}
                  </span>
                </div>

                {event.type === 'llm_call' && (
                  <div className="space-y-1">
                    {event.data.model && (
                      <div className="text-xs text-gray-400">
                        Model: {event.data.model}
                      </div>
                    )}
                    {event.data.prompt && (
                      <div className="text-sm bg-gray-900 p-2 rounded">
                        <div className="text-xs text-gray-400 mb-1">Prompt:</div>
                        <div className="text-xs text-gray-300">
                          {event.data.prompt.substring(0, 200)}
                          {event.data.prompt.length > 200 && '...'}
                        </div>
                      </div>
                    )}
                    {event.data.response && (
                      <div className="text-sm bg-gray-900 p-2 rounded">
                        <div className="text-xs text-gray-400 mb-1">Response:</div>
                        <div className="text-xs text-gray-300">
                          {event.data.response.substring(0, 200)}
                          {event.data.response.length > 200 && '...'}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {event.type === 'tool_call' && (
                  <div className="space-y-1">
                    {event.data.toolName && (
                      <div className="text-xs text-gray-400">
                        Tool: {event.data.toolName}
                      </div>
                    )}
                    {event.data.toolInput && (
                      <div className="text-sm bg-gray-900 p-2 rounded">
                        <div className="text-xs text-gray-400 mb-1">Input:</div>
                        <div className="text-xs text-gray-300">
                          {JSON.stringify(event.data.toolInput).substring(0, 200)}
                          {JSON.stringify(event.data.toolInput).length > 200 && '...'}
                        </div>
                      </div>
                    )}
                    {event.data.toolOutput && (
                      <div className="text-sm bg-gray-900 p-2 rounded">
                        <div className="text-xs text-gray-400 mb-1">Output:</div>
                        <div className="text-xs text-gray-300">
                          {JSON.stringify(event.data.toolOutput).substring(0, 200)}
                          {JSON.stringify(event.data.toolOutput).length > 200 && '...'}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {event.type === 'agent_message' && (
                  <div className="space-y-1">
                    {event.data.fromAgent && (
                      <div className="text-xs text-gray-400">
                        From: {event.data.fromAgent}
                      </div>
                    )}
                    {event.data.toAgent && (
                      <div className="text-xs text-gray-400">
                        To: {event.data.toAgent}
                      </div>
                    )}
                    {event.data.message && (
                      <div className="text-sm bg-gray-900 p-2 rounded">
                        <div className="text-xs text-gray-400 mb-1">Message:</div>
                        <div className="text-xs text-gray-300">
                          {event.data.message.substring(0, 200)}
                          {event.data.message.length > 200 && '...'}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default LLMTrace;
