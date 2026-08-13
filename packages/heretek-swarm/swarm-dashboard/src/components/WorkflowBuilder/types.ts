/**
 * Workflow Builder Types
 *
 * Defines node types for visual workflow builder.
 * Based on Flowise and ReactFlow patterns.
 */

import type { Edge, Position } from '@xyflow/react';

// ============================================================================
// Node Types
// ============================================================================

/**
 * Base interface for all workflow nodes
 */
export interface BaseNodeData {
  id: string;
  type: NodeType;
  position: Position;
}

/**
 * Node type identifiers
 */
export enum NodeType {
  // Agent nodes
  AGENT = 'agent',
  // Tool nodes
  TOOL = 'tool',
  // Memory nodes
  MEMORY = 'memory',
  // Decision nodes
  DECISION = 'decision',
  // Connector nodes
  CONNECTOR = 'connector',
  // Input/Output nodes
  INPUT = 'input',
  OUTPUT = 'output',
  // LLM nodes
  LLM = 'llm',
  // Template nodes
  TEMPLATE = 'template',
}

/**
 * Agent node data
 */
export interface AgentNodeData {
  agentId: string;
  agentType: AgentType;
  config: Record<string, any>;
}

/**
 * Agent types
 */
// ============================================================================
// Agent Types - All 23 Agents
// ============================================================================

/**
 * Complete list of 23 Heretek Swarm agents
 * Organized by tier:
 * - Tier 1 (Core Triad): Steward, Alpha, Beta, Charlie
 * - Tier 2 (Support): Historian, Metis, Empath, Perceiver, Echo
 * - Tier 3 (Exploration): Explorer, Examiner, Dreamer, Coder
 * - Tier 4 (Safety & Security): Sentinel, Sentinel-Prime, Arbiter
 * - Tier 5 (Coordination): Coordinator, Nexus, Catalyst, Chronos
 * - Tier 6 (Enhancement): Prism, Habit-Forge, Perceiver+
 */
export enum AgentType {
  // Tier 1 - Core Triad
  STEWARD = 'steward',
  ALPHA = 'alpha',
  BETA = 'beta',
  CHARLIE = 'charlie',
  // Tier 2 - Support
  HISTORIAN = 'historian',
  METIS = 'metis',
  EMPATH = 'empath',
  PERCEIVER = 'perceiver',
  ECHO = 'echo',
  // Tier 3 - Exploration
  EXPLORER = 'explorer',
  EXAMINER = 'examiner',
  DREAMER = 'dreamer',
  CODER = 'coder',
  // Tier 4 - Safety & Security
  SENTINEL = 'sentinel',
  SENTINEL_PRIME = 'sentinel_prime',
  ARBITER = 'arbiter',
  // Tier 5 - Coordination
  COORDINATOR = 'coordinator',
  NEXUS = 'nexus',
  CATALYST = 'catalyst',
  CHRONOS = 'chronos',
  // Tier 6 - Enhancement
  PRISM = 'prism',
  HABIT_FORGE = 'habit_forge',
  PERCEIVER_PLUS = 'perceiver_plus',
  // Legacy
  CUSTOM = 'custom',
}

/**
 * Agent metadata for UI display
 */
export interface AgentMetadata {
  type: AgentType;
  name: string;
  tier: number;
  tierName: string;
  icon: string;
  description: string;
  capabilities: string[];
  color: string;
}

/**
 * Complete agent registry with metadata
 */
