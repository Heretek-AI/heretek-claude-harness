import { describe, it, expect, beforeEach } from 'vitest';
import { useCanvasStore } from '../../src/stores/canvasStore';
import type { AgentData } from '../../src/stores/canvasStore';
import type { Node } from '@xyflow/react';

const makeNode = (id: string, overrides?: Partial<AgentData>): Node<AgentData> => ({
  id,
  type: 'agentNode',
  position: { x: 0, y: 0 },
  data: {
    agentId: id,
    agentType: 'alpha',
    status: 'idle',
    consciousnessMetrics: undefined,
    lastActivity: '',
    messageCount: 0,
    ...overrides,
  },
});

describe('canvasStore', () => {
  beforeEach(() => {
    useCanvasStore.setState({
      nodes: [],
      edges: [],
      selectedNode: null,
      selectedEdge: null,
      isExecuting: false,
      executionProgress: 0,
      loading: false,
      error: null,
    });
  });

  it('adds a node', () => {
    const { addNode } = useCanvasStore.getState();
    addNode(makeNode('agent-1'));
    expect(useCanvasStore.getState().nodes).toHaveLength(1);
    expect(useCanvasStore.getState().nodes[0].id).toBe('agent-1');
  });

  it('removes a node', () => {
    const { addNode, removeNode } = useCanvasStore.getState();
    addNode(makeNode('agent-1'));
    removeNode('agent-1');
    expect(useCanvasStore.getState().nodes).toHaveLength(0);
  });

  it('sets selected node', () => {
    const node = makeNode('agent-1');
    const { addNode, setSelectedNode } = useCanvasStore.getState();
    addNode(node);
    setSelectedNode(node);
    expect(useCanvasStore.getState().selectedNode?.id).toBe('agent-1');
  });

  it('clears selected node', () => {
    const { addNode, setSelectedNode } = useCanvasStore.getState();
    addNode(makeNode('agent-1'));
    setSelectedNode(makeNode('agent-1'));
    setSelectedNode(null);
    expect(useCanvasStore.getState().selectedNode).toBeNull();
  });

  it('updates node metrics', () => {
    const { addNode, updateNodeMetrics } = useCanvasStore.getState();
    addNode(makeNode('agent-1'));
    updateNodeMetrics('agent-1', {
      gwt_score: 0.9,
      phi_value: 0.8,
      ast_competence: 0.7,
      free_energy: 0.6,
    });
    const node = useCanvasStore.getState().nodes.find((n) => n.id === 'agent-1');
    expect(node?.data.consciousnessMetrics).toEqual({
      gwt_score: 0.9,
      phi_value: 0.8,
      ast_competence: 0.7,
      free_energy: 0.6,
    });
  });

  it('sets executing state', () => {
    const { setExecuting } = useCanvasStore.getState();
    setExecuting(true);
    expect(useCanvasStore.getState().isExecuting).toBe(true);
    setExecuting(false);
    expect(useCanvasStore.getState().isExecuting).toBe(false);
  });

  it('sets loading and error', () => {
    const { setLoading, setError } = useCanvasStore.getState();
    setLoading(true);
    expect(useCanvasStore.getState().loading).toBe(true);
    setError('test error');
    expect(useCanvasStore.getState().error).toBe('test error');
  });

  it('resets to initial state', () => {
    const { addNode, setExecuting, setLoading, setError, reset } = useCanvasStore.getState();
    addNode(makeNode('agent-1'));
    setExecuting(true);
    setLoading(true);
    setError('some error');
    reset();
    const s = useCanvasStore.getState();
    expect(s.nodes).toEqual([]);
    expect(s.edges).toEqual([]);
    expect(s.isExecuting).toBe(false);
    expect(s.loading).toBe(false);
    expect(s.error).toBeNull();
  });
});
