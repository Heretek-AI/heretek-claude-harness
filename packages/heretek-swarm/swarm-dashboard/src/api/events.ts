/**
 * API Client — Historian events endpoint
 *
 * Provides getHistorianEvents() for querying persisted domain events
 * from the HistorianAgent via GET /api/historian/events.
 */

import apiClient from './client';

// =============================================================================
// Types
// =============================================================================

/** A single structured domain event from the historian. */
export interface HistorianEvent {
  event_id: string;
  type: string;
  timestamp: string;
  agent_id: string;
  payload: Record<string, unknown>;
}

/** Optional filter parameters for querying historian events. */
export interface GetHistorianEventsParams {
  agent_id?: string;
  event_type?: string;
  since?: string;
  until?: string;
  limit?: number;
}

/** Response envelope from GET /api/historian/events. */
export interface GetHistorianEventsResponse {
  events: HistorianEvent[];
  mode: string;
}

// =============================================================================
// API function
// =============================================================================

/**
 * Fetch persisted domain events from the HistorianAgent.
 *
 * Returns `{ events: [], mode: 'error' }` on any transport or server
 * failure so callers never crash — callers should inspect the `mode`
 * field to decide whether to show an error state.
 */
export const getHistorianEvents = async (
  params?: GetHistorianEventsParams
): Promise<GetHistorianEventsResponse> => {
  try {
    const response = await apiClient.get<GetHistorianEventsResponse>(
      '/api/historian/events',
      { params }
    );
    return response.data;
  } catch (error) {
    console.error(
      'getHistorianEvents failed:',
      error instanceof Error ? error.message : error
    );
    return { events: [], mode: 'error' };
  }
};
