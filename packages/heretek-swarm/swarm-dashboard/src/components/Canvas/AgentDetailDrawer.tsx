/**
 * AgentDetailDrawer - Slide-in detail panel for agent inspection
 *
 * Slides in from the right when an agent is selected. Displays four tabs:
 * - Consciousness: phi score, FEP metrics, consciousness state badge, agency metrics
 * - Memory: total memory count, breakdown by type (episodic, semantic, procedural,
 *   working, declarative, reflection), recent memory entries with content previews
 * - Tools/MCP: skills and plugins lists with names, categories, authors, and descriptions
 * - Tasks: agent status badge, message/error counts, capabilities tags, uptime,
 *   last activity timestamp
 *
 * Data refreshes via polling every 10s while open (via useAgentDetail hook).
 * Gracefully degrades: individual sections show "unavailable" when their endpoint fails,
 * without crashing the drawer.
 */

import { useState } from 'react';
import { useAgentDetail } from './useAgentDetail';
import { useConsciousnessWebSocket } from '../../hooks/useConsciousnessWebSocket';
import type {
  AgentMemoryResponse,
  AgentToolsResponse,
  AgentTasksResponse,
} from '../../api/agents';

interface AgentDetailDrawerProps {
  /** The selected agent ID. Pass null to hide the drawer. */
  agentId: string | null;
  /** Called when the user clicks the close button. */
  onClose: () => void;
}

// ----------------------------------------------------------------------------
// Tab definitions
// ----------------------------------------------------------------------------
type TabId = 'consciousness' | 'memory' | 'tools' | 'tasks';

const TABS: { id: TabId; label: string }[] = [
  { id: 'consciousness', label: 'Consciousness' },
  { id: 'memory', label: 'Memory' },
  { id: 'tools', label: 'Tools/MCP' },
  { id: 'tasks', label: 'Tasks' },
];

// ----------------------------------------------------------------------------
// Status badge helpers
// ----------------------------------------------------------------------------
function getStatusDotColor(status: string): string {
  switch (status) {
    case 'idle':    return 'bg-gray-500';
    case 'thinking':return 'bg-blue-500';
    case 'acting':  return 'bg-green-500';
    case 'error':   return 'bg-red-500';
    case 'offline': return 'bg-gray-600';
    default:        return 'bg-gray-500';
  }
}

function getConsciousnessStateColor(state: string): string {
  switch (state) {
    case 'transcendent': return 'bg-purple-900 text-purple-300 border-purple-600';
    case 'coherent':     return 'bg-green-900 text-green-300 border-green-600';
    case 'emerging':     return 'bg-blue-900 text-blue-300 border-blue-600';
    case 'dormant':      return 'bg-gray-800 text-gray-400 border-gray-600';
    default:            return 'bg-gray-800 text-gray-400 border-gray-600';
  }
}

function getTaskStatusColor(status: string): string {
  switch (status) {
    case 'active':     return 'bg-green-900 text-green-300 border-green-600';
    case 'running':    return 'bg-green-900 text-green-300 border-green-600';
    case 'not_running':return 'bg-gray-800 text-gray-400 border-gray-600';
    case 'error':      return 'bg-red-900 text-red-300 border-red-600';
    case 'stopped':    return 'bg-yellow-900 text-yellow-300 border-yellow-600';
    default:           return 'bg-gray-800 text-gray-400 border-gray-600';
  }
}

function getMemoryTypeColor(type: string): string {
  const colors: Record<string, string> = {
    episodic:    'bg-blue-900 text-blue-300',
    semantic:    'bg-purple-900 text-purple-300',
    procedural:  'bg-green-900 text-green-300',
    working:     'bg-yellow-900 text-yellow-300',
    declarative: 'bg-cyan-900 text-cyan-300',
    reflection:  'bg-indigo-900 text-indigo-300',
  };
  return colors[type] ?? 'bg-gray-700 text-gray-300';
}

function relativeTime(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatUptime(seconds: number | null): string {
  if (seconds == null) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0 && m > 0) return `${h} hours, ${m} minutes`;
  if (h > 0) return `${h} hours`;
  return `${m} minutes`;
}

