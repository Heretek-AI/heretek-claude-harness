/**
 * Workflow Builder - Visual Workflow Editor
 *
 * Flowise-like visual workflow builder for Heretek Swarm.
 * Based on ReactFlow for drag-and-drop node-based workflow design.
 *
 * NOTE: Math.random() is used for random node positioning in the UI canvas.
 * This is non-security-critical - random positions are for UI aesthetics only,
 * not for any cryptographic or authentication purposes. See
 * docs/security/S05_TYPESCRIPT_PRNG_REVIEW.md for details.
 */

import React, { useCallback, useState, useMemo, useRef, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  MiniMap,
  Node,
  NodeChange,
  EdgeChange,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
  Connection,
  NodeTypes,
  useReactFlow,
} from '@xyflow/react';
import { api } from '../../api/client';
import {
  useWorkflowProgress,
  type NodeResult,
  type ExecutionState as WsExecutionState,
} from '../../hooks/useWorkflowProgress';

import {
  BaseNodeData,
  NodeType,
  Workflow,
  WorkflowValidation,
  NodePaletteItem,
  NodeCategory,
  WorkflowTemplate,
  WorkflowHistory,
  WorkflowExportFormat,
} from './types';

import '@xyflow/react/dist/style.css';
import { AgentNode, ToolNode, MemoryNode, DecisionNode, ConnectorNode, LLMNode } from './index';
import { NodeConfigPanel } from '../Workflow/NodeConfigPanel';
import type { AgentConfig } from '../Workflow/NodeConfigPanel';
import { WorkflowList } from './WorkflowList';

// Use environment variable or relative path (nginx proxies /api to api:8000)
const API_URL = import.meta.env.VITE_API_HOST || localStorage.getItem('swarm_api_host') || '';

/** Fetch wrapper that attaches Authorization header from localStorage */
async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const apiKey = localStorage.getItem('api_key');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string>) || {}),
  };
  if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;
  return fetch(url, { ...init, headers });
}

// =============================================================================
// CanvasFlow — inner component with useReactFlow for drag-and-drop
// =============================================================================

interface CanvasFlowProps {
  nodes: Node<BaseNodeData>[];
  edges: Edge[];
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  onNodeClick: (event: React.MouseEvent, node: Node) => void;
  onPaneClick: () => void;
  nodeTypes: NodeTypes;
  onDrop: (type: string, position: { x: number; y: number }) => void;
  configPanelNode: {
    id: string;
    type: string;
    data: { agentId?: string; agentType?: string; config?: Record<string, any> };
  } | null;
  configPanelOpen: boolean;
  handleCloseConfig: () => void;
  handleSaveConfig: (config: AgentConfig) => Promise<void>;
  isExecuting: boolean;
  executionState: { status: string; progress: number; currentNode: string | null };
  wsCurrentNode: string | null;
  wsConnected: boolean;
  wsExecutionState: WsExecutionState;
  wsError: string | null;
  wsNodeResults: Map<string, NodeResult>;
  currentWorkflowId: string | null;
  getStatusBadgeClass: (status: string) => string;
  getProgressBarClass: (status: string) => string;
}

