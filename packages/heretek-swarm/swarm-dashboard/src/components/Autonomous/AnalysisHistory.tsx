/**
 * AnalysisHistory Component
 *
 * Displays a scrollable table of autonomous analysis records from
 * GET /api/autonomous/analyses. Each row shows Metis analyses and
 * Empath responses from the analysis record.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner } from '../UI/LoadingSpinner';
import { EmptyState } from '../UI/EmptyState';
import { getAnalysisHistory, AnalysisRecord } from '../../api/autonomous';

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

function getTriggerColor(trigger: string | null): string {
  switch (trigger?.toLowerCase()) {
    case 'scheduled':
      return 'text-blue-400';
    case 'event':
      return 'text-green-400';
    case 'manual':
      return 'text-yellow-400';
    case 'anomaly':
      return 'text-red-400';
    default:
      return 'text-gray-400';
  }
}

interface AnalysisHistoryProps {
  /** Optional class name override */
  className?: string;
}

export function AnalysisHistory({ className = '' }: AnalysisHistoryProps) {
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const limit = 20;

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAnalysisHistory({ page, limit });
      setRecords(data.items);
      setTotalPages(data.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis history');
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <LoadingSpinner size="lg" message="Loading analysis history..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-6 text-center">
        <p className="text-red-400 text-sm">{error}</p>
        <button
          onClick={fetchRecords}
          className="mt-3 px-4 py-1.5 bg-red-600/30 hover:bg-red-600/50 text-red-300 rounded-lg text-sm transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <EmptyState
        icon="📊"
        title="No Analysis Records"
        description="Analysis records from the autonomous loop will appear here when the system processes data."
        size="md"
      />
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-left text-gray-400">
              <th className="pb-2 pr-4 font-medium">Time</th>
              <th className="pb-2 pr-4 font-medium">Trigger</th>
              <th className="pb-2 pr-4 font-medium">Metis</th>
              <th className="pb-2 pr-4 font-medium">Empath</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <React.Fragment key={record.id}>
                <tr
                  className="border-b border-gray-700/50 hover:bg-gray-700/30 cursor-pointer transition-colors"
                  onClick={() => setExpandedId(expandedId === record.id ? null : record.id)}
                >
                  <td className="py-3 pr-4 text-gray-300 whitespace-nowrap font-mono text-xs">
                    {formatTimestamp(record.collected_at)}
                  </td>
                  <td className="py-3 pr-4">
                    <span className={`font-medium capitalize ${getTriggerColor(record.trigger_type)}`}>
                      {record.trigger_type || 'unknown'}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-gray-300">
                    {record.metis_analyses.length > 0 ? (
                      <span className="inline-flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                        {record.metis_analyses.length} analysis
                        {record.metis_analyses.length !== 1 ? 'es' : ''}
                      </span>
                    ) : (
                      <span className="text-gray-500">—</span>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-gray-300">
                    {record.empath_responses.length > 0 ? (
                      <span className="inline-flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-green-500" />
                        {record.empath_responses.length} response
                        {record.empath_responses.length !== 1 ? 's' : ''}
                      </span>
                    ) : (
                      <span className="text-gray-500">—</span>
                    )}
                  </td>
                  <td className="py-3 text-gray-300">
                    {record.chronos_actions.length > 0 ? (
                      <span className="inline-flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-yellow-500" />
                        {record.chronos_actions.length} action
                        {record.chronos_actions.length !== 1 ? 's' : ''}
                      </span>
                    ) : (
                      <span className="text-gray-500">—</span>
                    )}
                  </td>
                </tr>
                {expandedId === record.id && (
                  <tr className="bg-gray-800/50">
                    <td colSpan={5} className="py-4 px-4">
                      <div className="space-y-4 text-sm">
                        <div>
                          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                            Record Details
                          </h4>
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <span className="text-gray-500 text-xs">ID</span>
                              <p className="text-gray-300 font-mono text-xs mt-0.5">{record.id}</p>
                            </div>
                            <div>
                              <span className="text-gray-500 text-xs">Mediation</span>
                              <p className="text-gray-300 mt-0.5">
                                {record.mediation_dispatched ? (
                                  <span className="text-green-400">Dispatched</span>
                                ) : (
                                  <span className="text-gray-500">None</span>
                                )}
                              </p>
                            </div>
                          </div>
                        </div>

                        {record.metis_analyses.length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2">
                              Metis Analyses
                            </h4>
                            {record.metis_analyses.map((ma, idx) => (
                              <div key={idx} className="bg-gray-900/50 rounded p-2 mb-1 text-xs text-gray-400 font-mono">
                                {JSON.stringify(ma).slice(0, 200)}
                                {JSON.stringify(ma).length > 200 ? '...' : ''}
                              </div>
                            ))}
                          </div>
                        )}

                        {record.empath_responses.length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-2">
                              Empath Responses
                            </h4>
                            {record.empath_responses.map((er, idx) => (
                              <div key={idx} className="bg-gray-900/50 rounded p-2 mb-1 text-xs text-gray-400 font-mono">
                                {JSON.stringify(er).slice(0, 200)}
                                {JSON.stringify(er).length > 200 ? '...' : ''}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
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

export default AnalysisHistory;
