/**
 * NodePalette - Drag-and-Drop Node Palette
 *
 * Provides draggable items for each agent type organized by tier.
 * Supports search and filter functionality.
 */

import React, { useState, useMemo } from 'react';

export interface AgentType {
  id: string;
  name: string;
  tier: number;
  icon: string;
  description: string;
}

export interface NodePaletteProps {
  onDragStart?: (agentType: string) => void;
  searchPlaceholder?: string;
  showTierHeaders?: boolean;
}

// All 23 agents organized by tier
const AGENT_TYPES: AgentType[] = [
  // Tier 1: Core Triad
  { id: 'steward', name: 'Steward', tier: 1, icon: '🎯', description: 'Governance & orchestration' },
  { id: 'alpha', name: 'Alpha', tier: 1, icon: '🔬', description: 'Deep analysis' },
  { id: 'beta', name: 'Beta', tier: 1, icon: '✅', description: 'Validation' },
  { id: 'charlie', name: 'Charlie', tier: 1, icon: '⚔️', description: 'Challenge agent' },

  // Tier 2: Support Agents
  { id: 'historian', name: 'Historian', tier: 2, icon: '📚', description: 'Memory management' },
  { id: 'metis', name: 'Metis', tier: 2, icon: '🧠', description: 'Strategic planning' },
  { id: 'empath', name: 'Empath', tier: 2, icon: '💚', description: 'Emotional intelligence' },
  { id: 'perceiver', name: 'Perceiver', tier: 2, icon: '👁️', description: 'Multi-modal processing' },
  { id: 'echo', name: 'Echo', tier: 2, icon: '🔊', description: 'Communication' },

  // Tier 3: Exploration Agents
  { id: 'explorer', name: 'Explorer', tier: 3, icon: '🧭', description: 'Intelligence gathering' },
  { id: 'examiner', name: 'Examiner', tier: 3, icon: '🔍', description: 'Quality assurance' },
  { id: 'dreamer', name: 'Dreamer', tier: 3, icon: '💭', description: 'Creative solutions' },
  { id: 'coder', name: 'Coder', tier: 3, icon: '💻', description: 'Code generation' },

  // Tier 4: Safety & Security
  { id: 'sentinel', name: 'Sentinel', tier: 4, icon: '🛡️', description: 'Safety validation' },
  { id: 'sentinel-prime', name: 'Sentinel Prime', tier: 4, icon: '🚨', description: 'Threat response' },
  { id: 'arbiter', name: 'Arbiter', tier: 4, icon: '⚖️', description: 'Conflict resolution' },

  // Tier 5: Coordination Agents
  { id: 'coordinator', name: 'Coordinator', tier: 5, icon: '🔄', description: 'Task synchronization' },
  { id: 'nexus', name: 'Nexus', tier: 5, icon: '🔗', description: 'API integration' },
  { id: 'catalyst', name: 'Catalyst', tier: 5, icon: '⚡', description: 'Change management' },
  { id: 'chronos', name: 'Chronos', tier: 5, icon: '⏰', description: 'Scheduling' },

  // Tier 6: Enhancement Agents
  { id: 'prism', name: 'Prism', tier: 6, icon: '🌈', description: 'Multi-perspective analysis' },
  { id: 'habit-forge', name: 'Habit Forge', tier: 6, icon: '🔨', description: 'Behavior optimization' },
  { id: 'perceiver-plus', name: 'Perceiver+', tier: 6, icon: '📊', description: 'Advanced analytics' },
];

const tierNames: Record<number, string> = {
  1: 'Core Triad',
  2: 'Support Agents',
  3: 'Exploration Agents',
  4: 'Safety & Security',
  5: 'Coordination Agents',
  6: 'Enhancement Agents',
};

const tierColors: Record<number, string> = {
  1: 'border-red-500 bg-red-950/30',
  2: 'border-blue-500 bg-blue-950/30',
  3: 'border-green-500 bg-green-950/30',
  4: 'border-purple-500 bg-purple-950/30',
  5: 'border-yellow-500 bg-yellow-950/30',
  6: 'border-pink-500 bg-pink-950/30',
};

export function NodePalette({
  onDragStart,
  searchPlaceholder = 'Search agents...',
  showTierHeaders = true,
}: NodePaletteProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTier, setSelectedTier] = useState<number | null>(null);

  const filteredAgents = useMemo(() => {
    return AGENT_TYPES.filter((agent) => {
      const matchesSearch =
        agent.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        agent.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        agent.id.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesTier = selectedTier === null || agent.tier === selectedTier;

      return matchesSearch && matchesTier;
    });
  }, [searchTerm, selectedTier]);

  const agentsByTier = useMemo(() => {
    const grouped: Record<number, AgentType[]> = {};
    filteredAgents.forEach((agent) => {
      if (!grouped[agent.tier]) {
        grouped[agent.tier] = [];
      }
      grouped[agent.tier].push(agent);
    });
    return grouped;
  }, [filteredAgents]);

  const handleDragStart = (e: React.DragEvent, agentId: string) => {
    e.dataTransfer.setData('application/reactflow', agentId);
    e.dataTransfer.effectAllowed = 'move';
    onDragStart?.(agentId);
  };

  return (
    <div className="w-72 bg-gray-800 border-r border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-white font-bold text-lg mb-3 flex items-center gap-2">
          <span>🧩</span> Node Palette
        </h2>

        {/* Search */}
        <input
          type="text"
          placeholder={searchPlaceholder}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3"
        />

        {/* Tier Filter */}
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => setSelectedTier(null)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              selectedTier === null
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
            }`}
          >
            All
          </button>
          {Object.entries(tierNames).map(([tier, name]) => (
            <button
              key={tier}
              onClick={() => setSelectedTier(Number(tier))}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                selectedTier === Number(tier)
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
              title={name}
            >
              T{tier}
            </button>
          ))}
        </div>
      </div>

      {/* Agent List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {Object.entries(agentsByTier).map(([tier, agents]) => (
          <div key={tier}>
            {showTierHeaders && (
              <h3 className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-2">
                {tierNames[Number(tier)]}
              </h3>
            )}

            <div className="space-y-2">
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, agent.id)}
                  className={`
                    flex items-center gap-3 p-3 rounded-lg border-l-4 cursor-grab active:cursor-grabbing
                    transition-all hover:scale-105 hover:shadow-lg
                    ${tierColors[agent.tier]}
                    border-gray-700 hover:border-gray-500
                  `}
                  title={agent.description}
                >
                  <span className="text-2xl">{agent.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-white font-semibold text-sm truncate">
                      {agent.name}
                    </div>
                    <div className="text-gray-500 text-xs truncate">
                      {agent.description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        {filteredAgents.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            <div className="text-4xl mb-2">🔍</div>
            <div className="text-sm">No agents found</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default NodePalette;
