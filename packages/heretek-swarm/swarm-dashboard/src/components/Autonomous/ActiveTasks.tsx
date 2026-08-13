/**
 * ActiveTasks Component
 *
 * Renders a task list from GET /api/autonomous/tasks with status badges
 * showing Chronos task state (pending, running, completed, failed).
 */

import React, { useState, useEffect, useCallback } from 'react';
import { StatusBadge } from '../UI/StatusBadge';
import { LoadingSpinner } from '../UI/LoadingSpinner';
import { EmptyState } from '../UI/EmptyState';
import { getActiveTasks, TaskSnapshot } from '../../api/autonomous';

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

function mapTaskStatusToBadge(status: string): string {
  switch (status.toLowerCase()) {
    case 'pending':
      return 'pending';
    case 'running':
    case 'in_progress':
      return 'starting';
    case 'completed':
    case 'success':
      return 'success';
    case 'failed':
    case 'error':
      return 'error';
    case 'cancelled':
      return 'inactive';
    default:
      return 'pending';
  }
}

function getPriorityColor(priority: string | null): string {
  switch (priority?.toLowerCase()) {
    case 'high':
    case 'critical':
      return 'text-red-400';
    case 'medium':
      return 'text-yellow-400';
    case 'low':
      return 'text-green-400';
    default:
      return 'text-gray-400';
  }
}

interface ActiveTasksProps {
  className?: string;
}

export function ActiveTasks({ className = '' }: ActiveTasksProps) {
  const [tasks, setTasks] = useState<TaskSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const limit = 20;

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getActiveTasks({ page, limit });
      setTasks(data.items);
      setTotalPages(data.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load active tasks');
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <LoadingSpinner size="lg" message="Loading active tasks..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-6 text-center">
        <p className="text-red-400 text-sm">{error}</p>
        <button
          onClick={fetchTasks}
          className="mt-3 px-4 py-1.5 bg-red-600/30 hover:bg-red-600/50 text-red-300 rounded-lg text-sm transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <EmptyState
        icon="📋"
        title="No Active Tasks"
        description="Chronos task snapshots will appear here when the autonomous runtime schedules tasks."
        size="md"
      />
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="grid gap-3">
        {tasks.map((task) => (
          <div
            key={task.task_id}
            className="bg-gray-800/30 border border-gray-700/50 rounded-lg p-4 hover:border-gray-600 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-sm font-medium text-white truncate">{task.title}</h3>
                  {task.priority && (
                    <span className={`text-xs font-semibold uppercase ${getPriorityColor(task.priority)}`}>
                      {task.priority}
                    </span>
                  )}
                </div>
                {task.description && (
                  <p className="text-xs text-gray-400 line-clamp-2 mt-0.5">{task.description}</p>
                )}
              </div>
              <StatusBadge status={mapTaskStatusToBadge(task.status)} size="sm" />
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-xs text-gray-500">
              {task.task_id && (
                <span className="font-mono" title={task.task_id}>
                  ID: {task.task_id.slice(0, 8)}...
                </span>
              )}
              {task.assigned_to && <span>Assigned: {task.assigned_to}</span>}
              {task.scheduled_at && <span>Scheduled: {formatTimestamp(task.scheduled_at)}</span>}
              {task.created_at && <span>Created: {formatTimestamp(task.created_at)}</span>}
              {task.tags.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {task.tags.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="px-1.5 py-0.5 bg-gray-700/50 rounded text-xs text-gray-400"
                    >
                      {tag}
                    </span>
                  ))}
                  {task.tags.length > 3 && (
                    <span className="text-gray-500">+{task.tags.length - 3}</span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
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

export default ActiveTasks;
