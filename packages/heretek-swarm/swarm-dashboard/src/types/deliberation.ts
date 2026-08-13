// Shared types for the deliberation UI.
// These mirror the Pydantic models in tier1/deliberation/state.py.

export type AgentName = 'alpha' | 'beta' | 'charlie' | 'steward';
export type VerdictPosition = 'approve' | 'reject' | 'challenge' | 'abstain';
export type FinalDecision = 'approved' | 'rejected' | 'needs-revision' | 'no-consensus';
export type EventKind =
  | 'started'
  | 'alpha_thinking'
  | 'alpha_verdict'
  | 'beta_thinking'
  | 'beta_verdict'
  | 'charlie_thinking'
  | 'charlie_verdict'
  | 'steward_feedback'
  | 'user_interjection'
  | 'token'
  | 'consensus_reached'
  | 'consensus_failed'
  | 'completed';
export type DeliberationStatus = 'running' | 'completed' | 'failed';

export interface AgentVerdict {
  agent: AgentName;
  position: VerdictPosition;
  confidence: number;
  concerns: string[];
  reasoning: string;
}

export interface FinalVerdict {
  decision: FinalDecision;
  summary: string;
  votes: Record<string, AgentVerdict>;
  rounds: number;
}

export interface DeliberationEvent {
  seq: number;
  ts: number;
  kind: EventKind;
  payload: Record<string, unknown>;
}

export interface DeliberationSummary {
  id: string;
  problem: string;
  status: DeliberationStatus;
  created_at: number;
}

export interface DeliberationDetail {
  id: string;
  problem: string;
  status: DeliberationStatus;
  final_verdict: FinalVerdict | null;
  events: DeliberationEvent[];
}