export const AGENT_METADATA: Record<AgentType, AgentMetadata> = {
  [AgentType.STEWARD]: {
    type: AgentType.STEWARD,
    name: 'Steward',
    tier: 1,
    tierName: 'Core Triad',
    icon: '🎯',
    description: 'Central coordination and task orchestration',
    capabilities: ['task_distribution', 'workflow_management', 'resource_allocation'],
    color: '#F59E0B',
  },
  [AgentType.ALPHA]: {
    type: AgentType.ALPHA,
    name: 'Alpha',
    tier: 1,
    tierName: 'Core Triad',
    icon: '🧠',
    description: 'Primary reasoning and decision making',
    capabilities: ['logical_reasoning', 'decision_making', 'strategy'],
    color: '#3B82F6',
  },
  [AgentType.BETA]: {
    type: AgentType.BETA,
    name: 'Beta',
    tier: 1,
    tierName: 'Core Triad',
    icon: '✅',
    description: 'Verification and validation',
    capabilities: ['validation', 'quality_assurance', 'testing'],
    color: '#10B981',
  },
  [AgentType.CHARLIE]: {
    type: AgentType.CHARLIE,
    tier: 1,
    name: 'Charlie',
    tierName: 'Core Triad',
    icon: '🔍',
    description: 'Analysis and pattern recognition',
    capabilities: ['analysis', 'pattern_recognition', 'data_processing'],
    color: '#8B5CF6',
  },
  [AgentType.HISTORIAN]: {
    type: AgentType.HISTORIAN,
    name: 'Historian',
    tier: 2,
    tierName: 'Support',
    icon: '📚',
    description: 'Memory and knowledge management',
    capabilities: ['memory', 'knowledge_retrieval', 'context_preservation'],
    color: '#6366F1',
  },
  [AgentType.METIS]: {
    type: AgentType.METIS,
    name: 'Metis',
    tier: 2,
    tierName: 'Support',
    icon: '🧘',
    description: 'Strategic planning and introspection',
    capabilities: ['strategic_planning', 'reflection', 'self_optimization'],
    color: '#EC4899',
  },
  [AgentType.EMPATH]: {
    type: AgentType.EMPATH,
    name: 'Empath',
    tier: 2,
    tierName: 'Support',
    icon: '💜',
    description: 'Emotional intelligence and rapport',
    capabilities: ['emotional_understanding', 'relationship_building', 'tone_analysis'],
    color: '#F472B6',
  },
  [AgentType.PERCEIVER]: {
    type: AgentType.PERCEIVER,
    name: 'Perceiver',
    tier: 2,
    tierName: 'Support',
    icon: '👁️',
    description: 'Sensory input and data gathering',
    capabilities: ['sensing', 'data_collection', 'observation'],
    color: '#14B8A6',
  },
  [AgentType.ECHO]: {
    type: AgentType.ECHO,
    name: 'Echo',
    tier: 2,
    tierName: 'Support',
    icon: '🔊',
    description: 'Communication and message relay',
    capabilities: ['messaging', 'broadcasting', 'routing'],
    color: '#F97316',
  },
  [AgentType.EXPLORER]: {
    type: AgentType.EXPLORER,
    name: 'Explorer',
    tier: 3,
    tierName: 'Exploration',
    icon: '🗺️',
    description: 'Discovery and exploration',
    capabilities: ['exploration', 'discovery', 'pathfinding'],
    color: '#06B6D4',
  },
  [AgentType.EXAMINER]: {
    type: AgentType.EXAMINER,
    name: 'Examiner',
    tier: 3,
    tierName: 'Exploration',
    icon: '🔬',
    description: 'Deep analysis and investigation',
    capabilities: ['investigation', 'deep_analysis', 'research'],
    color: '#84CC16',
  },
  [AgentType.DREAMER]: {
    type: AgentType.DREAMER,
    name: 'Dreamer',
    tier: 3,
    tierName: 'Exploration',
    icon: '💭',
    description: 'Creative generation and imagination',
    capabilities: ['creative_generation', 'brainstorming', 'ideation'],
    color: '#A855F7',
  },
  [AgentType.CODER]: {
    type: AgentType.CODER,
    name: 'Coder',
    tier: 3,
    tierName: 'Exploration',
    icon: '💻',
    description: 'Code generation and technical tasks',
    capabilities: ['code_generation', 'technical_tasks', 'programming'],
    color: '#22D3EE',
  },
  [AgentType.SENTINEL]: {
    type: AgentType.SENTINEL,
    name: 'Sentinel',
    tier: 4,
    tierName: 'Safety & Security',
    icon: '🛡️',
    description: 'Safety monitoring and guardrails',
    capabilities: ['safety_monitoring', 'guardrails', 'content_filtering'],
    color: '#EF4444',
  },
  [AgentType.SENTINEL_PRIME]: {
    type: AgentType.SENTINEL_PRIME,
    name: 'Sentinel-Prime',
    tier: 4,
    tierName: 'Safety & Security',
    icon: '🛡️',
    description: 'Enhanced security and threat detection',
    capabilities: ['threat_detection', 'security_enforcement', 'access_control'],
    color: '#DC2626',
  },
  [AgentType.ARBITER]: {
    type: AgentType.ARBITER,
    name: 'Arbiter',
    tier: 4,
    tierName: 'Safety & Security',
    icon: '⚖️',
    description: 'Conflict resolution and decision arbitration',
    capabilities: ['conflict_resolution', 'arbitration', 'fair_decisions'],
    color: '#B91C1C',
  },
  [AgentType.COORDINATOR]: {
    type: AgentType.COORDINATOR,
    name: 'Coordinator',
    tier: 5,
    tierName: 'Coordination',
    icon: '📊',
    description: 'Multi-agent coordination and synchronization',
    capabilities: ['coordination', 'synchronization', 'task_scheduling'],
    color: '#0EA5E9',
  },
  [AgentType.NEXUS]: {
    type: AgentType.NEXUS,
    name: 'Nexus',
    tier: 5,
    tierName: 'Coordination',
    icon: '🌐',
    description: 'External integration and API management',
    capabilities: ['external_integration', 'api_management', 'connector_services'],
    color: '#8B5CF6',
  },
  [AgentType.CATALYST]: {
    type: AgentType.CATALYST,
    name: 'Catalyst',
    tier: 5,
    tierName: 'Coordination',
    icon: '⚗️',
    description: 'Change management and transformation',
    capabilities: ['change_management', 'transformation', 'process_improvement'],
    color: '#D946EF',
  },
  [AgentType.CHRONOS]: {
    type: AgentType.CHRONOS,
    name: 'Chronos',
    tier: 5,
    tierName: 'Coordination',
    icon: '⏰',
    description: 'Scheduling and temporal management',
    capabilities: ['scheduling', 'time_management', 'deadline_tracking'],
    color: '#F59E0B',
  },
  [AgentType.PRISM]: {
    type: AgentType.PRISM,
    name: 'Prism',
    tier: 6,
    tierName: 'Enhancement',
    icon: '🔮',
    description: 'Multi-perspective analysis',
    capabilities: ['multi_perspective', 'viewpoint_synthesis', 'perspective_analysis'],
    color: '#E879F9',
  },
  [AgentType.HABIT_FORGE]: {
    type: AgentType.HABIT_FORGE,
    name: 'Habit-Forge',
    tier: 6,
    tierName: 'Enhancement',
    icon: '🔨',
    description: 'Behavior optimization and pattern formation',
    capabilities: ['habit_formation', 'behavior_optimization', 'pattern_learning'],
    color: '#4ADE80',
  },
  [AgentType.PERCEIVER_PLUS]: {
    type: AgentType.PERCEIVER_PLUS,
    name: 'Perceiver+',
    tier: 6,
    tierName: 'Enhancement',
    icon: '🔭',
    description: 'Advanced analytics and predictive modeling',
    capabilities: ['advanced_analytics', 'prediction', 'trend_analysis'],
    color: '#2DD4BF',
  },
  [AgentType.CUSTOM]: {
    type: AgentType.CUSTOM,
    name: 'Custom Agent',
    tier: 0,
    tierName: 'Custom',
    icon: '🤖',
    description: 'User-defined custom agent',
    capabilities: [],
    color: '#6B7280',
  },
};

