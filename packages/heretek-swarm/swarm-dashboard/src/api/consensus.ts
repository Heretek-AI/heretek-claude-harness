/**
 * API Client - Consensus endpoints
 *
 * Provides typed functions for interacting with the consensus API:
 * - Listing active consensus rounds
 * - Creating new consensus processes
 * - Submitting votes
 * - Retrieving consensus results and history
 * - Aggregating consensus decisions
 */

import { api } from './client';

// =============================================================================
// Types
// =============================================================================

/** Consensus round state machine values */
export type ConsensusState =
  | 'gathering'
  | 'voting'
  | 'aggregating'
  | 'completed'
  | 'failed';

/** An individual agent vote in a consensus round */
export interface ConsensusVote {
  agent_id: string;
  decision: string;
  confidence: number;
  timestamp: string;
  metadata: Record<string, unknown>;
}

/** Active consensus round summary (from GET /api/consensus) */
export interface ConsensusRoundSummary {
  id: string;
  state: ConsensusState;
  topic: string;
  vote_count: number;
  created_at: string;
  deadline: string | null;
}

/** Full consensus round detail (from GET /api/consensus/:id) */
export interface ConsensusRoundDetail {
  id: string;
  topic: string;
  state: ConsensusState;
  votes: ConsensusVote[];
  decision: string | null;
  confidence: number | null;
  red_flags: string[];
  created_at: string;
  completed_at: string | null;
  metadata: Record<string, unknown>;
}

/** Completed consensus round from history */
export interface ConsensusHistoryEntry {
  id: string;
  topic: string;
  decision: string | null;
  confidence: number | null;
  vote_count: number;
  completed_at: string | null;
  red_flags: string[];
}

/** Consensus configuration parameters */
export interface ConsensusConfig {
  ahead_by_k: number;
  min_votes: number;
  red_flag_threshold: number;
  voting_timeout_seconds: number;
}

/** Aggregated consensus result */
export interface ConsensusResult {
  id: string;
  decision: string;
  confidence: number;
  state: ConsensusState;
  votes: ConsensusVote[];
  red_flags: string[];
  completed_at: string;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get all active consensus rounds.
 *
 * Calls GET /api/consensus — returns rounds in gathering or voting state.
 */
export async function getActiveConsensusRounds(): Promise<{
  consensus_rounds: ConsensusRoundSummary[];
  total: number;
}> {
  const response = await api.get<{
    consensus_rounds: ConsensusRoundSummary[];
    total: number;
  }>('/api/consensus');
  return response.data;
}

/**
 * Get completed consensus rounds history.
 *
 * Calls GET /api/consensus/history — sorted by completion time (most recent first).
 *
 * @param limit - Maximum number of results (default: 50)
 */
export async function getConsensusHistory(
  limit: number = 50
): Promise<{ consensus_history: ConsensusHistoryEntry[]; total: number }> {
  const response = await api.get<{
    consensus_history: ConsensusHistoryEntry[];
    total: number;
  }>(`/api/consensus/history?limit=${limit}`);
  return response.data;
}

/**
 * Get details of a specific consensus round.
 *
 * Calls GET /api/consensus/:consensusId — includes all votes and metadata.
 */
export async function getConsensusRound(
  consensusId: string
): Promise<ConsensusRoundDetail> {
  const response = await api.get<ConsensusRoundDetail>(
    `/api/consensus/${consensusId}`
  );
  return response.data;
}

/**
 * Create a new consensus round.
 *
 * Calls POST /api/consensus — requires 'create' permission.
 */
export async function createConsensusRound(
  topic: string,
  description: string = ''
): Promise<{
  id: string;
  topic: string;
  description: string;
  state: ConsensusState;
  created_at: string;
}> {
  const response = await api.post<{
    id: string;
    topic: string;
    description: string;
    state: ConsensusState;
    created_at: string;
  }>('/api/consensus', { topic, description });
  return response.data;
}

/**
 * Submit a vote for a consensus round.
 *
 * Calls POST /api/consensus/:consensusId/vote — requires 'vote' permission.
 *
 * @param consensusId - The consensus round to vote on
 * @param decision - The agent's decision/answer
 * @param confidence - Confidence level (0.0 to 1.0)
 * @param metadata - Optional additional metadata
 */
export async function submitVote(
  consensusId: string,
  decision: string,
  confidence: number,
  metadata?: Record<string, unknown>
): Promise<{
  status: string;
  consensus_id: string;
  agent_id: string;
  vote_count: number;
  current_state: ConsensusState;
}> {
  const response = await api.post<{
    status: string;
    consensus_id: string;
    agent_id: string;
    vote_count: number;
    current_state: ConsensusState;
  }>(`/api/consensus/${consensusId}/vote`, {
    decision,
    confidence,
    metadata,
  });
  return response.data;
}

/**
 * Aggregate votes and determine consensus decision.
 *
 * Calls POST /api/consensus/:consensusId/aggregate — requires 'create' permission.
 */
export async function aggregateConsensus(
  consensusId: string
): Promise<ConsensusResult> {
  const response = await api.post<ConsensusResult>(
    `/api/consensus/${consensusId}/aggregate`
  );
  return response.data;
}

/**
 * Get results of a completed consensus round.
 *
 * Calls GET /api/consensus/:consensusId/results.
 */
export async function getConsensusResults(
  consensusId: string
): Promise<{
  id: string;
  topic: string;
  decision: string | null;
  confidence: number | null;
  state: ConsensusState;
  votes: ConsensusVote[];
  red_flags: string[];
  completed_at: string | null;
  message?: string;
}> {
  const response = await api.get<{
    id: string;
    topic: string;
    decision: string | null;
    confidence: number | null;
    state: ConsensusState;
    votes: ConsensusVote[];
    red_flags: string[];
    completed_at: string | null;
    message?: string;
  }>(`/api/consensus/${consensusId}/results`);
  return response.data;
}

/**
 * Cancel an active consensus round.
 *
 * Calls DELETE /api/consensus/:consensusId — requires 'create' permission.
 */
export async function cancelConsensus(
  consensusId: string
): Promise<{ status: string; consensus_id: string }> {
  const response = await api.delete<{ status: string; consensus_id: string }>(
    `/api/consensus/${consensusId}`
  );
  return response.data;
}

/**
 * Get current consensus configuration.
 *
 * Calls GET /api/consensus/config.
 */
export async function getConsensusConfig(): Promise<ConsensusConfig> {
  const response = await api.get<ConsensusConfig>('/api/consensus/config');
  return response.data;
}
