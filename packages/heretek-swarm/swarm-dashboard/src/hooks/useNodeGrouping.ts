/**
 * Node Grouping Hook
 *
 * Provides functionality for grouping, organizing, and managing
 * collections of nodes in the workflow builder.
 *
 * Features:
 * - Create/delete groups from selected nodes
 * - Named groups with collapsible headers
 * - Auto-layout within groups
 * - Color-coded groups by function
 * - Drag nodes in/out of groups
 * - Group statistics (agent count, total load, average Phi)
 *
 * Inspired by XYFlow node grouping patterns.
 */

import { useCallback, useState } from 'react';
import { Node } from '@xyflow/react';

// ============================================================================
// Types
// ============================================================================

/**
 * Node group structure
 */
export interface NodeGroup {
  id: string;
  name: string;
  color: string;
  nodes: string[]; // Node IDs
  position: { x: number; y: number };
  size: { width: number; height: number };
  collapsed: boolean;
  statistics: {
    agentCount: number;
    totalLoad: number;
    averagePhi: number;
  };
}

/**
 * Group function categories for color coding
 */
export enum GroupFunction {
  PERCEPTION = 'perception',
  DECISION = 'decision',
  ACTION = 'action',
  MEMORY = 'memory',
  COMMUNICATION = 'communication',
  CUSTOM = 'custom',
}

/**
 * Group color scheme
 */
export interface GroupColorScheme {
  background: string;
  border: string;
  header: string;
  text: string;
}

/**
 * Color schemes for different group functions
 */
export const GROUP_COLOR_SCHEMES: Record<GroupFunction, GroupColorScheme> = {
  [GroupFunction.PERCEPTION]: {
    background: 'rgba(59, 130, 246, 0.1)',
    border: '#3b82f6',
    header: '#3b82f6',
    text: '#1e40af',
  },
  [GroupFunction.DECISION]: {
    background: 'rgba(168, 85, 247, 0.1)',
    border: '#a855f7',
    header: '#a855f7',
    text: '#6b21a8',
  },
  [GroupFunction.ACTION]: {
    background: 'rgba(34, 197, 94, 0.1)',
    border: '#22c55e',
    header: '#22c55e',
    text: '#166534',
  },
  [GroupFunction.MEMORY]: {
    background: 'rgba(245, 158, 11, 0.1)',
    border: '#f59e0b',
    header: '#f59e0b',
    text: '#92400e',
  },
  [GroupFunction.COMMUNICATION]: {
    background: 'rgba(236, 72, 153, 0.1)',
    border: '#ec4899',
    header: '#ec4899',
    text: '#9d174d',
  },
  [GroupFunction.CUSTOM]: {
    background: 'rgba(107, 114, 128, 0.1)',
    border: '#6b7280',
    header: '#6b7280',
    text: '#374151',
  },
};

/**
 * Hook options
 */
export interface UseNodeGroupingOptions {
  /** Default group width */
  defaultGroupWidth?: number;
  /** Default group height */
  defaultGroupHeight?: number;
  /** Padding around grouped nodes */
  groupPadding?: number;
}

/**
 * Hook state and operations
 */
