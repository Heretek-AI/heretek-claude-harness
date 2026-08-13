/**
 * MessageInput - Message Composition Input
 *
 * Text input with auto-resize, send button, agent selector,
 * message type selector, and keyboard shortcuts.
 */

import React, { useState, useRef, useEffect, KeyboardEvent } from 'react';

export type MessageType = 'task' | 'query' | 'consensus';

export interface AgentOption {
  id: string;
  type: string;
  status?: string;
  icon?: string;
}

export interface MessageInputProps {
  onSendMessage: (content: string, agentId: string, messageType: MessageType) => void;
  agents?: AgentOption[];
  disabled?: boolean;
  placeholder?: string;
  showAgentSelector?: boolean;
  showTypeSelector?: boolean;
  defaultAgentId?: string;
  defaultMessageType?: MessageType;
  minRows?: number;
  maxRows?: number;
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

const MESSAGE_TYPE_OPTIONS: { value: MessageType; label: string; color: string; description: string }[] = [
  { value: 'task', label: 'Task', color: 'bg-blue-600', description: 'Assign a task to execute' },
  { value: 'query', label: 'Query', color: 'bg-purple-600', description: 'Ask a question' },
  { value: 'consensus', label: 'Consensus', color: 'bg-green-600', description: 'Request consensus decision' },
];

export function MessageInput({
  onSendMessage,
  agents = [],
  disabled = false,
  placeholder = 'Type your message...',
  showAgentSelector = true,
  showTypeSelector = true,
  defaultAgentId,
  defaultMessageType = 'query',
  minRows = 2,
  maxRows = 6,
}: MessageInputProps) {
  const [content, setContent] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<string>(defaultAgentId || '');
  const [messageType, setMessageType] = useState<MessageType>(defaultMessageType);
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      const maxHeight = maxRows * 24; // Assuming 24px per line
      const newHeight = Math.min(scrollHeight, maxHeight);
      textareaRef.current.style.height = `${Math.max(newHeight, minRows * 24)}px`;
    }
  }, [content, minRows, maxRows]);

  // Set default agent if not set
  useEffect(() => {
    if (!selectedAgent && agents.length > 0) {
      setSelectedAgent(agents[0].id);
    }
    if (defaultAgentId) {
      setSelectedAgent(defaultAgentId);
    }
  }, [agents, selectedAgent, defaultAgentId]);

  const handleSend = () => {
    if (!content.trim() || disabled) return;
    onSendMessage(content.trim(), selectedAgent, messageType);
    setContent('');
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const selectedAgentData = agents.find(a => a.id === selectedAgent);
  const selectedTypeData = MESSAGE_TYPE_OPTIONS.find(t => t.value === messageType);

  return (
    <div className={`
      bg-gray-800 border-t border-gray-700 p-4
      transition-all duration-200
      ${isFocused ? 'shadow-lg' : ''}
    `}>
      {/* Options Bar */}
      <div className="flex items-center gap-3 mb-3">
        {/* Agent Selector */}
        {showAgentSelector && (
          <div className="flex items-center gap-2">
            <label className="text-gray-400 text-sm font-medium">To:</label>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              disabled={disabled}
              className="bg-gray-700 text-white text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed min-w-[150px]"
            >
              {agents.length === 0 ? (
                <option value="">Select agent...</option>
              ) : (
                agents.map(agent => (
                  <option key={agent.id} value={agent.id}>
                    {AGENT_ICONS[agent.type.toLowerCase()] || '🤖'} {agent.type}
                    {agent.status && ` (${agent.status})`}
                  </option>
                ))
              )}
            </select>

            {/* Selected agent icon badge */}
            {selectedAgentData && (
              <span className="text-2xl" title={selectedAgentData.type}>
                {AGENT_ICONS[selectedAgentData.type.toLowerCase()] || '🤖'}
              </span>
            )}
          </div>
        )}

        {/* Message Type Selector */}
        {showTypeSelector && (
          <div className="flex items-center gap-2">
            <label className="text-gray-400 text-sm font-medium">Type:</label>
            <div className="flex gap-1">
              {MESSAGE_TYPE_OPTIONS.map(type => (
                <button
                  key={type.value}
                  onClick={() => setMessageType(type.value)}
                  disabled={disabled}
                  className={`
                    px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                    ${messageType === type.value
                      ? `${type.color} text-white shadow-md`
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'}
                    disabled:opacity-50 disabled:cursor-not-allowed
                  `}
                  title={type.description}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Type indicator */}
        {selectedTypeData && (
          <div className="ml-auto text-xs text-gray-500">
            {selectedTypeData.description}
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholder}
            disabled={disabled}
            rows={minRows}
            className="
              w-full bg-gray-700 text-white rounded-lg px-4 py-3
              focus:outline-none focus:ring-2 focus:ring-blue-500
              disabled:opacity-50 disabled:cursor-not-allowed
              resize-none overflow-y-auto
              placeholder-gray-500
            "
            style={{
              minHeight: `${minRows * 24}px`,
              maxHeight: `${maxRows * 24}px`,
            }}
          />

          {/* Character count (optional, shows when typing) */}
          {content.length > 0 && (
            <div className="absolute bottom-2 right-3 text-xs text-gray-500">
              {content.length} chars
            </div>
          )}
        </div>

        {/* Send Button */}
        <button
          onClick={handleSend}
          disabled={disabled || !content.trim()}
          className="
            px-6 py-3 bg-blue-600 hover:bg-blue-700
            disabled:bg-gray-600 disabled:cursor-not-allowed
            text-white font-semibold rounded-lg
            transition-all duration-200
            flex items-center gap-2
            hover:shadow-lg hover:scale-105
            disabled:hover:scale-100 disabled:hover:shadow-none
          "
          title="Send message (Enter)"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
          <span className="hidden sm:inline">Send</span>
        </button>
      </div>

      {/* Help text */}
      <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-4">
          <span>Press <kbd className="px-1.5 py-0.5 bg-gray-700 rounded text-gray-400">Enter</kbd> to send</span>
          <span>Press <kbd className="px-1.5 py-0.5 bg-gray-700 rounded text-gray-400">Shift+Enter</kbd> for new line</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${selectedTypeData?.color || 'bg-gray-500'}`} />
          <span>{selectedTypeData?.label || 'Message'}</span>
        </div>
      </div>
    </div>
  );
}

export default MessageInput;
