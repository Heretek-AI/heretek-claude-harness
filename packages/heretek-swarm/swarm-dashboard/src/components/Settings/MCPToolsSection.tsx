/**
 * MCP Tools Section
 *
 * Displays all registered MCP tools in a table with name, description,
 * category, enabled/disabled badge, and toggle switch.
 *
 * Toggle calls PUT /mcp/tools/toggle/{name} and shows immediate visual
 * feedback with rollback on API failure. All state comes from the API —
 * no localStorage for tool state.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useToast } from '../UI/Toast';
import { mcpToolsApi, MCPToolSummary } from '../../api/mcp';

// =============================================================================
// Sub-components
// =============================================================================

/** Toggle switch with immediate visual feedback and rollback on failure */
function ToolToggle({
  toolName,
  enabled,
  onToggle,
  disabled,
}: {
  toolName: string;
  enabled: boolean;
  onToggle: (name: string, newEnabled: boolean) => Promise<void>;
  disabled: boolean;
}) {
  const [pending, setPending] = useState(false);

  const handleChange = async () => {
    if (pending || disabled) return;
    setPending(true);
    try {
      await onToggle(toolName, !enabled);
    } finally {
      setPending(false);
    }
  };

  return (
    <button
      onClick={handleChange}
      disabled={pending || disabled}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900
        disabled:opacity-50 disabled:cursor-not-allowed
        ${enabled ? 'bg-blue-600' : 'bg-gray-600'}
      `}
      aria-label={`Toggle ${toolName} ${enabled ? 'off' : 'on'}`}
      role="switch"
      aria-checked={enabled}
    >
      <span
        className={`
          inline-block h-4 w-4 rounded-full bg-white transition-transform
          ${enabled ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
    </button>
  );
}

/** Status badge: green for enabled, gray for disabled */
function StatusBadge({ enabled }: { enabled: boolean }) {
  return (
    <span
      className={`
        inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
        ${enabled
          ? 'bg-green-500/20 text-green-400 border border-green-500/30'
          : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
        }
      `}
    >
      {enabled ? 'Enabled' : 'Disabled'}
    </span>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function MCPToolsSection() {
  const [tools, setTools] = useState<MCPToolSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingAll, setTogglingAll] = useState(false);
  const toast = useToast();

  const fetchTools = useCallback(async () => {
    try {
      setError(null);
      const response = await mcpToolsApi.listTools();
      setTools(response.tools);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to fetch MCP tools';
      setError(message);
      toast.error('Failed to load MCP tools', message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  /**
   * Toggle a single tool. Uses optimistic update: immediately flips the local
   * state, calls the API, then reverts on failure.
   */
  const handleToggle = useCallback(
    async (toolName: string, newEnabled: boolean) => {
      // Optimistic update
      setTools((prev) =>
        prev.map((t) =>
          t.name === toolName ? { ...t, enabled: newEnabled } : t
        )
      );

      try {
        await mcpToolsApi.toggleTool(toolName, newEnabled);
        toast.success(
          `Tool ${newEnabled ? 'enabled' : 'disabled'}`,
          `${toolName} is now ${newEnabled ? 'available' : 'unavailable'} to agents`
        );
        // Refetch to confirm server state
        await fetchTools();
      } catch (err: unknown) {
        // Rollback optimistic update
        setTools((prev) =>
          prev.map((t) =>
            t.name === toolName ? { ...t, enabled: !newEnabled } : t
          )
        );
        const message = err instanceof Error ? err.message : 'Toggle failed';
        toast.error('Toggle failed', `Could not ${newEnabled ? 'enable' : 'disable'} ${toolName}: ${message}`);
      }
    },
    [toast, fetchTools]
  );

  /** Bulk toggle: enable or disable all tools */
  const handleToggleAll = useCallback(
    async (enableAll: boolean) => {
      setTogglingAll(true);
      const targets = tools.filter((t) => t.enabled !== enableAll);
      let succeeded = 0;
      let failed = 0;

      for (const tool of targets) {
        try {
          await mcpToolsApi.toggleTool(tool.name, enableAll);
          succeeded++;
        } catch {
          failed++;
        }
      }

      if (failed > 0) {
        toast.warning(
          'Partial update',
          `${succeeded} tools updated, ${failed} failed`
        );
      } else {
        toast.success(
          'Bulk update complete',
          `All ${succeeded} tools ${enableAll ? 'enabled' : 'disabled'}`
        );
      }

      await fetchTools();
      setTogglingAll(false);
    },
    [tools, toast, fetchTools]
  );

  // Get unique categories for filter
  const categories = [...new Set(tools.map((t) => t.category))].sort();

  // ===========================================================================
  // Render: Loading state
  // ===========================================================================
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">MCP Tools</h2>
            <p className="text-sm text-gray-400 mt-1">
              Manage which MCP tools are available to agents
            </p>
          </div>
        </div>
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          <span className="ml-3 text-gray-400">Loading tools...</span>
        </div>
      </div>
    );
  }

  // ===========================================================================
  // Render: Error state
  // ===========================================================================
  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">MCP Tools</h2>
            <p className="text-sm text-gray-400 mt-1">
              Manage which MCP tools are available to agents
            </p>
          </div>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={() => {
              setLoading(true);
              fetchTools();
            }}
            className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 border border-red-500/50 text-red-400 rounded-lg text-sm font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ===========================================================================
  // Render: Empty state
  // ===========================================================================
  if (tools.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">MCP Tools</h2>
            <p className="text-sm text-gray-400 mt-1">
              Manage which MCP tools are available to agents
            </p>
          </div>
        </div>
        <div className="bg-gray-900/50 border border-gray-700 rounded-xl p-8 text-center">
          <span className="text-4xl mb-4 block">🔧</span>
          <p className="text-gray-400 text-sm">No MCP tools registered</p>
          <p className="text-gray-500 text-xs mt-1">
            Tools will appear here once MCP servers are configured
          </p>
        </div>
      </div>
    );
  }

  // ===========================================================================
  // Render: Populated state
  // ===========================================================================
  const enabledCount = tools.filter((t) => t.enabled).length;
  const disabledCount = tools.length - enabledCount;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">MCP Tools</h2>
          <p className="text-sm text-gray-400 mt-1">
            Manage which MCP tools are available to agents
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">
            {enabledCount} enabled · {disabledCount} disabled
          </span>
          <button
            onClick={() => handleToggleAll(true)}
            disabled={togglingAll || enabledCount === tools.length}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-medium transition-colors"
          >
            Enable All
          </button>
          <button
            onClick={() => handleToggleAll(false)}
            disabled={togglingAll || disabledCount === tools.length}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-medium transition-colors"
          >
            Disable All
          </button>
        </div>
      </div>

      {/* Category summary */}
      {categories.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {categories.map((cat) => {
            const count = tools.filter((t) => t.category === cat).length;
            return (
              <span
                key={cat}
                className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-gray-800 text-gray-300 border border-gray-700"
              >
                {cat} ({count})
              </span>
            );
          })}
        </div>
      )}

      {/* Tools table */}
      <div className="bg-gray-900/50 border border-gray-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700 bg-gray-800/50">
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Description
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Category
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Toggle
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {tools.map((tool) => (
                <tr
                  key={tool.name}
                  className={`
                    transition-colors
                    ${tool.enabled
                      ? 'hover:bg-gray-800/50'
                      : 'opacity-60 hover:bg-gray-800/30'
                    }
                  `}
                >
                  <td className="px-4 py-3">
                    <span className={`text-sm font-mono ${tool.enabled ? 'text-white' : 'text-gray-500'}`}>
                      {tool.name}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-sm ${tool.enabled ? 'text-gray-300' : 'text-gray-500'}`}>
                      {tool.description || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`
                      inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
                      ${tool.enabled
                        ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                        : 'bg-gray-700/50 text-gray-500 border border-gray-600/50'
                      }
                    `}>
                      {tool.category}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge enabled={tool.enabled} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ToolToggle
                      toolName={tool.name}
                      enabled={tool.enabled}
                      onToggle={handleToggle}
                      disabled={togglingAll}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Info box */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <span className="text-blue-400 text-lg">ℹ️</span>
          <div>
            <h4 className="text-sm font-medium text-blue-400 mb-1">
              MCP Tool Management
            </h4>
            <p className="text-xs text-gray-400">
              Disabled tools will not appear in agent tool schemas and cannot be invoked by the LLM.
              Changes persist across daemon restarts via tools_state.json.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MCPToolsSection;
