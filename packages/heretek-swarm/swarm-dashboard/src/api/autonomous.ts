/**
 * API Client - Autonomous runtime endpoints
 *
 * Provides typed functions for fetching analysis history, active tasks,
 * goal pipeline state, and events timeline from the autonomous runtime.
 */

import { api } from './client';

// ── Analysis types ───────────────────────────────────────────────────────────

export interface AnalysisRecord {
  id: string;
  collected_at: string;
  trigger_type: string | null;
  metis_analyses: Record<string, unknown>[];
  empath_responses: Record<string, unknown>[];
  chronos_actions: Record<string, unknown>[];
  mediation_dispatched: boolean;
}

export interface AnalysisListResponse {
  items: AnalysisRecord[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// ── Task types ───────────────────────────────────────────────────────────────

export interface TaskSnapshot {
  task_id: string;
  title: string;
  status: string;
  priority: string | null;
  created_at: string | null;
  scheduled_at: string | null;
  assigned_to: string | null;
  description: string | null;
  tags: string[];
}

export interface TaskListResponse {
  items: TaskSnapshot[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// ── Goal types ───────────────────────────────────────────────────────────────

export interface GoalSnapshot {
  goal_id: string;
  title: string;
  description: string | null;
  status: string;
  priority: string | null;
  created_at: string | null;
  updated_at: string | null;
  votes_for: number;
  votes_against: number;
  outcome: string | null;
  proposed_by: string | null;
}

export interface GoalListResponse {
  items: GoalSnapshot[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// ── Event types ──────────────────────────────────────────────────────────────

export interface TimelineEvent {
  id: string;
  event_type: string;
  collected_at: string;
  source: string;
  summary: string | null;
  payload: Record<string, unknown>;
}

export interface EventListResponse {
  items: TimelineEvent[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// ── Status types ─────────────────────────────────────────────────────────────

export interface AutonomousStatus {
  connected: boolean;
  agent_count: number;
  last_update: string | null;
  total_analyses: number;
}

// ── Helper ───────────────────────────────────────────────────────────────────

interface PaginationParams {
  page?: number;
  limit?: number;
}

function buildParams(page = 1, limit = 20): string {
  return `?page=${page}&limit=${limit}`;
}

// ── API functions ────────────────────────────────────────────────────────────

export const getAnalysisHistory = async (
  params?: PaginationParams,
): Promise<AnalysisListResponse> => {
  const response = await api.get<AnalysisListResponse>(
    `/api/autonomous/analyses${buildParams(params?.page, params?.limit)}`,
  );
  return response.data;
};

export const getActiveTasks = async (params?: PaginationParams): Promise<TaskListResponse> => {
  const response = await api.get<TaskListResponse>(
    `/api/autonomous/tasks${buildParams(params?.page, params?.limit)}`,
  );
  return response.data;
};

export const getGoalPipeline = async (params?: PaginationParams): Promise<GoalListResponse> => {
  const response = await api.get<GoalListResponse>(
    `/api/autonomous/goals${buildParams(params?.page, params?.limit)}`,
  );
  return response.data;
};

export const getEventsTimeline = async (params?: PaginationParams): Promise<EventListResponse> => {
  const response = await api.get<EventListResponse>(
    `/api/autonomous/events${buildParams(params?.page, params?.limit)}`,
  );
  return response.data;
};

export const getAutonomousStatus = async (): Promise<AutonomousStatus> => {
  const response = await api.get<AutonomousStatus>('/api/autonomous/status');
  return response.data;
};