export interface UseNodeGroupingReturn {
  /** All groups */
  groups: NodeGroup[];
  /** Create a new group from selected nodes */
  createGroup: (nodeIds: string[], name: string, func?: GroupFunction) => NodeGroup | null;
  /** Delete a group */
  deleteGroup: (groupId: string) => void;
  /** Update group properties */
  updateGroup: (groupId: string, updates: Partial<NodeGroup>) => void;
  /** Toggle group collapsed state */
  toggleGroup: (groupId: string) => void;
  /** Add node to group */
  addNodeToGroup: (groupId: string, nodeId: string) => void;
  /** Remove node from group */
  removeNodeFromGroup: (groupId: string, nodeId: string) => void;
  /** Get group by ID */
  getGroup: (groupId: string) => NodeGroup | undefined;
  /** Get group containing a node */
  getGroupForNode: (nodeId: string) => NodeGroup | undefined;
  /** Calculate bounds for nodes */
  calculateGroupBounds: (
    nodeIds: string[],
    nodes: Node[],
  ) => {
    position: { x: number; y: number };
    size: { width: number; height: number };
  };
  /** Check if node is in any group */
  isNodeGrouped: (nodeId: string) => boolean;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Generate a unique group ID
 *
 * Uses crypto.getRandomValues for better randomness than Math.random().
 * This is NOT security-critical - group IDs are for UI organization only.
 */
function generateGroupId(): string {
  const array = new Uint8Array(9);
  crypto.getRandomValues(array);
  return `group-${Date.now()}-${Array.from(array, (b) => b.toString(36).padStart(2, '0'))
    .join('')
    .slice(0, 9)}`;
}

/**
 * Calculate bounds for a set of nodes
 */
function calculateBounds(
  nodeIds: string[],
  nodes: Node[],
  padding: number = 40,
): { position: { x: number; y: number }; size: { width: number; height: number } } {
  const groupNodes = nodes.filter((n) => nodeIds.includes(n.id));

  if (groupNodes.length === 0) {
    return {
      position: { x: 0, y: 0 },
      size: { width: 0, height: 0 },
    };
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const node of groupNodes) {
    const x = node.position.x;
    const y = node.position.y;
    // Assume standard node dimensions if not available
    const width = (node.width as number) || 200;
    const height = (node.height as number) || 100;

    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + width);
    maxY = Math.max(maxY, y + height);
  }

  return {
    position: {
      x: minX - padding,
      y: minY - padding,
    },
    size: {
      width: maxX - minX + padding * 2,
      height: maxY - minY + padding * 2,
    },
  };
}

/**
 * Calculate group statistics from nodes
 */
export function calculateGroupStatistics(
  nodeIds: string[],
  nodes: Node[],
): {
  agentCount: number;
  totalLoad: number;
  averagePhi: number;
} {
  const groupNodes = nodes.filter((n) => nodeIds.includes(n.id));

  let agentCount = 0;
  let totalLoad = 0;
  let totalPhi = 0;
  let phiCount = 0;

  for (const node of groupNodes) {
    const data = node.data as Record<string, any>;

    // Count agents
    if (node.type === 'agent' || data?.agentType) {
      agentCount++;
    }

    // Sum load
    if (data?.load !== undefined) {
      totalLoad += data.load;
    }

    // Sum Phi
    if (data?.phi !== undefined) {
      totalPhi += data.phi;
      phiCount++;
    }
  }

  return {
    agentCount,
    totalLoad,
    averagePhi: phiCount > 0 ? totalPhi / phiCount : 0,
  };
}

// ============================================================================
// Main Hook
// ============================================================================

/**
 * Hook for managing node groups
 *
 * @param options - Configuration options
 * @returns Group management functions and state
 *
 * @example
 * ```typescript
 * const {
 *   groups,
 *   createGroup,
 *   deleteGroup,
 *   addNodeToGroup,
 *   removeNodeFromGroup,
 * } = useNodeGrouping({
 *   groupPadding: 40,
 * });
 * ```
 */
