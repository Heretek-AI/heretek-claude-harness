/**
 * MessageList - Message History Display
 *
 * Scrollable message list with bubbles, timestamps, agent icons,
 * and filtering capabilities.
 */

import React, { useRef, useEffect, useMemo, useState } from 'react';

export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageType = 'task' | 'query' | 'consensus' | 'alert' | 'default';

export interface Message {
  id: string;
  role: MessageRole;
  type?: MessageType;
  content: string;
  timestamp: string;
  agentId?: string;
  agentType?: string;
  metadata?: Record<string, unknown>;
}

export interface MessageListProps {
  messages?: Message[];
  onMessageClick?: (message: Message) => void;
  showTimestamps?: boolean;
  showAgentIcons?: boolean;
  showFilter?: boolean;
  autoScroll?: boolean;
  loading?: boolean;
}

const AGENT_ICONS: Record<string, string> = {
  steward: '🎯',
  alpha: '🔬',
  beta: '✅',
  charlie: '⚔️',
  historian: '📚',
  metis: '🧠',
  empath: '💚',
  perceiver: '👁️',
  echo: '🔊',
  explorer: '🧭',
  examiner: '🔍',
  dreamer: '💭',
  coder: '💻',
  sentinel: '🛡️',
  'sentinel-prime': '🚨',
  arbiter: '⚖️',
  coordinator: '🔄',
  nexus: '🔗',
  catalyst: '⚡',
  chronos: '⏰',
  prism: '🌈',
  'habit-forge': '🔨',
  'perceiver-plus': '📊',
};

const MESSAGE_TYPE_COLORS: Record<MessageType, string> = {
  task: 'border-blue-500 bg-blue-950/30',
  query: 'border-purple-500 bg-purple-950/30',
  consensus: 'border-green-500 bg-green-950/30',
  alert: 'border-red-500 bg-red-950/30',
  default: 'border-gray-500 bg-gray-950/30',
};