/**
 * Tool node data
 */
export interface ToolNodeData {
  toolId: string;
  toolName: string;
  toolType: ToolType;
  config: Record<string, any>;
}

/**
 * Tool types
 */
export enum ToolType {
  CODE_EXECUTION = 'code_execution',
  WEB_BROWSER = 'web_browser',
  FILE_OPERATIONS = 'file_operations',
  API_CONNECTOR = 'api_connector',
  DATABASE = 'database',
  VECTOR_SEARCH = 'vector_search',
  CUSTOM = 'custom',
}

/**
 * Memory node data
 */
export interface MemoryNodeData {
  memoryType: MemoryType;
  memoryId?: string;
  query?: string;
  config: Record<string, any>;
}

/**
 * Memory types
 */
export enum MemoryType {
  EPHEMERAL = 'ephemeral',
  PERSISTENT = 'persistent',
  MEM0 = 'mem0',
  HYBRID = 'hybrid',
}

/**
 * Decision node data
 */
export interface DecisionNodeData {
  condition: string;
  branches: DecisionBranch[];
  config: Record<string, any>;
}

/**
 * Decision branch
 */
export interface DecisionBranch {
  id: string;
  label: string;
  condition: string;
}

/**
 * Connector node data
 */
export interface ConnectorNodeData {
  connectorType: ConnectorType;
  config: Record<string, any>;
}

/**
 * Connector types
 */
export enum ConnectorType {
  AGENT_TO_AGENT = 'agent_to_agent',
  AGENT_TO_TOOL = 'agent_to_tool',
  AGENT_TO_MEMORY = 'agent_to_memory',
  TOOL_TO_MEMORY = 'tool_to_memory',
  MEMORY_TO_AGENT = 'memory_to_agent',
  CUSTOM = 'custom',
}

/**
 * LLM node data
 */
export interface LLMNodeData {
  model: string;
  provider: string;
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
  config: Record<string, any>;
}

/**
 * Template node data
 */
export interface TemplateNodeData {
  templateId: string;
  templateType: TemplateType;
  variables: Record<string, any>;
}

/**
 * Template types
 */
export enum TemplateType {
  PROMPT = 'prompt',
  WORKFLOW = 'workflow',
  TASK = 'task',
  CUSTOM = 'custom',
}

// ============================================================================
// Workflow Definition
// ============================================================================

/**
 * Complete workflow definition
 */