export function useNodeGrouping(options: UseNodeGroupingOptions = {}): UseNodeGroupingReturn {
  const { defaultGroupWidth = 400, defaultGroupHeight = 300, groupPadding = 40 } = options;

  // State
  const [groups, setGroups] = useState<NodeGroup[]>([]);

  /**
   * Create a new group from selected nodes
   */
  const createGroup = useCallback(
    (
      nodeIds: string[],
      name: string,
      func: GroupFunction = GroupFunction.CUSTOM,
    ): NodeGroup | null => {
      if (nodeIds.length === 0) {
        return null;
      }

      // Check if any node is already in a group
      const alreadyGrouped = nodeIds.some((nodeId) => groups.some((g) => g.nodes.includes(nodeId)));

      if (alreadyGrouped) {
        console.warn('Cannot create group: some nodes are already in a group');
        return null;
      }

      const groupId = generateGroupId();
      const color = GROUP_COLOR_SCHEMES[func].border;

      // Create group (bounds will be calculated when nodes are available)
      const newGroup: NodeGroup = {
        id: groupId,
        name,
        color,
        nodes: [...nodeIds],
        position: { x: 0, y: 0 },
        size: { width: defaultGroupWidth, height: defaultGroupHeight },
        collapsed: false,
        statistics: {
          agentCount: 0,
          totalLoad: 0,
          averagePhi: 0,
        },
      };

      setGroups((prev) => [...prev, newGroup]);

      return newGroup;
    },
    [groups, defaultGroupWidth, defaultGroupHeight],
  );

  /**
   * Delete a group
   */
  const deleteGroup = useCallback((groupId: string) => {
    setGroups((prev) => prev.filter((g) => g.id !== groupId));
  }, []);

  /**
   * Update group properties
   */
  const updateGroup = useCallback((groupId: string, updates: Partial<NodeGroup>) => {
    setGroups((prev) => prev.map((g) => (g.id === groupId ? { ...g, ...updates } : g)));
  }, []);

  /**
   * Toggle group collapsed state
   */
  const toggleGroup = useCallback((groupId: string) => {
    setGroups((prev) =>
      prev.map((g) => (g.id === groupId ? { ...g, collapsed: !g.collapsed } : g)),
    );
  }, []);

  /**
   * Add node to group
   */
  const addNodeToGroup = useCallback((groupId: string, nodeId: string) => {
    setGroups((prev) =>
      prev.map((g) => {
        if (g.id !== groupId) return g;

        // Check if node is already in another group
        const inOtherGroup = prev.some(
          (other) => other.id !== groupId && other.nodes.includes(nodeId),
        );

        if (inOtherGroup) {
          console.warn('Node is already in another group');
          return g;
        }

        // Check if node is already in this group
        if (g.nodes.includes(nodeId)) {
          return g;
        }

        return {
          ...g,
          nodes: [...g.nodes, nodeId],
        };
      }),
    );
  }, []);

  /**
   * Remove node from group
   */
  const removeNodeFromGroup = useCallback((groupId: string, nodeId: string) => {
    setGroups(
      (prev) =>
        prev
          .map((g) => {
            if (g.id !== groupId) return g;
            return {
              ...g,
              nodes: g.nodes.filter((id) => id !== nodeId),
            };
          })
          .filter((g) => g.nodes.length > 0), // Remove empty groups
    );
  }, []);

  /**
   * Get group by ID
   */
  const getGroup = useCallback(
    (groupId: string): NodeGroup | undefined => {
      return groups.find((g) => g.id === groupId);
    },
    [groups],
  );

  /**
   * Get group containing a node
   */
  const getGroupForNode = useCallback(
    (nodeId: string): NodeGroup | undefined => {
      return groups.find((g) => g.nodes.includes(nodeId));
    },
    [groups],
  );

  /**
   * Calculate group bounds
   */
  const calculateGroupBounds = useCallback(
    (nodeIds: string[], nodes: Node[]) => {
      return calculateBounds(nodeIds, nodes, groupPadding);
    },
    [groupPadding],
  );

  /**
   * Check if node is in any group
   */
  const isNodeGrouped = useCallback(
    (nodeId: string): boolean => {
      return groups.some((g) => g.nodes.includes(nodeId));
    },
    [groups],
  );

  return {
    groups,
    createGroup,
    deleteGroup,
    updateGroup,
    toggleGroup,
    addNodeToGroup,
    removeNodeFromGroup,
    getGroup,
    getGroupForNode,
    calculateGroupBounds,
    isNodeGrouped,
  };
}

export default useNodeGrouping;
