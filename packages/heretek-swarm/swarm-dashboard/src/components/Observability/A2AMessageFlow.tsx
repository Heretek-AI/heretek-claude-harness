/**
 * A2A Message Flow Component - Visualize agent-to-agent communication
 *
 * Shows message flow between agents in the system.
 * Inspired by RagaAI-Catalyst agent interaction patterns.
 */

import React, { useState, useEffect } from 'react';

interface A2AMessage {
  id: string;
  from_agent: string;
  to_agent: string;
  content: string;
  timestamp: string;
  type: string;
}

interface A2AMessageFlowProps {
  agentId: string;
  timeRange?: { start: number; end: number };
}

// Use relative path (nginx proxies /api to api:8000)
const API_URL = '';

export function A2AMessageFlow({ agentId, timeRange }: A2AMessageFlowProps) {
  const [messages, setMessages] = useState<A2AMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMessages = async () => {
      try {
        const params = new URLSearchParams();
        params.append('agent_id', agentId);
        if (timeRange) {
          params.append('start_time', timeRange.start.toString());
          params.append('end_time', timeRange.end.toString());
        }

        const response = await fetch(`${API_URL}/api/observability/a2a_messages?${params}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('api_key') || ''}` },
        });

        if (!response.ok) throw new Error('Failed to fetch A2A messages');

        const data = await response.json();
        setMessages(data.messages || []);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();

    // Poll for updates every 5 seconds
    const interval = setInterval(fetchMessages, 5000);
    return () => clearInterval(interval);
  }, [agentId, timeRange]);

  const getMessageColor = (type: string) => {
    switch (type) {
      case 'request': return '#3B82F6'; // blue
      case 'response': return '#22C55E'; // green
      case 'handoff': return '#F59E0B'; // orange
      case 'error': return '#EF4444'; // red
      default: return '#6B7280'; // gray
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-900">
        <div className="text-white text-xl">Loading messages...</div>
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
        <h2 className="text-xl font-bold">A2A Message Flow</h2>
        <div className="text-sm text-gray-400">
          {messages.length} messages
        </div>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            No A2A messages found
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className="flex items-start space-x-3 p-3 bg-gray-800 rounded border-l-2"
              style={{ borderColor: getMessageColor(message.type) }}
            >
              <div className="flex-shrink-0 w-24 text-center">
                <div className="text-xs text-gray-400 mb-1">
                  {formatTimestamp(message.timestamp)}
                </div>
                <div className="text-2xl">
                  {message.type === 'request' ? '→' : message.type === 'response' ? '←' : '↔'}
                </div>
              </div>

              <div className="flex-grow">
                <div className="flex items-center space-x-2 mb-1">
                  <span className="text-sm font-semibold text-gray-300">
                    {message.from_agent}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatTimestamp(message.timestamp)}
                  </span>
                </div>

                <div className="space-y-1">
                  <div className="text-xs text-gray-400">
                    Type: {message.type}
                  </div>
                  <div className="text-sm bg-gray-900 p-2 rounded">
                    {message.content.substring(0, 200)}
                    {message.content.length > 200 && '...'}
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <span className="text-sm font-semibold text-gray-300">
                    {message.to_agent}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatTimestamp(message.timestamp)}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default A2AMessageFlow;
