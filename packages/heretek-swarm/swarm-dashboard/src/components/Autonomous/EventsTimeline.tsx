/**
 * EventsTimeline Component
 *
 * Renders a chronological timeline from GET /api/autonomous/events
 * showing trigger chronology with typed event markers.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner } from '../UI/LoadingSpinner';
import { EmptyState } from '../UI/EmptyState';
import { getEventsTimeline, TimelineEvent } from '../../api/autonomous';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return ts;
  }
}

interface EventTypeStyle {
  icon: string;
  color: string;
  lineColor: string;
  label: string;
}

const EVENT_STYLES: Record<string, EventTypeStyle> = {
  analysis_completed: {
    icon: '🔬',
    color: 'text-blue-400 border-blue-500/30 bg-blue-500/10',
    lineColor: 'bg-blue-500',
    label: 'Analysis',
  },
  metis_analysis: {
    icon: '🧠',
    color: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
    lineColor: 'bg-purple-500',
    label: 'Metis',
  },
  empath_response: {
    icon: '💚',
    color: 'text-green-400 border-green-500/30 bg-green-500/10',
    lineColor: 'bg-green-500',
    label: 'Empath',
  },
  chronos_action: {
    icon: '⚡',
    color: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10',
    lineColor: 'bg-yellow-500',
    label: 'Chronos',
  },
  mediation_dispatched: {
    icon: '🤝',
    color: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
    lineColor: 'bg-cyan-500',
    label: 'Mediation',
  },
};

function getEventStyle(eventType: string): EventTypeStyle {
  return EVENT_STYLES[eventType] || {
    icon: '📌',
    color: 'text-gray-400 border-gray-500/30 bg-gray-500/10',
    lineColor: 'bg-gray-500',
    label: eventType,
  };
}

interface EventsTimelineProps {
  className?: string;
}

export function EventsTimeline({ className = '' }: EventsTimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const limit = 20;

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getEventsTimeline({ page, limit });
      setEvents(data.items);
      setTotalPages(data.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events timeline');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <LoadingSpinner size="lg" message="Loading events timeline..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-6 text-center">
        <p className="text-red-400 text-sm">{error}</p>
        <button
          onClick={fetchEvents}
          className="mt-3 px-4 py-1.5 bg-red-600/30 hover:bg-red-600/50 text-red-300 rounded-lg text-sm transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <EmptyState
        icon="📅"
        title="No Timeline Events"
        description="Autonomous loop events will appear here as the system processes analysis records."
        size="md"
      />
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="relative">
        {/* Vertical timeline line */}
        <div className="absolute left-[18px] top-0 bottom-0 w-0.5 bg-gray-700" />

        <div className="space-y-0">
          {events.map((event) => {
            const style = getEventStyle(event.event_type);
            const isExpanded = expandedId === event.id;
            const sourceLabel = event.source ? event.source.charAt(0).toUpperCase() + event.source.slice(1) : '';

            return (
              <div key={event.id} className="relative flex gap-4 pb-4 last:pb-0">
                {/* Timeline dot */}
                <div className="relative z-10 flex-shrink-0 mt-1">
                  <div className={`w-9 h-9 rounded-full ${style.color} flex items-center justify-center text-sm border`}>
                    {style.icon}
                  </div>
                </div>

                {/* Event content */}
                <div
                  className={`flex-1 min-w-0 rounded-lg border ${style.color} p-3 cursor-pointer transition-colors hover:opacity-90`}
                  onClick={() => setExpandedId(isExpanded ? null : event.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-semibold uppercase tracking-wider">
                          {style.label}
                        </span>
                        {sourceLabel && (
                          <span className="text-[10px] text-gray-500/80">by {sourceLabel}</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-300 line-clamp-1">
                        {event.summary || 'No summary'}
                      </p>
                    </div>
                    <span className="text-[10px] text-gray-500 whitespace-nowrap font-mono">
                      {formatTimestamp(event.collected_at)}
                    </span>
                  </div>

                  {/* Expanded payload */}
                  {isExpanded && Object.keys(event.payload).length > 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-700/50">
                      <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1">
                        Payload
                      </h4>
                      <pre className="text-[10px] text-gray-400 font-mono bg-gray-900/50 rounded p-2 overflow-x-auto max-h-32">
                        {JSON.stringify(event.payload, null, 2)}
                      </pre>
                    </div>
                  )}

                  {isExpanded && Object.keys(event.payload).length === 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-700/50">
                      <p className="text-[10px] text-gray-500 italic">No additional payload data</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-gray-500">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              ← Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default EventsTimeline;
