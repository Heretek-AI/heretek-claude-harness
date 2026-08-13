/**
 * AutonomousPage component tests
 *
 * Verifies the Autonomous section renders all four tab sub-views,
 * handles loading/error/empty states, and tab switching works correctly.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('../../../api/autonomous', () => ({
  getAnalysisHistory: vi.fn(),
  getActiveTasks: vi.fn(),
  getGoalPipeline: vi.fn(),
  getEventsTimeline: vi.fn(),
  getAutonomousStatus: vi.fn(),
}));

// ── Imports after mocks are hoisted ────────────────────────────────────────

import { AutonomousPage } from '../AutonomousPage';
import {
  getAnalysisHistory,
  getActiveTasks,
  getGoalPipeline,
  getEventsTimeline,
} from '../../../api/autonomous';
import type {
  AnalysisRecord,
  TaskSnapshot,
  GoalSnapshot,
  TimelineEvent,
} from '../../../api/autonomous';

const mockGetAnalysisHistory = vi.mocked(getAnalysisHistory);
const mockGetActiveTasks = vi.mocked(getActiveTasks);
const mockGetGoalPipeline = vi.mocked(getGoalPipeline);
const mockGetEventsTimeline = vi.mocked(getEventsTimeline);

// ── Helpers ────────────────────────────────────────────────────────────────

function defaultAnalysisRecords(): AnalysisRecord[] {
  return [
    {
      id: 'analysis-001',
      collected_at: '2025-06-01T12:00:00Z',
      trigger_type: 'scheduled',
      metis_analyses: [{ type: 'pattern_match', confidence: 0.85 }],
      empath_responses: [{ type: 'emotional_context', sentiment: 'neutral' }],
      chronos_actions: [{ type: 'schedule_task', task_id: 'task-001' }],
      mediation_dispatched: false,
    },
    {
      id: 'analysis-002',
      collected_at: '2025-06-01T11:30:00Z',
      trigger_type: 'event',
      metis_analyses: [{ type: 'anomaly_detection', score: 0.92 }],
      empath_responses: [],
      chronos_actions: [],
      mediation_dispatched: true,
    },
  ];
}

function defaultTasks(): TaskSnapshot[] {
  return [
    {
      task_id: 'task-001',
      title: 'Process incoming data batch',
      status: 'running',
      priority: 'high',
      created_at: '2025-06-01T10:00:00Z',
      scheduled_at: '2025-06-01T12:00:00Z',
      assigned_to: 'chronos',
      description: 'Process the latest batch of incoming sensor data',
      tags: ['data', 'processing'],
    },
    {
      task_id: 'task-002',
      title: 'Consolidate memory',
      status: 'pending',
      priority: 'medium',
      created_at: '2025-06-01T09:00:00Z',
      scheduled_at: null,
      assigned_to: null,
      description: null,
      tags: [],
    },
  ];
}

function defaultGoals(): GoalSnapshot[] {
  return [
    {
      goal_id: 'goal-001',
      title: 'Optimize energy usage',
      description: 'Reduce average free energy by 15%',
      status: 'voting',
      priority: 'high',
      created_at: '2025-06-01T08:00:00Z',
      updated_at: '2025-06-01T09:00:00Z',
      votes_for: 3,
      votes_against: 1,
      outcome: null,
      proposed_by: 'metis',
    },
    {
      goal_id: 'goal-002',
      title: 'Explore new data source',
      description: null,
      status: 'proposed',
      priority: null,
      created_at: '2025-06-01T10:00:00Z',
      updated_at: null,
      votes_for: 0,
      votes_against: 0,
      outcome: null,
      proposed_by: 'explorer',
    },
  ];
}

function defaultEvents(): TimelineEvent[] {
  return [
    {
      id: 'event-001',
      event_type: 'analysis_completed',
      collected_at: '2025-06-01T12:00:00Z',
      source: 'metis',
      summary: 'Completed scheduled analysis of agent states',
      payload: { duration_ms: 2345, agents_analyzed: 5 },
    },
    {
      id: 'event-002',
      event_type: 'chronos_action',
      collected_at: '2025-06-01T11:55:00Z',
      source: 'chronos',
      summary: 'Dispatched task task-001 for processing',
      payload: { task_id: 'task-001', priority: 'high' },
    },
  ];
}

function defaultPaginatedResponse<T>(items: T[]) {
  return {
    items,
    total: items.length,
    page: 1,
    limit: 20,
    pages: 1,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('AutonomousPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
    mockGetAnalysisHistory.mockResolvedValue(defaultPaginatedResponse(defaultAnalysisRecords()));
    mockGetActiveTasks.mockResolvedValue(defaultPaginatedResponse(defaultTasks()));
    mockGetGoalPipeline.mockResolvedValue(defaultPaginatedResponse(defaultGoals()));
    mockGetEventsTimeline.mockResolvedValue(defaultPaginatedResponse(defaultEvents()));
  });

  afterEach(() => {
    cleanup();
  });

  it('renders the page title and tab navigation', async () => {
    render(<AutonomousPage />);

    expect(screen.getByText('Autonomous Runtime')).toBeInTheDocument();
    expect(screen.getByText('Analysis History')).toBeInTheDocument();
    expect(screen.getByText('Active Tasks')).toBeInTheDocument();
    expect(screen.getByText('Goal Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Events Timeline')).toBeInTheDocument();
  });

  it('loads and displays Analysis History tab by default', async () => {
    render(<AutonomousPage />);

    // The Analysis History tab is active by default; wait for its data to load
    await waitFor(() => {
      expect(mockGetAnalysisHistory).toHaveBeenCalledTimes(1);
    });

    // Analysis data trigger type should appear
    await waitFor(() => {
      expect(screen.getByText('scheduled')).toBeInTheDocument();
    });
  });

  it('shows loading spinner in Analysis History while data loads', () => {
    // Keep promise pending to observe loading state
    mockGetAnalysisHistory.mockReturnValue(new Promise(() => {}));

    render(<AutonomousPage />);

    expect(screen.getByText('Loading analysis history...')).toBeInTheDocument();
  });

  it('shows error state when an API call fails', async () => {
    mockGetAnalysisHistory.mockRejectedValue(new Error('Network error'));

    render(<AutonomousPage />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    // Error should include a retry button
    const retryButtons = screen.getAllByText('Retry');
    expect(retryButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('shows empty state when no analysis records exist', async () => {
    mockGetAnalysisHistory.mockResolvedValue(defaultPaginatedResponse([]));

    render(<AutonomousPage />);

    await waitFor(() => {
      expect(screen.getByText('No Analysis Records')).toBeInTheDocument();
    });
  });

  it('switches to Active Tasks tab and loads task data', async () => {
    render(<AutonomousPage />);

    // Click the Active Tasks tab
    const tasksTab = screen.getByText('Active Tasks');
    tasksTab.click();

    // Wait for the task data to load
    await waitFor(() => {
      expect(mockGetActiveTasks).toHaveBeenCalledTimes(1);
    });
  });

  it('shows empty state when no tasks exist', async () => {
    mockGetActiveTasks.mockResolvedValue(defaultPaginatedResponse([]));

    render(<AutonomousPage />);

    // Switch to tasks tab
    screen.getByText('Active Tasks').click();

    await waitFor(() => {
      expect(screen.getByText('No Active Tasks')).toBeInTheDocument();
    });
  });

  it('shows error state when tasks API fails', async () => {
    mockGetActiveTasks.mockRejectedValue(new Error('Task service unavailable'));

    render(<AutonomousPage />);

    // Switch to tasks tab
    screen.getByText('Active Tasks').click();

    await waitFor(() => {
      expect(screen.getByText('Task service unavailable')).toBeInTheDocument();
    });
  });

  it('switches to Goal Pipeline tab and loads goal data', async () => {
    render(<AutonomousPage />);

    // Click the Goal Pipeline tab
    screen.getByText('Goal Pipeline').click();

    await waitFor(() => {
      expect(mockGetGoalPipeline).toHaveBeenCalledTimes(1);
    });
  });

  it('shows empty state when no goals exist', async () => {
    mockGetGoalPipeline.mockResolvedValue(defaultPaginatedResponse([]));

    render(<AutonomousPage />);

    screen.getByText('Goal Pipeline').click();

    await waitFor(() => {
      expect(screen.getByText('No Goals in Pipeline')).toBeInTheDocument();
    });
  });

  it('switches to Events Timeline tab and loads event data', async () => {
    render(<AutonomousPage />);

    screen.getByText('Events Timeline').click();

    await waitFor(() => {
      expect(mockGetEventsTimeline).toHaveBeenCalledTimes(1);
    });
  });

  it('shows empty state when no events exist', async () => {
    mockGetEventsTimeline.mockResolvedValue(defaultPaginatedResponse([]));

    render(<AutonomousPage />);

    screen.getByText('Events Timeline').click();

    await waitFor(() => {
      expect(screen.getByText('No Timeline Events')).toBeInTheDocument();
    });
  });

  it('shows tab-specific description text', () => {
    render(<AutonomousPage />);

    // Default tab (analysis) description
    expect(
      screen.getByText(/Metis analysis records with Empath responses/)
    ).toBeInTheDocument();
  });

  it('description updates when switching tabs', async () => {
    render(<AutonomousPage />);

    // Default
    expect(
      screen.getByText(/Metis analysis records with Empath responses/)
    ).toBeInTheDocument();

    // Switch to tasks
    screen.getByText('Active Tasks').click();
    await waitFor(() => {
      expect(
        screen.getByText(/Chronos task snapshots and status/)
      ).toBeInTheDocument();
    });

    // Switch to goals
    screen.getByText('Goal Pipeline').click();
    await waitFor(() => {
      expect(
        screen.getByText(/Goal lifecycle: proposed/)
      ).toBeInTheDocument();
    });

    // Switch to events
    screen.getByText('Events Timeline').click();
    await waitFor(() => {
      expect(
        screen.getByText(/Chronological event feed/)
      ).toBeInTheDocument();
    });
  });

  it('calls all four API endpoints at least once when each tab is visited', async () => {
    render(<AutonomousPage />);

    // Visit each tab
    await waitFor(() => {
      expect(mockGetAnalysisHistory).toHaveBeenCalledTimes(1);
    });

    screen.getByText('Active Tasks').click();
    await waitFor(() => {
      expect(mockGetActiveTasks).toHaveBeenCalledTimes(1);
    });

    screen.getByText('Goal Pipeline').click();
    await waitFor(() => {
      expect(mockGetGoalPipeline).toHaveBeenCalledTimes(1);
    });

    screen.getByText('Events Timeline').click();
    await waitFor(() => {
      expect(mockGetEventsTimeline).toHaveBeenCalledTimes(1);
    });
  });
});
