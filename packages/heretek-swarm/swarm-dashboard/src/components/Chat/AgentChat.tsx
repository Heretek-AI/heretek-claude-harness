/**
 * AgentChat - Vercel AI SDK chat surface for the swarm.
 *
 * Streams LLM output from the backend's /api/chat/stream endpoint
 * using `useChat` + `TextStreamChatTransport`. The endpoint delegates
 * to `ModelGarage.stream` (pydantic-ai transport) so the chat uses
 * the same LLM path as the rest of the swarm — no separate transport.
 *
 * The transport is configured with `prepareSendMessagesRequest` to map
 * the Vercel AI SDK's { messages, id } body shape onto the backend's
 * flat { messages, model, temperature, max_tokens } schema.
 */

import { useChat } from '@ai-sdk/react';
import { TextStreamChatTransport } from 'ai';
import { useMemo, useState } from 'react';

const API_HOST =
  (import.meta.env.VITE_API_HOST as string | undefined) ||
  (typeof localStorage !== 'undefined'
    ? localStorage.getItem('swarm_api_host') || ''
    : '');

export interface AgentChatProps {
  model?: string;
  providerId?: string;
  temperature?: number;
  maxTokens?: number;
}

export function AgentChat(props: AgentChatProps) {
  const { model, providerId, temperature = 0.7, maxTokens } = props;

  const [input, setInput] = useState('');

  const transport = useMemo(
    () =>
      new TextStreamChatTransport({
        api: `${API_HOST}/api/chat/stream`,
        prepareSendMessagesRequest: ({ messages }) => {
          return {
            body: {
              messages: messages.map((m) => ({
                role: m.role,
                content: m.parts
                  .filter(
                    (p): p is { type: 'text'; text: string } =>
                      p.type === 'text',
                  )
                  .map((p) => p.text)
                  .join(''),
              })),
              ...(model ? { model } : {}),
              ...(providerId ? { provider_id: providerId } : {}),
              temperature,
              ...(maxTokens ? { max_tokens: maxTokens } : {}),
            },
          };
        },
      }),
    [model, providerId, temperature, maxTokens],
  );

  const { messages, sendMessage, status, error, stop } = useChat({ transport });

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        padding: '1rem',
        border: '1px solid #ddd',
        borderRadius: '8px',
        maxWidth: '720px',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
          minHeight: '240px',
          maxHeight: '480px',
          overflowY: 'auto',
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: '#888' }}>Send a message to start a chat with the swarm.</p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              background: m.role === 'user' ? '#1e6fdb' : '#f0f0f0',
              color: m.role === 'user' ? '#fff' : '#222',
              padding: '0.5rem 0.75rem',
              borderRadius: '12px',
              maxWidth: '80%',
              whiteSpace: 'pre-wrap',
            }}
          >
            <strong style={{ fontSize: '0.75rem', opacity: 0.8 }}>
              {m.role}
            </strong>
            <div>
              {m.parts
                .filter((p) => p.type === 'text')
                .map((p, i) => (
                  <span key={i}>{p.text}</span>
                ))}
            </div>
          </div>
        ))}
        {status === 'streaming' && (
          <button onClick={() => stop()} style={{ alignSelf: 'flex-start' }}>
            Stop
          </button>
        )}
        {error && <p style={{ color: 'crimson' }}>Error: {error.message}</p>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!input.trim()) return;
          void sendMessage({ text: input });
          setInput('');
        }}
        style={{ display: 'flex', gap: '0.5rem' }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the swarm…"
          disabled={status === 'submitted' || status === 'streaming'}
          style={{ flex: 1, padding: '0.5rem' }}
        />
        <button
          type="submit"
          disabled={
            status === 'submitted' || status === 'streaming' || !input.trim()
          }
        >
          {status === 'submitted' || status === 'streaming' ? 'Sending…' : 'Send'}
        </button>
      </form>
    </div>
  );
}

export default AgentChat;