function CanvasFlow({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
  onPaneClick,
  nodeTypes: nt,
  onDrop,
  configPanelNode,
  configPanelOpen,
  handleCloseConfig,
  handleSaveConfig,
  isExecuting,
  executionState,
  wsCurrentNode,
  wsConnected,
  wsExecutionState,
  wsError,
  wsNodeResults,
  currentWorkflowId,
  getStatusBadgeClass,
  getProgressBarClass,
}: CanvasFlowProps) {
  const reactFlow = useReactFlow();
  const wrapperRef = useRef<HTMLDivElement>(null);

  /** Allow drop by preventing default */
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  /** Handle drop: read type from dataTransfer, convert screen→flow position */
  const onDropHandler = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const rawData = event.dataTransfer.getData('application/reactflow');
      if (!rawData) return;

      const type = rawData;
      const position = reactFlow.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      onDrop(type, position);
    },
    [reactFlow, onDrop],
  );

  return (
    <div className="canvas-container" ref={wrapperRef}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onDragOver={onDragOver}
        onDrop={onDropHandler}
        nodeTypes={nt}
        fitView
        snapToGrid
        snapGrid={[15, 15]}
        defaultEdgeOptions={{
          animated: true,
          type: 'smoothstep',
          style: { stroke: '#b1b1b1b1', strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#b1b1b1',
          },
        }}
        deleteKeyCode="Delete"
      >
        <Background color="#f8fafc" variant={BackgroundVariant.Dots} />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            const data = node.data as BaseNodeData;
            switch (data.type) {
              case NodeType.AGENT:
                return '#3b82f6';
              case NodeType.TOOL:
                return '#06b6d4';
              case NodeType.MEMORY:
                return '#8b5cf6';
              case NodeType.DECISION:
                return '#eab308';
              case NodeType.CONNECTOR:
                return '#6366f1';
              case NodeType.LLM:
                return '#10b981';
              default:
                return '#6b7280';
            }
          }}
          nodeStrokeWidth={2}
          zoomable
          pannable
        />
      </ReactFlow>

      {/* Node Configuration Panel */}
      <NodeConfigPanel
        node={configPanelNode}
        isOpen={configPanelOpen}
        onClose={handleCloseConfig}
        onSave={handleSaveConfig}
      />

      {/* Execution Progress Panel */}
      {isExecuting && (
        <div className="absolute top-4 right-4 w-80 bg-white border border-gray-300 rounded-lg shadow-lg p-4 z-50 max-h-[70vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-800">Workflow Execution</h3>
            <span
              className={`text-xs px-2 py-1 rounded ${getStatusBadgeClass(executionState.status)}`}
            >
              {executionState.status}
            </span>
          </div>

          {/* Progress Bar */}
          <div className="mb-3">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">Progress</span>
              <span className="text-gray-800 font-medium">{executionState.progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${getProgressBarClass(executionState.status)}`}
                style={{ width: `${executionState.progress}%` }}
              />
            </div>
          </div>

          {/* Current Node */}
          {wsCurrentNode && (
            <div className="mb-2 text-sm">
              <span className="text-gray-600">Current Node:</span>
              <span className="ml-2 text-gray-800 font-medium">{wsCurrentNode}</span>
            </div>
          )}

          {/* WebSocket Connection Status */}
          <div className="mb-2 text-xs">
            {wsConnected ? (
              <span className="text-green-600">🟢 WebSocket connected</span>
            ) : (
              <span className="text-red-600">🔴 WebSocket disconnected</span>
            )}
          </div>

          {/* Error Message */}
          {wsError && (
            <div className="mb-2 text-sm text-red-600 bg-red-50 rounded p-2">{wsError}</div>
          )}

          {/* Per-Node Results */}
          {wsNodeResults.size > 0 && (
            <div className="mt-3 border-t border-gray-200 pt-3">
              <h4 className="text-xs font-semibold text-gray-600 uppercase mb-2">Node Results</h4>
              <div className="space-y-2">
                {Array.from(wsNodeResults.entries()).map(([nodeId, result]) => (
                  <div
                    key={nodeId}
                    className={`p-2 rounded text-xs border ${
                      result.status === 'completed'
                        ? 'bg-green-50 border-green-200'
                        : result.status === 'failed'
                          ? 'bg-red-50 border-red-200'
                          : result.status === 'running'
                            ? 'bg-blue-50 border-blue-200'
                            : 'bg-gray-50 border-gray-200'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className="font-medium text-gray-800 truncate max-w-[140px]"
                        title={nodeId}
                      >
                        {nodeId}
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          result.status === 'completed'
                            ? 'bg-green-100 text-green-800'
                            : result.status === 'failed'
                              ? 'bg-red-100 text-red-800'
                              : result.status === 'running'
                                ? 'bg-blue-100 text-blue-800'
                                : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {result.status}
                      </span>
                    </div>
                    {result.duration !== undefined && (
                      <div className="text-gray-500">Duration: {result.duration}ms</div>
                    )}
                    {result.output !== undefined && result.output !== null && (
                      <div
                        className="text-gray-600 mt-1 truncate"
                        title={
                          typeof result.output === 'string'
                            ? result.output
                            : JSON.stringify(result.output)
                        }
                      >
                        Output:{' '}
                        {String(
                          typeof result.output === 'string'
                            ? result.output.slice(0, 80)
                            : JSON.stringify(result.output).slice(0, 80),
                        )}
                        {(typeof result.output === 'string'
                          ? result.output.length
                          : JSON.stringify(result.output).length) > 80 && '…'}
                      </div>
                    )}
                    {result.error && <div className="text-red-600 mt-1">Error: {result.error}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Execution ID */}
          {currentWorkflowId && (
            <div className="mt-3 text-xs text-gray-400">Workflow: {currentWorkflowId}</div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// WorkflowBuilder — outer shell with state, palette, toolbar, properties
// =============================================================================

/**
 * Workflow Builder Component
 */
export function WorkflowBuilder() {
  const [nodes, setNodes, onNodesChange] = useNodesState<BaseNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<BaseNodeData | null>(null);
  const [nodeConfig, setNodeConfig] = useState<Record<string, Record<string, any>>>({});
  const [validation, setValidation] = useState<WorkflowValidation>({
    valid: true,
    errors: [],
    warnings: [],
  });
  const [isExecuting, setIsExecuting] = useState(false);
  const [savedWorkflows, setSavedWorkflows] = useState<Workflow[]>([]);
  const [currentWorkflowId, setCurrentWorkflowId] = useState<string | null>(null);
  const [workflowName, setWorkflowName] = useState<string>('Custom Workflow');
  const [workflowListOpen, setWorkflowListOpen] = useState(false);

  // Real-time execution progress via WebSocket hook (replaces SSE)
  const {
    executionState: wsExecutionState,
    currentNode: wsCurrentNode,
    progress: wsProgress,
    nodeResults: wsNodeResults,
    error: wsError,
    connected: wsConnected,
    executeWorkflow: wsExecuteWorkflow,
    reExecuteWorkflow: wsReExecuteWorkflow,
  } = useWorkflowProgress();

  // Derive display state from WebSocket hook
  const executionState = {
    status:
      wsExecutionState === 'idle' && !wsConnected
        ? ('idle' as const)
        : wsConnected && wsExecutionState === 'idle'
          ? ('connected' as const)
          : wsExecutionState,
    progress: wsProgress,
    currentNode: wsCurrentNode,
    message: wsError || '',
    executionId: currentWorkflowId || '',
  };

  // Helper to get status badge CSS classes — avoids nested ternary chains (S3358)
  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'connected':
        return 'bg-blue-100 text-blue-800';
      case 'running':
        return 'bg-yellow-100 text-yellow-800';
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };
  const getProgressBarClass = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-blue-500';
    }
  };

  // NodeConfigPanel state
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [configPanelNode, setConfigPanelNode] = useState<{
    id: string;
    type: string;
    data: {
      agentId?: string;
      agentType?: string;
      config?: Record<string, any>;
    };
  } | null>(null);

  /**
   * Node palette - organized by category
   */
  const nodePalette: NodePaletteItem[] = useMemo(
    () => [
      // Agents
      {
        type: NodeType.AGENT,
        label: 'Steward',
        icon: '👥',
        category: NodeCategory.AGENTS,
        description: 'Orchestrator agent for coordinating swarm operations',
        defaultConfig: {
          agentType: 'steward',
        },
      },
      {
        type: NodeType.AGENT,
        label: 'Alpha',
        icon: '🧠',
        category: NodeCategory.AGENTS,
        description: 'Primary analyst agent in Triad',
        defaultConfig: {
          agentType: 'alpha',
        },
      },
      // Tools
      {
        type: NodeType.TOOL,
        label: 'Code Execution',
        icon: '⚡',
        category: NodeCategory.TOOLS,
        description: 'Execute code in a secure environment',
        defaultConfig: {
          toolType: 'code_execution',
        },
      },
      {
        type: NodeType.TOOL,
        label: 'Web Browser',
        icon: '🌐',
        category: NodeCategory.TOOLS,
        description: 'Browse and interact with web pages',
        defaultConfig: {
          toolType: 'web_browser',
        },
      },
      // Memory
      {
        type: NodeType.MEMORY,
        label: 'Ephemeral Memory',
        icon: '⚡',
        category: NodeCategory.MEMORY,
        description: 'Short-term in-memory storage',
        defaultConfig: {
          memoryType: 'ephemeral',
        },
      },
      {
        type: NodeType.MEMORY,
        label: 'Persistent Memory',
        icon: '💾',
        category: NodeCategory.MEMORY,
        description: 'Long-term database storage',
        defaultConfig: {
          memoryType: 'persistent',
        },
      },
      {
        type: NodeType.MEMORY,
        label: 'mem0 Memory',
        icon: '🧠',
        category: NodeCategory.MEMORY,
        description: 'AI-powered memory with mem0',
        defaultConfig: {
          memoryType: 'mem0',
        },
      },
      // Decision
      {
        type: NodeType.DECISION,
        label: 'Conditional Branch',
        icon: '🔀',
        category: NodeCategory.LOGIC,
        description: 'Branch workflow based on conditions',
        defaultConfig: {
          condition: 'true',
          branches: [
            { id: 'true', label: 'True', condition: 'true' },
            { id: 'false', label: 'False', condition: 'false' },
          ],
        },
      },
      // Connector
      {
        type: NodeType.CONNECTOR,
        label: 'Agent to Agent',
        icon: '🤝',
        category: NodeCategory.CONNECTORS,
        description: 'Connect agents for collaboration',
        defaultConfig: {
          connectorType: 'agent_to_agent',
        },
      },
      // LLM
      {
        type: NodeType.LLM,
        label: 'OpenAI GPT-4',
        icon: '🤖',
        category: NodeCategory.LLM,
        description: 'OpenAI GPT-4 model',
        defaultConfig: {
          model: 'gpt-4',
          provider: 'openai',
          temperature: 0.7,
          maxTokens: 4096,
        },
      },
    ],
    [],
  );

  /**
   * Register custom node types
   */
  const nodeTypes: NodeTypes = useMemo(
    () => ({
      [NodeType.AGENT]: AgentNode,
      [NodeType.TOOL]: ToolNode,
      [NodeType.MEMORY]: MemoryNode,
      [NodeType.DECISION]: DecisionNode,
      [NodeType.CONNECTOR]: ConnectorNode,
      [NodeType.LLM]: LLMNode,
    }),
    [],
  );

  /**
   * Add node to canvas. Accepts optional position for drag-and-drop placement;
   * falls back to random position for click-to-add from palette.
   */
  const addNode = useCallback(
    (type: string, position?: { x: number; y: number }) => {
      const paletteItem = nodePalette.find((item) => item.type === type);
      if (!paletteItem) return;

      const nodeId = `node-${Date.now()}`;
      const newNode: Node<BaseNodeData> = {
        id: nodeId,
        type: paletteItem.type,
        position: position || { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 },
        data: {
          id: nodeId,
          type: paletteItem.type,
          ...paletteItem.defaultConfig,
          config: paletteItem.defaultConfig || {},
          // Add callback for opening config panel
          onOpenConfig: handleOpenConfig,
        } as any,
      };

      setNodes((nds) => [...nds, newNode]);
      setNodeConfig((prev) => ({
        ...prev,
        [newNode.id]: paletteItem.defaultConfig || {},
      }));
    },
    [nodePalette],
  );

  /**
   * Handle opening configuration panel
   */
  const handleOpenConfig = useCallback(
    (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (node) {
        setConfigPanelNode({
          id: node.id,
          type: node.type || 'agent',
          data: {
            agentId: (node.data as any).agentId || node.id,
            agentType: (node.data as any).agentType || 'steward',
            config: (node.data as any).config || {},
          },
        });
        setConfigPanelOpen(true);
      }
    },
    [nodes],
  );

  /**
   * Handle closing configuration panel
   */
  const handleCloseConfig = useCallback(() => {
    setConfigPanelOpen(false);
    setConfigPanelNode(null);
  }, []);

  /**
   * Handle saving configuration via API
   */
  const handleSaveConfig = useCallback(
    async (config: AgentConfig) => {
      try {
        const response = await authFetch(`${API_URL}/api/agent-config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            agent_id: config.agentId,
            agent_type: config.agentType,
            config: {
              llmProvider: config.llmProvider,
              model: config.model,
              temperature: config.temperature,
              maxTokens: config.maxTokens,
              // Arbiter-specific
              decisionThreshold: config.decisionThreshold,
              quorumSize: config.quorumSize,
              timeout: config.timeout,
              // Prism-specific
              analysisDepth: config.analysisDepth,
              perspectiveCount: config.perspectiveCount,
              confidenceThreshold: config.confidenceThreshold,
              // Habit-Forge-specific
              repetitionThreshold: config.repetitionThreshold,
              rewardSchedule: config.rewardSchedule,
              extinctionCriteria: config.extinctionCriteria,
            },
          }),
        });

        if (!response.ok) throw new Error('Failed to save configuration');

        // Update local node config
        if (configPanelNode) {
          setNodeConfig((prev) => ({
            ...prev,
            [configPanelNode.id]: {
              ...prev[configPanelNode.id],
              agentType: config.agentType,
              llmProvider: config.llmProvider,
              model: config.model,
              temperature: config.temperature,
              maxTokens: config.maxTokens,
            },
          }));

          // Update node data in ReactFlow
          setNodes((nds) =>
            nds.map((node) =>
              node.id === configPanelNode.id
                ? {
                    ...node,
                    data: {
                      ...(node.data as any),
                      agentType: config.agentType,
                      config: {
                        ...((node.data as any).config || {}),
                        llmProvider: config.llmProvider,
                        model: config.model,
                        temperature: config.temperature,
                        maxTokens: config.maxTokens,
                      },
                    },
                  }
                : node,
            ),
          );
        }
      } catch (error) {
        console.error('Failed to save agent configuration:', error);
        throw error;
      }
    },
    [configPanelNode, setNodes],
  );

  /**
   * Delete node
   */
  const deleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((node) => node.id !== nodeId));
      setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
      setNodeConfig((prev) => {
        const newConfig = { ...prev };
        delete newConfig[nodeId];
        return newConfig;
      });
      if (selectedNode?.id === nodeId) {
        setSelectedNode(null);
      }
    },
    [selectedNode],
  );

  /**
   * Handle connection
   */
  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge(connection, eds));
  }, []);

  /**
   * Handle node selection
   */
  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    // Don't select node if config panel was opened
    if ((node.data as any).onOpenConfig) {
      // Let the node handle the click for config
    }
    setSelectedNode(node.data as BaseNodeData);
  }, []);

  /**
   * Handle background click to deselect
   */
  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  /**
   * Validate workflow
   */
  const validateWorkflow = useCallback(() => {
    const errors: {
      nodeId: string;
      field: string;
      message: string;
      severity: 'error' | 'warning';
    }[] = [];
    const warnings: { nodeId: string; message: string; suggestion?: string }[] = [];

    // Check for nodes without connections
    nodes.forEach((node) => {
      const hasConnections = edges.some(
        (edge) => edge.source === node.id || edge.target === node.id,
      );
      if (!hasConnections && nodes.length > 1) {
        warnings.push({
          nodeId: node.id,
          message: 'Node is not connected to any other node',
        });
      }
    });

    // Check for cycles
    const visited = new Set<string>();
    const hasCycle = (nodeId: string, path: string[] = []): boolean => {
      if (path.includes(nodeId)) {
        return true;
      }
      if (visited.has(nodeId)) {
        return false;
      }
      visited.add(nodeId);
      const outgoingEdges = edges.filter((edge) => edge.source === nodeId);
      return outgoingEdges.some((edge) => hasCycle(edge.target, [...path, nodeId]));
    };

    nodes.forEach((node) => {
      if (hasCycle(node.id)) {
        errors.push({
          nodeId: node.id,
          field: 'connections',
          message: 'Cycle detected in workflow',
          severity: 'error',
        });
      }
    });

    setValidation({
      valid: errors.length === 0,
      errors,
      warnings,
    });
  }, [nodes, edges]);

  /**
   * Export workflow
   */
  const exportWorkflow = useCallback(
    (format: WorkflowExportFormat) => {
      const workflow: Workflow = {
        id: 'custom',
        name: workflowName,
        description: 'Custom workflow created in Workflow Builder',
        nodes: nodes.map((n) => n.data as BaseNodeData),
        edges: edges,
        version: 1,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      let content = '';
      if (format === 'json') {
        content = JSON.stringify(workflow, null, 2);
      } else if (format === 'yaml') {
        content = `name: ${workflow.name}\n`;
        content += `description: ${workflow.description}\n`;
        content += `nodes:\n`;
        nodes.forEach((node) => {
          content += `  - id: ${node.id}\n`;
          content += `    type: ${node.type}\n`;
        });
        content += `edges:\n`;
        edges.forEach((edge) => {
          content += `  - source: ${edge.source}\n`;
          content += `    target: ${edge.target}\n`;
        });
      }

      // Create download link
      const blob = new Blob([content], {
        type: format === 'yaml' ? 'text/yaml' : 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `workflow.${format}`;
      a.click();
    },
    [nodes, edges, workflowName],
  );

  /**
   * Save workflow to backend. Uses workflowName state for the name field.
   */
  const saveWorkflow = useCallback(async () => {
    try {
      const response = await authFetch(`${API_URL}/api/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: currentWorkflowId || `workflow-${Date.now()}`,
          name: workflowName || 'Untitled Workflow',
          description: 'Workflow created in Workflow Builder',
          nodes: nodes.map((n) => ({ id: n.id, type: n.type, position: n.position, data: n.data })),
          edges: edges,
          version: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });

      if (!response.ok) throw new Error('Failed to save workflow');

      const saved = await response.json();
      setCurrentWorkflowId(saved.id);

      // Refresh workflow list
      loadWorkflows();
    } catch (error) {
      console.error('Failed to save workflow:', error);
      alert('Failed to save workflow');
    }
  }, [nodes, edges, currentWorkflowId, workflowName]);

  /**
   * Load workflow list from backend
   */
  const loadWorkflows = useCallback(async () => {
    try {
      const response = await authFetch(`${API_URL}/api/workflows`);
      if (!response.ok) throw new Error('Failed to load workflows');

      const data = await response.json();
      setSavedWorkflows(data.workflows || []);
    } catch (error) {
      console.error('Failed to load workflows:', error);
    }
  }, []);

  /**
   * Load specific workflow by ID and populate the canvas
   */
  const loadWorkflow = useCallback(async (workflowId: string) => {
    try {
      const response = await authFetch(`${API_URL}/api/workflows/${workflowId}`);
      if (!response.ok) throw new Error('Failed to load workflow');

      const data = await response.json();
      setNodes(
        data.nodes.map((n: any) => ({
          id: n.id,
          type: n.type,
          position: n.position || { x: 0, y: 0 },
          data: n.data,
        })),
      );
      setEdges(data.edges || []);
      setCurrentWorkflowId(workflowId);
      setWorkflowName(data.name || 'Untitled Workflow');
      setWorkflowListOpen(false);
    } catch (error) {
      console.error('Failed to load workflow:', error);
    }
  }, []);

  /**
   * Execute workflow using WebSocket-based progress tracking.
   * Saves the workflow first, then triggers execution via the WS hook.
   */
  const executeWorkflow = useCallback(async () => {
    if (!validation.valid || nodes.length === 0) {
      alert('Please fix validation errors before executing');
      return;
    }

    try {
      setIsExecuting(true);

      // First, save the workflow
      const saveResponse = await authFetch(`${API_URL}/api/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: currentWorkflowId || `workflow-${Date.now()}`,
          name: workflowName || 'Untitled Workflow',
          description: 'Workflow created in Workflow Builder',
          nodes: nodes.map((n) => ({ id: n.id, type: n.type, position: n.position, data: n.data })),
          edges: edges,
          version: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });

      if (!saveResponse.ok) throw new Error('Failed to save workflow');
      const saved = await saveResponse.json();
      setCurrentWorkflowId(saved.id);

      // Execute via WebSocket hook (connects + POSTs to execute endpoint)
      await wsExecuteWorkflow(saved.id);
    } catch (error) {
      console.error('Failed to execute workflow:', error);
      setIsExecuting(false);
    }
  }, [nodes, edges, currentWorkflowId, validation.valid, wsExecuteWorkflow, workflowName]);

  /**
   * Re-execute the last workflow via the hook
   */
  const reExecuteWorkflow = useCallback(async () => {
    setIsExecuting(true);
    await wsReExecuteWorkflow();
  }, [wsReExecuteWorkflow]);

  /**
   * Re-execute a specific workflow from the WorkflowList sidebar.
   * Loads the workflow first, then executes.
   */
  const handleReExecuteFromList = useCallback(
    async (workflowId: string) => {
      await loadWorkflow(workflowId);
      setIsExecuting(true);
      // Small delay to let canvas populate before triggering execution
      setTimeout(async () => {
        await wsExecuteWorkflow(workflowId);
      }, 100);
    },
    [loadWorkflow, wsExecuteWorkflow],
  );

  // Sync isExecuting with WebSocket execution state
  useEffect(() => {
    if (wsExecutionState === 'completed' || wsExecutionState === 'failed') {
      const timer = setTimeout(() => setIsExecuting(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [wsExecutionState]);

  /**
   * Map node execution results from WS hook to node visual state.
   * Updates ReactFlow nodes with executionStatus data.
   */
  useEffect(() => {
    if (wsNodeResults.size === 0) return;

    setNodes((nds) =>
      nds.map((node) => {
        const result = wsNodeResults.get(node.id);
        if (!result) return node;
        return {
          ...node,
          data: {
            ...node.data,
            executionStatus: result.status,
            executionOutput: result.output,
            executionError: result.error,
            executionDuration: result.duration,
          },
        };
      }),
    );
  }, [wsNodeResults, setNodes]);

  /**
   * Load workflows on mount
   */
  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  /**
   * Validate on nodes/edges change
   */
  useEffect(() => {
    validateWorkflow();
  }, [nodes, edges]);

  return (
    <div className="workflow-builder">
      <div className="workflow-header">
        <h1>Workflow Builder</h1>
        <div className="header-actions">
          {/* Workflow name input */}
          <input
            type="text"
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
            placeholder="Workflow name"
            className="workflow-name-input"
            style={{
              padding: '6px 10px',
              border: '1px solid #d1d5db',
              borderRadius: 6,
              fontSize: 14,
              width: 180,
              outline: 'none',
            }}
          />
          <button
            onClick={validateWorkflow}
            className="btn btn-secondary"
            disabled={nodes.length === 0}
          >
            Validate
          </button>
          <button onClick={saveWorkflow} className="btn btn-primary" disabled={nodes.length === 0}>
            Save Workflow
          </button>
          <div className="export-buttons">
            <button onClick={() => exportWorkflow('json')} className="btn btn-secondary">
              Export JSON
            </button>
            <button onClick={() => exportWorkflow('yaml')} className="btn btn-secondary">
              Export YAML
            </button>
          </div>
        </div>
        <div className="workflow-actions">
          {/* Legacy select (hidden, replaced by WorkflowList sidebar) */}
          <select
            value={currentWorkflowId || ''}
            onChange={(e) => loadWorkflow(e.target.value)}
            className="workflow-select"
            style={{ display: 'none' }}
          >
            <option value="">Load Saved Workflow...</option>
            {savedWorkflows.map((wf) => (
              <option key={wf.id} value={wf.id}>
                {wf.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => setWorkflowListOpen((o) => !o)}
            className="btn btn-secondary"
            style={{
              background: workflowListOpen ? '#3b82f6' : undefined,
              color: workflowListOpen ? 'white' : undefined,
            }}
          >
            {workflowListOpen ? '✕ Close List' : '📋 Workflows'}
          </button>
          <button
            onClick={executeWorkflow}
            className="btn btn-success"
            disabled={nodes.length === 0 || !validation.valid}
          >
            Execute Workflow
          </button>
          <button
            onClick={reExecuteWorkflow}
            className="btn btn-secondary"
            disabled={!currentWorkflowId || wsExecutionState === 'running'}
            title="Re-execute the last workflow"
          >
            Re-execute
          </button>
        </div>
      </div>

      {/* Execution Progress Bar */}
      {isExecuting && (
        <div className="px-5 py-2 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <span
              className={`text-xs px-2 py-1 rounded font-medium ${getStatusBadgeClass(executionState.status)}`}
            >
              {executionState.status === 'running' ? 'Executing...' : executionState.status}
            </span>
            <div className="flex-1 bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${getProgressBarClass(executionState.status)}`}
                style={{ width: `${executionState.progress}%` }}
              />
            </div>
            <span className="text-sm text-gray-600 font-medium min-w-[3rem] text-right">
              {executionState.progress}%
            </span>
            {wsCurrentNode && (
              <span className="text-xs text-gray-500">
                Node: <span className="font-medium text-gray-700">{wsCurrentNode}</span>
              </span>
            )}
            {!wsConnected && wsExecutionState === 'running' && (
              <span className="text-xs text-red-500">🔴 Disconnected</span>
            )}
            {wsConnected && <span className="text-xs text-green-500">🟢 Connected</span>}
          </div>
        </div>
      )}

      {!validation.valid && (
        <div className="validation-errors">
          <h3>Validation Errors</h3>
          {validation.errors.map((error, idx) => (
            <div key={idx} className="error-item">
              <strong>{error.nodeId}</strong>: {error.message}
            </div>
          ))}
        </div>
      )}

      <div className="workflow-content">
        <div className="node-palette">
          <h2>Node Palette</h2>
          <div className="palette-categories">
            {Object.values(NodeCategory).map((category) => (
              <div key={category} className="palette-category">
                <h3>{category}</h3>
                {nodePalette
                  .filter((item) => item.category === category)
                  .map((item) => (
                    <div
                      key={item.type}
                      className="palette-item"
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.setData('application/reactflow', item.type);
                        e.dataTransfer.effectAllowed = 'move';
                      }}
                      onClick={() => addNode(item.type)}
                    >
                      <span className="palette-icon">{item.icon}</span>
                      <span className="palette-label">{item.label}</span>
                      <span className="palette-desc">{item.description}</span>
                    </div>
                  ))}
              </div>
            ))}
          </div>
        </div>

        <ReactFlowProvider>
          <CanvasFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            onDrop={addNode}
            configPanelNode={configPanelNode}
            configPanelOpen={configPanelOpen}
            handleCloseConfig={handleCloseConfig}
            handleSaveConfig={handleSaveConfig}
            isExecuting={isExecuting}
            executionState={executionState}
            wsCurrentNode={wsCurrentNode}
            wsConnected={wsConnected}
            wsExecutionState={wsExecutionState}
            wsError={wsError}
            wsNodeResults={wsNodeResults}
            currentWorkflowId={currentWorkflowId}
            getStatusBadgeClass={getStatusBadgeClass}
            getProgressBarClass={getProgressBarClass}
          />
        </ReactFlowProvider>

        {/* Workflow List Sidebar */}
        <WorkflowList
          isOpen={workflowListOpen}
          onClose={() => setWorkflowListOpen(false)}
          onLoad={loadWorkflow}
          onReExecute={handleReExecuteFromList}
          onRefresh={loadWorkflows}
        />
      </div>

      {selectedNode && (
        <div className="node-properties">
          <h3>Node Properties</h3>
          <div className="property-group">
            <label>Node ID:</label>
            <input type="text" value={selectedNode.id} readOnly className="property-input" />
          </div>
          <div className="property-group">
            <label>Node Type:</label>
            <input type="text" value={selectedNode.type} readOnly className="property-input" />
          </div>
          {Object.keys(nodeConfig[selectedNode.id] || {}).map((key) => (
            <div key={key} className="property-group">
              <label>{key}:</label>
              <input
                type="text"
                value={JSON.stringify(nodeConfig[selectedNode.id]?.[key])}
                onChange={(e) => {
                  const value = e.target.value;
                  try {
                    const parsed = JSON.parse(value);
                    setNodeConfig((prev) => ({
                      ...prev,
                      [selectedNode.id]: {
                        ...prev[selectedNode.id],
                        [key]: parsed,
                      },
                    }));
                  } catch {
                    setNodeConfig((prev) => ({
                      ...prev,
                      [selectedNode.id]: {
                        ...prev[selectedNode.id],
                        [key]: value,
                      },
                    }));
                  }
                }}
                className="property-input"
              />
            </div>
          ))}
          <div className="property-actions">
            <button onClick={() => deleteNode(selectedNode.id)} className="btn btn-danger">
              Delete Node
            </button>
          </div>
        </div>
      )}
      <style>{`
        .workflow-builder {
          display: flex;
          flex-direction: column;
          height: 100vh;
          background: #f8fafc;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        .workflow-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px;
          background: white;
          border-bottom: 1px solid #e5e7eb;
        }

        .workflow-header h1 {
          margin: 0;
          font-size: 24px;
          color: #1f2937;
        }

        .header-actions {
          display: flex;
          gap:  10px;
          align-items: center;
        }

        .export-buttons {
          display: flex;
          gap: 5px;
        }

        .validation-errors {
          background: #fee2e2;
          border: 1px solid #fecaca;
          border-radius: 8px;
          padding: 15px;
          margin: 10px 20px;
        }

        .validation-errors h3 {
          margin: 0 0 10px 0;
          color: #991b1b;
        }

        .error-item {
          color: #991b1b;
          margin: 5px 0;
        }

        .workflow-content {
          display: flex;
          flex: 1;
          overflow: hidden;
        }

        .node-palette {
          width: 300px;
          background: white;
          border-right: 1px solid #e5e7eb;
          overflow-y: auto;
          padding: 15px;
        }

        .node-palette h2 {
          margin: 0 0 15px 0;
          font-size: 18px;
          color: #1f2937;
        }

        .palette-categories {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .palette-category h3 {
          margin: 0 0 10px 0;
          font-size: 14px;
          color: #6b7280;
          text-transform: uppercase;
        }

        .palette-item {
          padding: 10px;
          background: #f9fafb;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          cursor: pointer;
          margin-bottom: 8px;
          transition: all 0.2s;
        }

        .palette-item:hover {
          background: #e0e7ff;
          border-color: #3b82f6;
        }

        .palette-icon {
          font-size: 24px;
          margin-right: 10px;
        }

        .palette-label {
          font-weight: 600;
          color: #1f2937;
        }

        .palette-desc {
          display: block;
          font-size: 12px;
          color: #6b7280;
          margin-top: 5px;
        }

        .canvas-container {
          flex: 1;
          background: #f8fafc;
          position: relative;
        }

        .react-flow-wrapper {
          height: 100%;
        }

        /* Execution Panel positioning */
        .canvas-container .react-flow {
          position: relative;
        }

        .node-properties {
          position: fixed;
          right: 20px;
          top: 80px;
          width: 300px;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 15px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          max-height: calc(100vh - 100px);
          overflow-y: auto;
        }

        .node-properties h3 {
          margin: 0 0 15px 0;
          font-size: 16px;
          color: #1f2937;
        }

        .property-group {
          margin-bottom: 10px;
        }

        .property-group label {
          display: block;
          margin-bottom: 5px;
          font-size: 12px;
          color: #6b7280;
          font-weight: 600;
        }

        .property-input {
          width: 100%;
          padding: 8px;
          border: 1px solid #e5e7eb;
          border-radius: 4px;
          font-size: 14px;
        }

        .property-actions {
          display: flex;
          gap: 10px;
          margin-top: 15px;
        }

        .btn {
          padding: 8px 16px;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-primary {
          background: #3b82f6;
          color: white;
        }

        .btn-primary:hover {
          background: #2563eb;
        }

        .btn-secondary {
          background: #e5e7eb;
          color: #333;
        }

        .btn-secondary:hover {
          background: #d1d5db;
        }

        .btn-danger {
          background: #ef4444;
          color: white;
        }

        .btn-danger:hover {
          background: #dc2626;
        }
      `}</style>
    </div>
  );
}
