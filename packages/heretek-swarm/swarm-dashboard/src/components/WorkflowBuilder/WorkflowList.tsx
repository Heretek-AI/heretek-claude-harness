/**
 * WorkflowList - Sidebar panel for browsing, loading, and deleting saved workflows.
 *
 * Fetches workflows from GET /api/workflows and renders a list with
 * load, delete, and re-execute actions. Toggled from the WorkflowBuilder toolbar.
 */

import React, { useState, useEffect, useCallback } from 'react';

interface WorkflowItem {
  id: string;
  name: string;
  created_at: string;
  state: string;
  node_count?: number;
}

interface WorkflowListProps {
  isOpen: boolean;
  onClose: () => void;
  onLoad: (workflowId: string) => void;
  onReExecute: (workflowId: string) => void;
  onRefresh: () => void;
}

const API_URL =
  import.meta.env.VITE_API_HOST ||
  localStorage.getItem('swarm_api_host') ||
  '';

/** Auth-aware fetch wrapper */
async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const apiKey = localStorage.getItem('api_key');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> || {}),
  };
  if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;
  return fetch(url, { ...init, headers });
}

export function WorkflowList({
  isOpen,
  onClose,
  onLoad,
  onReExecute,
  onRefresh,
}: WorkflowListProps) {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  /** Fetch workflows from backend */
  const fetchWorkflows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await authFetch(`${API_URL}/api/workflows`);
      if (!response.ok) throw new Error(`Failed to fetch workflows (${response.status})`);
      const data = await response.json();
      setWorkflows(data.workflows || []);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      console.error('Failed to fetch workflows:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  /** Fetch when panel opens */
  useEffect(() => {
    if (isOpen) fetchWorkflows();
  }, [isOpen, fetchWorkflows]);

  /** Delete a workflow */
  const handleDelete = useCallback(
    async (workflowId: string) => {
      if (!window.confirm('Delete this workflow?')) return;
      setDeletingId(workflowId);
      try {
        const response = await authFetch(`${API_URL}/api/workflows/${workflowId}`, {
          method: 'DELETE',
        });
        if (!response.ok) throw new Error('Failed to delete workflow');
        setWorkflows((prev) => prev.filter((w) => w.id !== workflowId));
        onRefresh();
      } catch (err) {
        console.error('Failed to delete workflow:', err);
      } finally {
        setDeletingId(null);
      }
    },
    [onRefresh],
  );

  /** Format date for display */
  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="workflow-list-panel"
      style={{
        width: 320,
        background: 'white',
        borderLeft: '1px solid #e5e7eb',
        overflowY: 'auto',
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0, fontSize: 18, color: '#1f2937' }}>Saved Workflows</h2>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 20,
            cursor: 'pointer',
            color: '#6b7280',
            padding: '0 4px',
          }}
          aria-label="Close workflow list"
        >
          ×
        </button>
      </div>

      {/* Refresh */}
      <button
        onClick={fetchWorkflows}
        disabled={loading}
        style={{
          padding: '6px 12px',
          background: '#e5e7eb',
          border: 'none',
          borderRadius: 6,
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: 13,
          fontWeight: 600,
          color: '#374151',
        }}
      >
        {loading ? 'Loading…' : '↻ Refresh'}
      </button>

      {/* Error */}
      {error && (
        <div
          style={{
            background: '#fee2e2',
            border: '1px solid #fecaca',
            borderRadius: 6,
            padding: 10,
            color: '#991b1b',
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && workflows.length === 0 && (
        <div
          style={{
            textAlign: 'center',
            color: '#9ca3af',
            padding: '24px 0',
            fontSize: 14,
          }}
        >
          No saved workflows yet.
          <br />
          Build a workflow and save it to see it here.
        </div>
      )}

      {/* Workflow cards */}
      {workflows.map((wf) => (
        <div
          key={wf.id}
          style={{
            border: '1px solid #e5e7eb',
            borderRadius: 8,
            padding: 12,
            background: '#f9fafb',
            transition: 'border-color 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#3b82f6')}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#e5e7eb')}
        >
          {/* Name & state */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontWeight: 600, fontSize: 14, color: '#1f2937', wordBreak: 'break-word' }}>
              {wf.name || 'Untitled Workflow'}
            </span>
            <span
              style={{
                fontSize: 11,
                padding: '2px 6px',
                borderRadius: 4,
                background: '#dbeafe',
                color: '#1e40af',
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {wf.state}
            </span>
          </div>

          {/* Metadata */}
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 8 }}>
            {wf.node_count !== undefined && <span>Nodes: {wf.node_count} · </span>}
            Created: {formatDate(wf.created_at)}
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => onLoad(wf.id)}
              style={{
                flex: 1,
                padding: '6px 0',
                background: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Load
            </button>
            <button
              onClick={() => onReExecute(wf.id)}
              style={{
                flex: 1,
                padding: '6px 0',
                background: '#10b981',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Re-execute
            </button>
            <button
              onClick={() => handleDelete(wf.id)}
              disabled={deletingId === wf.id}
              style={{
                padding: '6px 10px',
                background: '#ef4444',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                fontSize: 12,
                fontWeight: 600,
                cursor: deletingId === wf.id ? 'not-allowed' : 'pointer',
                opacity: deletingId === wf.id ? 0.6 : 1,
              }}
            >
              {deletingId === wf.id ? '…' : 'Delete'}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
