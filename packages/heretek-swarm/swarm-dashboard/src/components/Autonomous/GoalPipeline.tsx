/**
 * GoalPipeline Component
 *
 * Shows goal lifecycle states from GET /api/autonomous/goals
 * with visual indicators for each phase: proposed, voting, accepted,
 * rejected, completed.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { StatusBadge, StatusType } from '../UI/StatusBadge';
import { LoadingSpinner } from '../UI/LoadingSpinner';
import { EmptyState } from '../UI/EmptyState';
import { getGoalPipeline, GoalSnapshot } from '../../api/autonomous';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTimestamp(ts: string | null): string {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return ts;
  }
}

function mapGoalStatusToBadge(status: string): StatusType {
  switch (status.toLowerCase()) {
    case 'proposed':
      return 'pending';
    case 'voting':
      return 'warning';
    case 'accepted':
      return 'healthy';
    case 'rejected':
      return 'error';
    case 'completed':
      return 'success';
    default:
      return 'inactive';
  }
}

function getGoalStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'proposed':
      return 'border-blue-500/30 bg-blue-500/5';
    case 'voting':
      return 'border-yellow-500/30 bg-yellow-500/5';
    case 'accepted':
      return 'border-green-500/30 bg-green-500/5';
    case 'rejected':
      return 'border-red-500/30 bg-red-500/5';
    case 'completed':
      return 'border-purple-500/30 bg-purple-500/5';
    default:
      return 'border-gray-500/30 bg-gray-500/5';
  }
}

function getGoalStatusLabel(status: string): { label: string; color: string } {
  switch (status.toLowerCase()) {
    case 'proposed':
      return { label: 'Proposed', color: 'text-blue-400' };
    case 'voting':
      return { label: 'Voting', color: 'text-yellow-400' };
    case 'accepted':
      return { label: 'Accepted', color: 'text-green-400' };
    case 'rejected':
      return { label: 'Rejected', color: 'text-red-400' };
    case 'completed':
      return { label: 'Completed', color: 'text-purple-400' };
    default:
      return { label: status, color: 'text-gray-400' };
  }
}

function getPriorityColor(priority: string | null): string {
  switch (priority?.toLowerCase()) {
    case 'high':
    case 'critical':
      return 'text-red-400 border-red-500/30';
    case 'medium':
      return 'text-yellow-400 border-yellow-500/30';
    case 'low':
      return 'text-green-400 border-green-500/30';
    default:
      return 'text-gray-400 border-gray-500/30';
  }
}

// ── Lifecycle step config ────────────────────────────────────────────────────

const LIFECYCLE_STEPS = ['proposed', 'voting', 'accepted', 'completed'];

function getLifecycleStepIndex(status: string): number {
  const idx = LIFECYCLE_STEPS.indexOf(status.toLowerCase());
  return idx >= 0 ? idx : -1;
}

interface GoalPipelineProps {
  className?: string;
}

export function GoalPipeline({ className = '' }: GoalPipelineProps) {
  const [goals, setGoals] = useState<GoalSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const limit = 20;

  const fetchGoals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGoalPipeline({ page, limit });
      setGoals(data.items);
      setTotalPages(data.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load goal pipeline');
      setGoals([]);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchGoals();
  }, [fetchGoals]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <LoadingSpinner size="lg" message="Loading goal pipeline..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-6 text-center">
        <p className="text-red-400 text-sm">{error}</p>
        <button
          onClick={fetchGoals}
          className="mt-3 px-4 py-1.5 bg-red-600/30 hover:bg-red-600/50 text-red-300 rounded-lg text-sm transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (goals.length === 0) {
    return (
      <EmptyState
        icon="🎯"
        title="No Goals in Pipeline"
        description="Goal lifecycle snapshots will appear here when goals are proposed."
        size="md"
      />
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="grid gap-3">
        {goals.map((goal) => {
          const stepIndex = getLifecycleStepIndex(goal.status);
          const statusInfo = getGoalStatusLabel(goal.status);
          const isExpanded = expandedId === goal.goal_id;

          return (
            <div
              key={goal.goal_id}
              className={`rounded-lg border ${getGoalStatusColor(goal.status)} p-4 cursor-pointer transition-colors hover:opacity-90`}
              onClick={() => setExpandedId(isExpanded ? null : goal.goal_id)}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-medium text-white">{goal.title}</h3>
                    {goal.priority && (
                      <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${getPriorityColor(goal.priority)}`}>
                        {goal.priority}
                      </span>
                    )}
                  </div>
                  {goal.description && (
                    <p className="text-xs text-gray-400 line-clamp-2 mt-0.5">{goal.description}</p>
                  )}
                </div>
                <StatusBadge status={mapGoalStatusToBadge(goal.status)} size="sm" />
              </div>

              {/* Lifecycle bar */}
              {stepIndex >= 0 && (
                <div className="flex items-center gap-1 mt-3">
                  {LIFECYCLE_STEPS.map((step, idx) => {
                    const isActive = idx <= stepIndex;
                    const isCurrent = idx === stepIndex;
                    return (
                      <React.Fragment key={step}>
                        <div className="flex items-center gap-1">
                          <div
                            className={`w-2 h-2 rounded-full ${
                              isActive
                                ? isCurrent
                                  ? 'bg-blue-400 ring-2 ring-blue-400/30'
                                  : 'bg-blue-500'
                                : 'bg-gray-600'
                            }`}
                          />
                          <span
                            className={`text-[10px] uppercase tracking-wider ${
                              isActive ? 'text-blue-400' : 'text-gray-600'
                            }`}
                          >
                            {step}
                          </span>
                        </div>
                        {idx < LIFECYCLE_STEPS.length - 1 && (
                          <div
                            className={`flex-1 h-px ${
                              idx < stepIndex ? 'bg-blue-500' : 'bg-gray-700'
                            }`}
                          />
                        )}
                      </React.Fragment>
                    );
                  })}
                </div>
              )}

              {/* Rejected state indicator */}
              {goal.status.toLowerCase() === 'rejected' && goal.outcome && (
                <div className="mt-2 text-xs text-red-400">
                  Outcome: {goal.outcome}
                </div>
              )}

              {/* Expanded details */}
              {isExpanded && (
                <div className="mt-4 pt-3 border-t border-gray-700/50 space-y-2 text-xs">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-gray-500">Goal ID</span>
                      <p className="text-gray-400 font-mono mt-0.5">{goal.goal_id}</p>
                    </div>
                    <div>
                      <span className="text-gray-500">Status</span>
                      <p className={statusInfo.color + ' mt-0.5 font-medium'}>{statusInfo.label}</p>
                    </div>
                    {goal.proposed_by && (
                      <div>
                        <span className="text-gray-500">Proposed By</span>
                        <p className="text-gray-400 mt-0.5">{goal.proposed_by}</p>
                      </div>
                    )}
                    {goal.created_at && (
                      <div>
                        <span className="text-gray-500">Created</span>
                        <p className="text-gray-400 mt-0.5">{formatTimestamp(goal.created_at)}</p>
                      </div>
                    )}
                    {goal.updated_at && (
                      <div>
                        <span className="text-gray-500">Updated</span>
                        <p className="text-gray-400 mt-0.5">{formatTimestamp(goal.updated_at)}</p>
                      </div>
                    )}
                  </div>
                  {(goal.votes_for > 0 || goal.votes_against > 0) && (
                    <div className="flex gap-4">
                      <span className="text-green-400">{goal.votes_for} for</span>
                      <span className="text-red-400">{goal.votes_against} against</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
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

export default GoalPipeline;