const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatDate = (timestamp: string): string => {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff} days ago`;
  return date.toLocaleDateString();
};

export function MessageList({
  messages = [],
  onMessageClick,
  showTimestamps = true,
  showAgentIcons = true,
  showFilter = true,
  autoScroll = true,
  loading = false,
}: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [filterRole, setFilterRole] = useState<MessageRole | 'all'>('all');
  const [filterAgent, setFilterAgent] = useState<string | 'all'>('all');
  const [filterType, setFilterType] = useState<MessageType | 'all'>('all');

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, autoScroll]);

  // Get unique agents from messages
  const uniqueAgents = useMemo(() => {
    const agents = new Set<string>();
    messages.forEach(msg => {
      if (msg.agentType) agents.add(msg.agentType);
    });
    return Array.from(agents);
  }, [messages]);

  // Filter messages
  const filteredMessages = useMemo(() => {
    return messages.filter(msg => {
      if (filterRole !== 'all' && msg.role !== filterRole) return false;
      if (filterAgent !== 'all' && msg.agentType !== filterAgent) return false;
      if (filterType !== 'all' && msg.type !== filterType && msg.type !== undefined) return false;
      return true;
    });
  }, [messages, filterRole, filterAgent, filterType]);

  // Group messages by date
  const groupedMessages = useMemo(() => {
    const groups: Record<string, Message[]> = {};
    filteredMessages.forEach(msg => {
      const date = formatDate(msg.timestamp);
      if (!groups[date]) groups[date] = [];
      groups[date].push(msg);
    });
    return groups;
  }, [filteredMessages]);

  const getBubbleStyle = (message: Message) => {
    const baseStyle = 'max-w-[80%] p-3 rounded-lg transition-all hover:shadow-lg';

    if (message.role === 'user') {
      return `${baseStyle} bg-blue-600 text-white ml-auto`;
    }

    if (message.role === 'system') {
      return `${baseStyle} bg-red-900/50 text-red-200 border border-red-700`;
    }

    // Assistant messages with type styling
    const typeStyle = message.type ? MESSAGE_TYPE_COLORS[message.type] : 'bg-gray-700 text-white';
    return `${baseStyle} ${typeStyle}`;
  };

  const clearFilters = () => {
    setFilterRole('all');
    setFilterAgent('all');
    setFilterType('all');
  };

  const hasActiveFilters = filterRole !== 'all' || filterAgent !== 'all' || filterType !== 'all';

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Filter Bar */}
      {showFilter && (
        <div className="flex items-center gap-2 p-3 bg-gray-800 border-b border-gray-700 flex-wrap">
          <span className="text-gray-400 text-sm">Filter:</span>

          {/* Role Filter */}
          <select
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value as MessageRole | 'all')}
            className="bg-gray-700 text-white text-sm rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Roles</option>
            <option value="user">User</option>
            <option value="assistant">Assistant</option>
            <option value="system">System</option>
          </select>

          {/* Agent Filter */}
          {uniqueAgents.length > 0 && (
            <select
              value={filterAgent}
              onChange={(e) => setFilterAgent(e.target.value)}
              className="bg-gray-700 text-white text-sm rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Agents</option>
              {uniqueAgents.map(agent => (
                <option key={agent} value={agent}>{agent}</option>
              ))}
            </select>
          )}

          {/* Type Filter */}
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as MessageType | 'all')}
            className="bg-gray-700 text-white text-sm rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Types</option>
            <option value="task">Task</option>
            <option value="query">Query</option>
            <option value="consensus">Consensus</option>
            <option value="alert">Alert</option>
          </select>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-blue-400 hover:text-blue-300 text-sm underline"
            >
              Clear filters
            </button>
          )}

          <span className="text-gray-500 text-sm ml-auto">
            {filteredMessages.length} / {messages.length} messages
          </span>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {Object.entries(groupedMessages).map(([date, dateMessages]) => (
          <div key={date}>
            {/* Date separator */}
            <div className="flex items-center justify-center my-4">
              <span className="bg-gray-800 text-gray-400 text-xs px-3 py-1 rounded-full">
                {date}
              </span>
            </div>

            {/* Messages for this date */}
            <div className="space-y-3">
              {dateMessages.map((message, index) => {
                const icon = message.agentType
                  ? AGENT_ICONS[message.agentType.toLowerCase()] || '🤖'
                  : message.role === 'user' ? '👤' : '🤖';

                return (
                  <div
                    key={message.id || index}
                    onClick={() => onMessageClick?.(message)}
                    className={`
                      flex gap-3 cursor-pointer transition-all hover:bg-gray-800/50 rounded-lg p-2 -mx-2
                      ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}
                    `}
                  >
                    {/* Agent Icon */}
                    {showAgentIcons && (
                      <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-xl">
                        {icon}
                      </div>
                    )}

                    {/* Message Content */}
                    <div className={getBubbleStyle(message)}>
                      {/* Header with agent info */}
                      <div className={`flex items-center gap-2 mb-1 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        {message.agentType && (
                          <span className="font-semibold text-sm">
                            {message.agentType}
                          </span>
                        )}
                        {message.type && message.role !== 'user' && (
                          <span className="text-xs px-2 py-0.5 rounded bg-black/30 uppercase">
                            {message.type}
                          </span>
                        )}
                        {showTimestamps && (
                          <span className="text-xs opacity-60">
                            {formatTime(message.timestamp)}
                          </span>
                        )}
                      </div>

                      {/* Message text */}
                      <div className="whitespace-pre-wrap break-words">
                        {message.content}
                      </div>

                      {/* Metadata */}
                      {message.metadata && Object.keys(message.metadata).length > 0 && (
                        <div className="mt-2 pt-2 border-t border-white/10 text-xs opacity-60">
                          {Object.entries(message.metadata).map(([key, value]) => (
                            <div key={key}>
                              <span className="font-semibold">{key}:</span> {String(value)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center text-xl">
              🤖
            </div>
            <div className="bg-gray-700 p-3 rounded-lg">
              <div className="flex gap-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {filteredMessages.length === 0 && !loading && (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <div className="text-4xl mb-2">💬</div>
              <div>
                {hasActiveFilters
                  ? 'No messages match the current filters'
                  : 'No messages yet. Start a conversation!'}
              </div>
            </div>
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}

export default MessageList;
