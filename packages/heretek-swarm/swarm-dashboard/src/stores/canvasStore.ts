/**
 * Canvas Store - Zustand state management for ReactFlow canvas
 */

import { create } from 'zustand';
import { Node, Edge } from '@xyflow/react';

export interface ConsciousnessMetrics {
  gwt_score: number;
  phi_value: number;
  ast_competence: number;
  free_energy: number;
}

export interface AgentData {
  agentId: string;
  agentType: string;
  status: 'idle' | 'thinking' | 'acting' | 'error' | 'offline';
  consciousnessMetrics?: ConsciousnessMetrics;
  lastActivity: string;
  messageCount?: number;
  [key: string]: unknown;
}

interface CanvasState {
  // State
  nodes: Node<AgentData>[];
  edges: Edge[];
  selectedNode: Node<AgentData> | null;
  selectedEdge: Edge | null;
  isExecuting: boolean;
  executionProgress: number;
  loading: boolean;
  error: string | null;

  // Actions
  setNodes: (nodes: Node<AgentData>[]) => void;
  setEdges: (edges: Edge[]) => void;
  setSelectedNode: (node: Node<AgentData> | null) => void;
  setSelectedEdge: (edge: Edge | null) => void;
  addNode: (node: Node<AgentData>) => void;
  addEdge: (edge: Edge) => void;
  removeNode: (nodeId: string) => void;
  removeEdge: (edgeId: string) => void;
  updateNode: (nodeId: string, data: Partial<AgentData>) => void;
  updateNodeMetrics: (nodeId: string, metrics: ConsciousnessMetrics) => void;
  setExecuting: (executing: boolean) => void;
  setExecutionProgress: (progress: number) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useCanvasStore = create<CanvasState>((set) => ({
  // Initial state
  nodes: [],
  edges: [],
  selectedNode: null,
  selectedEdge: null,
  isExecuting: false,
  executionProgress: 0,
  loading: false,
  error: null,

  // Actions
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  setSelectedNode: (node) => set({ selectedNode: node }),
  setSelectedEdge: (edge) => set({ selectedEdge: edge }),
  addNode: (node) => set((state) => ({ nodes: [...state.nodes, node] })),
  addEdge: (edge) => set((state) => ({ edges: [...state.edges, edge] })),
  removeNode: (nodeId) => set((state) => ({
    nodes: state.nodes.filter(n => n.id !== nodeId)
  })),
  removeEdge: (edgeId) => set((state) => ({
    edges: state.edges.filter(e => e.id !== edgeId)
  })),
  updateNode: (nodeId, data) => set((state) => ({
    nodes: state.nodes.map(n => n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n)
  })),
  updateNodeMetrics: (nodeId, metrics) => set((state) => ({
    nodes: state.nodes.map(n => n.id === nodeId
      ? { ...n, data: { ...n.data, consciousnessMetrics: metrics } }
      : n)
  })),
  setExecuting: (executing) => set({ isExecuting: executing }),
  setExecutionProgress: (progress) => set({ executionProgress: progress }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  reset: () => set({
    nodes: [],
    edges: [],
    selectedNode: null,
    selectedEdge: null,
    isExecuting: false,
    executionProgress: 0,
    loading: false,
    error: null,
  }),
}));