export interface Workflow {
  id: string;
  name: string;
  description?: string;
  nodes: BaseNodeData[];
  edges: Edge[];
  version: number;
  createdAt: string;
  updatedAt: string;
}

/**
 * Workflow execution context
 */
export interface WorkflowExecutionContext {
  workflowId: string;
  executionId: string;
  status: ExecutionStatus;
  startTime: string;
  endTime?: string;
  currentNodeId?: string;
  results: ExecutionResult[];
  error?: string;
}

/**
 * Execution status
 */
export enum ExecutionStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

/**
 * Execution result
 */
export interface ExecutionResult {
  nodeId: string;
  nodeName: string;
  status: 'success' | 'error';
  output?: any;
  error?: string;
  duration: number;
  timestamp: string;
}

// ============================================================================
// Node Configuration
// ============================================================================

/**
 * Node configuration schema
 */
export interface NodeConfigSchema {
  type: string;
  properties: ConfigProperty[];
  required: string[];
}

/**
 * Configuration property
 */
export interface ConfigProperty {
  name: string;
  type: PropertyType;
  label: string;
  description?: string;
  default?: any;
  required?: boolean;
  options?: ConfigOption[];
  validation?: ValidationRule[];
}

/**
 * Property types
 */
export enum PropertyType {
  STRING = 'string',
  NUMBER = 'number',
  BOOLEAN = 'boolean',
  SELECT = 'select',
  MULTI_SELECT = 'multi_select',
  TEXTAREA = 'textarea',
  JSON = 'json',
  ARRAY = 'array',
  OBJECT = 'object',
}

/**
 * Configuration option
 */
export interface ConfigOption {
  value: any;
  label: string;
  description?: string;
}

/**
 * Validation rule
 */
export interface ValidationRule {
  type: 'required' | 'min' | 'max' | 'pattern' | 'custom';
  value?: any;
  message?: string;
}

// ============================================================================
// Workflow Validation
// ============================================================================

/**
 * Workflow validation result
 */
export interface WorkflowValidation {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

/**
 * Validation error
 */
export interface ValidationError {
  nodeId: string;
  field: string;
  message: string;
  severity: 'error' | 'warning';
}

/**
 * Validation warning
 */
export interface ValidationWarning {
  nodeId: string;
  message: string;
  suggestion?: string;
}

// ============================================================================
// Workflow Execution API
// ============================================================================

/**
 * Execute workflow request
 */
export interface ExecuteWorkflowRequest {
  workflowId: string;
  inputs?: Record<string, any>;
  options?: ExecutionOptions;
}

/**
 * Execution options
 */
export interface ExecutionOptions {
  timeout?: number;
  maxIterations?: number;
  debug?: boolean;
  saveResults?: boolean;
}

/**
 * Execute workflow response
 */
export interface ExecuteWorkflowResponse {
  executionId: string;
  status: ExecutionStatus;
  workflowId: string;
  startTime: string;
  estimatedDuration?: number;
}

// ============================================================================
// Workflow Templates
// ============================================================================

/**
 * Workflow template
 */
export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: TemplateCategory;
  thumbnail?: string;
  nodes: BaseNodeData[];
  edges: Edge[];
  isPublic: boolean;
}

/**
 * Template categories
 */
export enum TemplateCategory {
  AGENT_ORCHESTRATION = 'agent_orchestration',
  DATA_PROCESSING = 'data_processing',
  CODE_GENERATION = 'code_generation',
  RESEARCH = 'research',
  CUSTOM = 'custom',
}

// ============================================================================
// Node Palette
// ============================================================================

/**
 * Node palette item
 */
export interface NodePaletteItem {
  type: NodeType;
  label: string;
  icon: string;
  category: NodeCategory;
  description: string;
  defaultConfig?: Record<string, any>;
}

/**
 * Node categories
 */
export enum NodeCategory {
  AGENTS = 'agents',
  TOOLS = 'tools',
  MEMORY = 'memory',
  LOGIC = 'logic',
  CONNECTORS = 'connectors',
  LLM = 'llm',
  IO = 'io',
  TEMPLATES = 'templates',
}

// ============================================================================
// Workflow History
// ============================================================================

/**
 * Workflow execution history
 */
export interface WorkflowHistory {
  executionId: string;
  workflowId: string;
  workflowName: string;
  status: ExecutionStatus;
  duration: number;
  startTime: string;
  endTime?: string;
  success: boolean;
}

// ============================================================================
// Export Types
// ============================================================================

/**
 * Workflow export format
 */
export type WorkflowExportFormat = 'json' | 'yaml' | 'python';

/**
 * Exported workflow
 */
export interface ExportedWorkflow {
  format: WorkflowExportFormat;
  content: string;
  exportedAt: string;
}
