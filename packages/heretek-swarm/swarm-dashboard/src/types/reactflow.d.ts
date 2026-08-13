/**
 * Type definitions for ReactFlow
 *
 * Provides type safety for ReactFlow components
 */

import { Node } from '@xyflow/react';

// =============================================================================
// Custom Node Types
// =============================================================================

export interface AgentNode extends Node {
  data: {
    agentId: string;
    agentType:
      | 'alpha'
      | 'beta'
      | 'charlie'
      | 'steward'
      | 'historian'
      | 'coder'
      | 'dreamer'
      | 'explorer'
      | 'examiner'
      | 'empath'
      | 'metis'
      | 'nexus'
      | 'perceiver'
      | 'sentinel'
      | 'sentinel-prime';
    status: 'idle' | 'thinking' | 'acting' | 'error';
    lastActivity?: string;
  };
}

export interface TriadNode extends Node {
  data: {
    agentId: string;
    role: 'alpha' | 'beta' | 'charlie';
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface HistorianNode extends Node {
  data: {
    agentId: string;
    memories: number;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface ToolNode extends Node {
  data: {
    toolName: string;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface MemoryNode extends Node {
  data: {
    memoryType: 'episodic' | 'semantic' | 'working';
    size: number;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface RAGNode extends Node {
  data: {
    query: string;
    resultCount: number;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface ConditionNode extends Node {
  data: {
    condition: string;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface LoopNode extends Node {
  data: {
    iterations: number;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface HandoffNode extends Node {
  data: {
    toAgentId: string;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface MergeNode extends Node {
  data: {
    mergeType: 'concat' | 'zip' | 'flatten';
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface DiscordNode extends Node {
  data: {
    channelId: string;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface TelegramNode extends Node {
  data: {
    chatId: string;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

export interface WebhookNode extends Node {
  data: {
    url: string;
    status: 'idle' | 'thinking' | 'acting' | 'error';
  };
}

// =============================================================================
// Type Mappings
// =============================================================================

export const NODE_TYPES = {
  agentNode: 'agentNode',
  triadNode: 'triadNode',
  historianNode: 'historianNode',
  toolNode: 'toolNode',
  memoryNode: 'memoryNode',
  ragNode: 'ragNode',
  conditionNode: 'conditionNode',
  loopNode: 'loopNode',
  handoffNode: 'handoffNode',
  mergeNode: 'mergeNode',
  discordNode: 'discordNode',
  telegramNode: 'telegramNode',
  webhookNode: 'webhookNode',
} as const;

export const NODE_COLORS = {
  agent: '#6B7280',
  triad: '#22C55E',
  historian: '#3B82F6',
  tool: '#10B981',
  memory: '#8B5CF6',
  rag: '#F59E0B',
  condition: '#FBBF24',
  loop: '#9CA3AF',
  handoff: '#EC4899',
  merge: '#8B5CF6',
  discord: '#5865F2',
  telegram: '#229ED9',
  webhook: '#6366F1',
} as const;
