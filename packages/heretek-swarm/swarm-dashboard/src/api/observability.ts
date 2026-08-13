/**
 * API Client - Observability endpoints
 *
 * Provides access to LLM provider usage statistics and other observability
 * data from the swarm runtime.
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

export interface ProviderStats {
  total_requests: number;
  total_cost: number;
  total_tokens: number;
  models_used: Record<string, number>;
}

export interface ProviderStatsResponse {
  providers: Record<string, ProviderStats>;
  total_cost: number;
  total_requests: number;
  total_tokens: number;
}

// =============================================================================
// Observability API
// =============================================================================

/**
 * Fetch aggregate LLM provider usage statistics across all agents.
 *
 * Returns per-provider totals for requests, cost, and tokens, plus grand
 * totals.  Calls GET /api/observability/provider-stats which aggregates
 * from every registered AgentModelRouter.
 *
 * Returns zeroed-out totals (not an error) when no usage has been recorded.
 */
export async function fetchProviderStats(): Promise<ProviderStatsResponse> {
  const response = await api.get<ProviderStatsResponse>(
    '/api/observability/provider-stats',
  );
  return response.data;
}
