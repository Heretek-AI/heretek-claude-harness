/**
 * Node Grouping Hook Tests
 *
 * Tests for useNodeGrouping hook covering:
 * - Group creation and deletion
 * - Adding/removing nodes from groups
 * - Group statistics calculation
 * - Node grouping state management
 */

import { renderHook, act } from '@testing-library/react';
import { useNodeGrouping, GroupFunction, NodeGroup } from '../useNodeGrouping';
import { vi } from 'vitest';

// reactflow imports fail in jsdom without this mock
vi.mock('reactflow', () => ({
  Node: () => null,
}));

describe('useNodeGrouping', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should initialize with empty groups', () => {
    const { result } = renderHook(() => useNodeGrouping());

    expect(result.current.groups).toEqual([]);
  });

  it('should create a group from selected nodes', () => {
    const { result } = renderHook(() => useNodeGrouping());

    let createdGroup: NodeGroup | null = null;
    act(() => {
      createdGroup = result.current.createGroup(['node1', 'node2'], 'Test Group');
    });

    expect(createdGroup).not.toBeNull();
    expect(createdGroup?.name).toBe('Test Group');
    expect(createdGroup?.nodes).toEqual(['node1', 'node2']);
    expect(result.current.groups).toHaveLength(1);
  });

  it('should create a group with specified function type', () => {
    const { result } = renderHook(() => useNodeGrouping());

    act(() => {
      result.current.createGroup(['node1'], 'Perception Group', GroupFunction.PERCEPTION);
    });

    expect(result.current.groups[0].color).toBe('#3b82f6'); // Perception blue
  });

  it('should prevent creating group with already grouped nodes', () => {
    const { result } = renderHook(() => useNodeGrouping());

    act(() => {
      result.current.createGroup(['node1', 'node2'], 'Group 1');
    });

    let createdGroup: NodeGroup | null = null;
    act(() => {
      createdGroup = result.current.createGroup(['node2', 'node3'], 'Group 2');
    });

    expect(createdGroup).toBeNull();
    expect(result.current.groups).toHaveLength(1);
  });

  it('should delete a group', () => {
    const { result } = renderHook(() => useNodeGrouping());

    let createdGroup: NodeGroup | null = null;
    act(() => {
      createdGroup = result.current.createGroup(['node1'], 'Test Group');
    });

    act(() => {
      result.current.deleteGroup(createdGroup!.id);
    });

    expect(result.current.groups).toHaveLength(0);
  });

  it('should update group properties', () => {
    const { result } = renderHook(() => useNodeGrouping());

    let createdGroup: NodeGroup | null = null;
    act(() => {
      createdGroup = result.current.createGroup(['node1'], 'Test Group');
    });

    act(() => {
      result.current.updateGroup(createdGroup!.id, { name: 'Updated Name' });
    });

    expect(result.current.groups[0].name).toBe('Updated Name');
  });

  it('should toggle group collapsed state', () => {
    const { result } = renderHook(() => useNodeGrouping());

    let createdGroup: NodeGroup | null = null;
    act(() => {
      createdGroup = result.current.createGroup(['node1'], 'Test Group');
    });

    expect(createdGroup?.collapsed).toBe(false);

    act(() => {
      result.current.toggleGroup(createdGroup!.id);
    });

    expect(result.current.groups[0].collapsed).toBe(true);
  });

  it('should add node to group', () => {
    const { result } = renderHook(() => useNodeGrouping());

    act(() => {
      result.current.createGroup(['node1'], 'Test Group');
    });

    act(() => {
      result.current.addNodeToGroup(result.current.groups[0].id, 'node2');
    });

    expect(result.current.groups[0].nodes).toEqual(['node1', 'node2']);
  });

  it('should remove node from group', () => {
    const { result } = renderHook(() => useNodeGrouping());

    act(() => {
      result.current.createGroup(['node1', 'node2'], 'Test Group');
    });

    act(() => {
      result.current.removeNodeFromGroup(result.current.groups[0].id, 'node1');
    });

    expect(result.current.groups[0].nodes).toEqual(['node2']);
  });

  it('should remove empty groups when last node is removed', () => {
    const { result } = renderHook(() => useNodeGrouping());

    act(() => {
      result.current.createGroup(['node1'], 'Test Group');
    });

    act(() => {
      result.current.removeNodeFromGroup(result.current.groups[0].id, 'node1');
    });

    expect(result.current.groups).toHaveLength(0);
  });

  it('should get group by ID', () => {
    const { result } = renderHook(() => useNodeGrouping());

    act(() => {
      result.current.createGroup(['node1'], 'Test Group');
    });

    const group = result.current.getGroup(result.current.groups[0].id);
    expect(group?.name).toBe('Test Group');
  });

  it('should get group containing a node', () => {
    const { result } = renderHook(() => useNodeGrouping());

    act(() => {
      result.current.createGroup(['node1', 'node2'], 'Test Group');
    });

    const group = result.current.getGroupForNode('node1');
    expect(group?.name).toBe('Test Group');

    const noGroup = result.current.getGroupForNode('node3');
    expect(noGroup).toBeUndefined();
  });

  it('should check if node is grouped', () => {
    const { result } = renderHook(() => useNodeGrouping());

    act(() => {
      result.current.createGroup(['node1'], 'Test Group');
    });

    expect(result.current.isNodeGrouped('node1')).toBe(true);
    expect(result.current.isNodeGrouped('node2')).toBe(false);
  });

  it('should calculate group bounds from nodes', () => {
    const { result } = renderHook(() => useNodeGrouping());

    const mockNodes: Node[] = [
      {
        id: 'node1',
        type: 'agent',
        position: { x: 100, y: 100 },
        width: 200,
        height: 100,
        data: {},
      },
      {
        id: 'node2',
        type: 'tool',
        position: { x: 350, y: 250 },
        width: 200,
        height: 100,
        data: {},
      },
    ];

    const bounds = result.current.calculateGroupBounds(['node1', 'node2'], mockNodes);

    expect(bounds.position.x).toBeLessThan(100); // With padding
    expect(bounds.position.y).toBeLessThan(100);
    expect(bounds.size.width).toBeGreaterThan(450); // Span + padding
    expect(bounds.size.height).toBeGreaterThan(250);
  });

  it('should handle empty node list for bounds calculation', () => {
    const { result } = renderHook(() => useNodeGrouping());

    const bounds = result.current.calculateGroupBounds([], []);

    expect(bounds.position).toEqual({ x: 0, y: 0 });
    expect(bounds.size).toEqual({ width: 0, height: 0 });
  });
});

describe('GroupFunction', () => {
  it('should have all expected function types', () => {
    expect(GroupFunction.PERCEPTION).toBe('perception');
    expect(GroupFunction.DECISION).toBe('decision');
    expect(GroupFunction.ACTION).toBe('action');
    expect(GroupFunction.MEMORY).toBe('memory');
    expect(GroupFunction.COMMUNICATION).toBe('communication');
    expect(GroupFunction.CUSTOM).toBe('custom');
  });
});