// ----------------------------------------------------------------------------
// Skeleton placeholder (loading state)
// ----------------------------------------------------------------------------
function SkeletonBar({ className = 'h-4 w-full' }: { className?: string }) {
  return <div className={`bg-gray-700 rounded animate-pulse ${className}`} />;
}

// ----------------------------------------------------------------------------
// Tab content components
// ----------------------------------------------------------------------------

interface ConsciousnessTabContentProps {
  /** consciousness.metrics: null = no metrics yet (404); undefined = not yet loaded */
  consciousness: import('../../api/consciousness').AgentMetrics | null;
  agency: import('../../api/consciousness').AgencyMetrics | null;
  loading: boolean;
  error?: string;
  /** WebSocket-supplied consciousness state (optional, takes precedence over REST) */
  wsState?: import('../../hooks/useConsciousnessWebSocket').ConsciousnessAgentState;
}

function ConsciousnessTabContent({
  consciousness,
  agency,
  loading,
  error,
  wsState,
}: ConsciousnessTabContentProps) {
  // Merge WebSocket state with REST polling state (WS takes precedence)
  const phi_score = wsState?.phi_score ?? consciousness?.phi_score ?? null;
  const state_str = wsState?.state ?? consciousness?.state ?? null;
  const free_energy =
    wsState?.free_energy ?? consciousness?.fep_metrics?.free_energy ?? null;
  const prediction_accuracy =
    wsState?.prediction_accuracy ?? consciousness?.fep_metrics?.prediction_accuracy ?? null;
  const surprise = wsState?.surprise ?? consciousness?.fep_metrics?.surprise ?? null;
  const belief_precision =
    wsState?.belief_precision ?? consciousness?.fep_metrics?.belief_precision ?? null;
  const agency_score = wsState?.agency_score ?? agency?.agency_score ?? null;
  const autonomy_score = wsState?.autonomy_score ?? agency?.autonomy_score ?? null;

  // Error state — show error message inline (not a crash)
  if (error && consciousness == null) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 text-sm">Metrics unavailable</p>
        <p className="text-gray-600 text-xs mt-1">{error}</p>
      </div>
    );
  }

  // Loading with no prior data (initial state: consciousness = null, loading = true)
  if (loading && consciousness == null) {
    return (
      <div className="space-y-3 px-1">
        <SkeletonBar className="h-12 w-full" />
        <SkeletonBar className="h-4 w-3/4" />
        <SkeletonBar className="h-4 w-2/3" />
        <SkeletonBar className="h-4 w-4/5" />
        <SkeletonBar className="h-4 w-1/2" />
      </div>
    );
  }

  // null = no metrics yet recorded (404 from backend); treat same as initial "no data" state
  if (consciousness == null) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 text-sm">No metrics available for this agent yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 px-1">
      {/* Phi score — large hero number */}
      <div className="text-center py-2">
        <div className="text-5xl font-bold text-white">
          {phi_score != null ? phi_score.toFixed(3) : '—'}
        </div>
        <div className="text-gray-400 text-sm mt-1">Φ Score</div>
      </div>

      {/* State badge */}
      <div className="flex justify-center">
        <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getConsciousnessStateColor(state_str ?? 'dormant')}`}>
          {state_str ? state_str.charAt(0).toUpperCase() + state_str.slice(1) : '—'}
        </span>
      </div>

      {/* FEP Metrics */}
      <div>
        <h4 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
          FEP Metrics
        </h4>
        <div className="bg-gray-800 rounded-lg p-3 space-y-2">
          <div className="flex justify-between">
            <span className="text-gray-400 text-sm">Free Energy</span>
            <span className="text-white font-mono text-sm">
              {free_energy != null ? free_energy.toFixed(4) : '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400 text-sm">Prediction Accuracy</span>
            <span className="text-white font-mono text-sm">
              {prediction_accuracy != null ? prediction_accuracy.toFixed(4) : '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400 text-sm">Surprise</span>
            <span className="text-white font-mono text-sm">
              {surprise != null ? surprise.toFixed(4) : '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400 text-sm">Belief Precision</span>
            <span className="text-white font-mono text-sm">
              {belief_precision != null ? belief_precision.toFixed(4) : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Agency metrics */}
      {agency && (
        <div>
          <h4 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
            Agency
          </h4>
          <div className="bg-gray-800 rounded-lg p-3 space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400 text-sm">Agency Score</span>
              <span className="text-white font-mono text-sm">
                {agency_score != null ? agency_score.toFixed(4) : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400 text-sm">Autonomy Score</span>
              <span className="text-white font-mono text-sm">
                {autonomy_score != null ? autonomy_score.toFixed(4) : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400 text-sm">Decision Count</span>
              <span className="text-white font-mono text-sm">{agency.decision_count}</span>
            </div>
            {agency.last_decision && (
              <div className="flex justify-between">
                <span className="text-gray-400 text-sm">Last Decision</span>
                <span className="text-gray-300 text-xs font-mono">
                  {new Date(agency.last_decision).toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Last updated */}
      <div className="text-center">
        <span className="text-gray-600 text-xs">
          {wsState?.last_updated
            ? `WS ${new Date(wsState.last_updated).toLocaleTimeString()}`
            : consciousness?.timestamp
              ? `REST ${new Date(consciousness.timestamp).toLocaleTimeString()}`
              : '—'}
        </span>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Memory tab
// ----------------------------------------------------------------------------
function MemoryTabContent({
  memory,
  loading,
  error,
}: {
  memory: AgentMemoryResponse | null;
  loading: boolean;
  error?: string;
}) {
  if (error && memory == null) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 text-sm">Memory unavailable</p>
        <p className="text-gray-600 text-xs mt-1">{error}</p>
      </div>
    );
  }

  if (loading && memory == null) {
    return (
      <div className="space-y-3 px-1">
        <SkeletonBar className="h-12 w-full" />
        <SkeletonBar className="h-4 w-3/4" />
        <SkeletonBar className="h-4 w-2/3" />
        <SkeletonBar className="h-4 w-4/5" />
        <SkeletonBar className="h-4 w-1/2" />
      </div>
    );
  }

  if (memory == null) return null;

  if (memory.status === 'unavailable') {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 text-sm">Memory backend not available</p>
      </div>
    );
  }

  const { total_memories, by_type, recent_entries } = memory;

  if (total_memories === 0 && !Object.keys(by_type ?? {}).length) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 text-sm">No memories recorded</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 px-1">
      {/* Hero number */}
      <div className="text-center py-2">
        <div className="text-5xl font-bold text-white">{total_memories}</div>
        <div className="text-gray-400 text-sm mt-1">
          {total_memories === 1 ? 'memory' : 'memories'}
        </div>
      </div>

      {/* By type */}
      {by_type && Object.keys(by_type).length > 0 && (
        <div>
          <h4 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
            By Type
          </h4>
          <div className="bg-gray-800 rounded-lg p-3 space-y-1.5">
            {Object.entries(by_type).map(([type, count]) => (
              <div key={type} className="flex justify-between items-center">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${getMemoryTypeColor(type)}`}>
                  {type}
                </span>
                <span className="text-white font-mono text-sm">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent entries */}
      {recent_entries && recent_entries.length > 0 && (
        <div>
          <h4 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
            Recent
          </h4>
          <div className="bg-gray-800 rounded-lg divide-y divide-gray-700 max-h-64 overflow-y-auto">
            {recent_entries.slice(0, 10).map((entry) => (
              <div key={entry.id} className="p-2.5">
                <p className="text-gray-200 text-xs leading-relaxed truncate" title={entry.content}>
                  {entry.content.length > 80
                    ? entry.content.slice(0, 80) + '...'
                    : entry.content}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${getMemoryTypeColor(entry.memory_type)}`}>
                    {entry.memory_type}
                  </span>
                  <span className="text-gray-600 text-[10px]">
                    {relativeTime(entry.created_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Tools tab
// ----------------------------------------------------------------------------
function ToolsTabContent({
  tools,
  loading,
  error,
}: {
  tools: AgentToolsResponse | null;
  loading: boolean;
  error?: string;
}) {
  if (error && tools == null) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 text-sm">Tools unavailable</p>
        <p className="text-gray-600 text-xs mt-1">{error}</p>
      </div>
    );
  }

  if (loading && tools == null) {
    return (
      <div className="space-y-3 px-1">
        <SkeletonBar className="h-12 w-full" />
        <SkeletonBar className="h-4 w-3/4" />
        <SkeletonBar className="h-4 w-2/3" />
        <SkeletonBar className="h-4 w-4/5" />
      </div>
    );
  }

  if (tools == null) return null;

  const { skills, plugins } = tools;

  return (
    <div className="space-y-4 px-1">
      {/* Header */}
      <div className="text-center py-2">
        <div className="text-2xl font-bold text-white">
          {skills.length} skills, {plugins.length} plugins
        </div>
      </div>

      {/* Skills section */}
      {skills.length > 0 && (
        <div>
          <h4 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
            Skills
          </h4>
          <div className="bg-gray-800 rounded-lg divide-y divide-gray-700 max-h-64 overflow-y-auto">
            {skills.map((skill, idx) => (
              <div key={`${skill.name}-${idx}`} className="p-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-white text-sm font-semibold">{skill.name}</span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-900 text-blue-300">
                    {skill.category}
                  </span>
                </div>
                {skill.description && (
                  <p className="text-gray-400 text-xs mt-1">{skill.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Plugins section */}
      {plugins.length > 0 && (
        <div>
          <h4 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
            Plugins
          </h4>
          <div className="bg-gray-800 rounded-lg divide-y divide-gray-700 max-h-64 overflow-y-auto">
            {plugins.map((plugin, idx) => (
              <div key={`${plugin.name}-${idx}`} className="p-2.5">
                <span className="text-white text-sm font-semibold">{plugin.name}</span>
                <div className="flex items-center gap-2 mt-0.5">
                  {plugin.author && (
                    <span className="text-gray-500 text-xs">{plugin.author}</span>
                  )}
                </div>
                {plugin.description && (
                  <p className="text-gray-400 text-xs mt-1">{plugin.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Both empty */}
      {skills.length === 0 && plugins.length === 0 && (
        <div className="text-center py-8">
          <p className="text-gray-500 text-sm">No skills or plugins configured</p>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Tasks tab
// ----------------------------------------------------------------------------
function TasksTabContent({
  tasks,
  loading,
  error,
}: {
  tasks: AgentTasksResponse | null;
  loading: boolean;
  error?: string;
}) {
  if (error && tasks == null) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 text-sm">Tasks unavailable</p>
        <p className="text-gray-600 text-xs mt-1">{error}</p>
      </div>
    );
  }

  if (loading && tasks == null) {
    return (
      <div className="space-y-3 px-1">
        <SkeletonBar className="h-12 w-full" />
        <SkeletonBar className="h-4 w-3/4" />
        <SkeletonBar className="h-4 w-2/3" />
        <SkeletonBar className="h-4 w-4/5" />
      </div>
    );
  }

  if (tasks == null) return null;

  const {
    status,
    capabilities,
    message_count,
    error_count,
    last_activity,
    uptime_seconds,
  } = tasks;

  const isRunning = status === 'active' || status === 'running';

  return (
    <div className="space-y-4 px-1">
      {/* Status badge */}
      <div className="flex justify-center">
        <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getTaskStatusColor(status)}`}>
          {status === 'not_running' ? 'Not Running' : status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
      </div>

      {!isRunning && (
        <div className="text-center">
          <p className="text-gray-500 text-sm">Agent is not currently running</p>
        </div>
      )}

      {/* Stat boxes */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-white">{message_count}</div>
          <div className="text-gray-400 text-xs mt-0.5">Messages</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-red-400">{error_count}</div>
          <div className="text-gray-400 text-xs mt-0.5">Errors</div>
        </div>
      </div>

      {/* Capabilities */}
      {capabilities && capabilities.length > 0 && (
        <div>
          <h4 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
            Capabilities
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {capabilities.map((cap) => (
              <span
                key={cap}
                className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-900 text-blue-300"
              >
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Uptime */}
      <div className="flex justify-between items-center bg-gray-800 rounded-lg p-3">
        <span className="text-gray-400 text-sm">Uptime</span>
        <span className="text-white font-mono text-sm">{formatUptime(uptime_seconds)}</span>
      </div>

      {/* Last activity */}
      <div className="flex justify-between items-center bg-gray-800 rounded-lg p-3">
        <span className="text-gray-400 text-sm">Last Activity</span>
        <span className="text-gray-300 text-sm">{relativeTime(last_activity)}</span>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Main drawer component
// ----------------------------------------------------------------------------
export function AgentDetailDrawer({ agentId, onClose }: AgentDetailDrawerProps) {
  const [activeTab, setActiveTab] = useState<TabId>('consciousness');

  // agentId null = drawer not rendered
  const { data, loading, errors } = useAgentDetail(agentId);

  // WebSocket for live consciousness metrics (supplementary to polling)
  const { agentStates: wsStates, connected: wsConnected } = useConsciousnessWebSocket();

  return (
    <div
      // Slide in from right: start off-screen, slide in when rendered
      className="absolute top-0 right-0 h-full w-96 bg-gray-900 border-l border-gray-700 shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out"
      style={{ transform: 'translateX(0)' }}
    >
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <div className="flex items-center gap-3 min-w-0">
          {/* Agent type icon */}
          <span className="text-2xl flex-shrink-0">
            {data?.agent ? getAgentIcon(data.agent.type) : '🤖'}
          </span>
          <div className="min-w-0">
            <h2 className="text-white font-semibold text-sm truncate">
              {data?.agent?.type ?? agentId ?? 'Agent'}
            </h2>
            {data?.agent && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusDotColor(data.agent.status)}`} />
                <span className="text-gray-400 text-xs capitalize">{data.agent.status}</span>
              </div>
            )}
          </div>
        </div>
        {/* Close button */}
        <button
          onClick={onClose}
          aria-label="Close agent detail drawer"
          className="flex-shrink-0 text-gray-400 hover:text-white p-1 rounded transition-colors"
        >
          ✕
        </button>
      </div>

      {/* ── Tab bar ────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-b border-gray-700">
        <nav className="flex" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-2.5 text-xs font-medium text-center transition-colors relative ${
                activeTab === tab.id
                  ? 'text-blue-400'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab.label}
              {activeTab === tab.id && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500" />
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Tab content ────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-4" role="tabpanel">
        {activeTab === 'consciousness' && (
          <ConsciousnessTabContent
            consciousness={data?.consciousness ?? null}
            agency={data?.agency ?? null}
            loading={loading}
            error={errors.consciousness}
            wsState={agentId ? wsStates.get(agentId) : undefined}
          />
        )}
        {activeTab === 'memory' && (
          <MemoryTabContent
            memory={data?.memory ?? null}
            loading={loading}
            error={errors.memory}
          />
        )}
        {activeTab === 'tools' && (
          <ToolsTabContent
            tools={data?.tools ?? null}
            loading={loading}
            error={errors.tools}
          />
        )}
        {activeTab === 'tasks' && (
          <TasksTabContent
            tasks={data?.tasks ?? null}
            loading={loading}
            error={errors.tasks}
          />
        )}
      </div>

      {/* ── Footer: polling / WebSocket indicator ─────────────────── */}
      {agentId !== null && (
        <div className="flex-shrink-0 px-4 py-2 border-t border-gray-800 flex items-center gap-2">
          {wsConnected ? (
            <>
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-gray-600 text-xs">Live (WS)</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-gray-500" />
              <span className="text-gray-600 text-xs">Polling every 10s</span>
            </>
          )}
          {loading && data && (
            <span className="ml-auto text-gray-600 text-xs">Refreshing…</span>
          )}
        </div>
      )}
    </div>
  );
}

// Small icon lookup (mirrors AgentNode.tsx)
function getAgentIcon(agentType: string): string {
  const icons: Record<string, string> = {
    steward: '🎯',
    alpha: '🔬',
    beta: '✅',
    charlie: '🎭',
    historian: '📚',
    metis: '🧠',
    empath: '💝',
    perceiver: '👁️',
    default: '🤖',
  };
  return icons[agentType?.toLowerCase()] ?? icons.default;
}

export default AgentDetailDrawer;
