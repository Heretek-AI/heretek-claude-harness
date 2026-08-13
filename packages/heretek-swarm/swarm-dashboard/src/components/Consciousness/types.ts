/**
 * Consciousness Metrics Types
 *
 * TypeScript interfaces for consciousness metrics data structures
 * including IIT, FEP, and agent connectivity metrics.
 */

// Consciousness states from EnhancedConsciousnessPlugin
export enum ConsciousnessState {
  DORMANT = "dormant",
  EMERGING = "emerging",
  COHERENT = "coherent",
  TRANSCENDENT = "transcendent",
}

// IIT (Integrated Information Theory) metrics
export interface IITMetrics {
  agent_id: string;
  phi_score: number;
  connectivity: Record<string, number>;
  average_phi: number;
  timestamp: string;
}

// FEP (Free Energy Principle) metrics
export interface FEPMetrics {
  agent_id: string;
  prediction_accuracy: number;
  surprise: number;
  free_energy: number;
  belief_precision: number;
  timestamp: string;
}

// Comprehensive consciousness metrics
export interface ConsciousnessMetrics {
  agent_id: string;
  phi_score: number;
  fep_metrics: FEPMetrics;
  connectivity: Record<string, number>;
  state: ConsciousnessState;
  timestamp: string;
}

// Statistics across all agents
export interface ConsciousnessStatistics {
  timestamp: string;
  total_agents: number;
  average_phi: number;
  average_free_energy: number;
  state_distribution: Record<ConsciousnessState, number>;
  active_connections: number;
}

// Agent state mapping
export interface AgentStates {
  timestamp: string;
  states: Record<string, ConsciousnessState>;
  counts: Record<ConsciousnessState, number>;
  total_agents: number;
}

// Network visualization node
export interface NetworkNode {
  id: string;
  phi: number;
  state: ConsciousnessState;
}

// Network visualization link
export interface NetworkLink {
  source: string;
  target: string;
  weight: number;
}

// Network visualization data
export interface NetworkVisualization {
  timestamp: string;
  nodes: NetworkNode[];
  links: NetworkLink[];
}

// Time series data point
export interface TimeSeriesDataPoint {
  timestamp: string;
  value: number;
}

// Time series response
export interface TimeSeriesResponse {
  agent_id: string;
  metric: "phi" | "free_energy" | "surprise";
  hours: number;
  data_points: TimeSeriesDataPoint[];
  count: number;
}

// Interaction record
export interface InteractionRecord {
  from_agent: string;
  to_agent: string;
  type: string;
  timestamp: string;
  phi?: number;
}

// History response
export interface HistoryResponse {
  timestamp: string;
  agent_id: string | null;
  hours: number;
  history: InteractionRecord[];
  count: number;
}

// Prediction record
export interface PredictionRecord {
  agent_id: string;
  predicted_outcome: any;
  actual_outcome?: any;
  context: Record<string, any>;
  timestamp: string;
  surprise?: number;
  free_energy?: number;
}

// Connectivity matrix
export interface ConnectivityMatrix {
  [agentId: string]: {
    [targetAgentId: string]: number;
  };
}

// Chart configuration
export interface ChartConfig {
  title: string;
  color: string;
  unit?: string;
  min?: number;
  max?: number;
}

// Visualization mode
export enum VisualizationMode {
  NETWORK = "network",
  TIMESERIES = "timeseries",
  HEATMAP = "heatmap",
  RADAR = "radar",
}

// Filter options
export interface FilterOptions {
  agentIds?: string[];
  states?: ConsciousnessState[];
  timeRange?: {
    start: Date;
    end: Date;
  };
  minPhi?: number;
  maxPhi?: number;
}
