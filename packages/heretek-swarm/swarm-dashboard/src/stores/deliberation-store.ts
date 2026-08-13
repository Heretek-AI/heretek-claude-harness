// Zustand store for one deliberation's live state.

import { create } from 'zustand';
import type {
  DeliberationDetail,
  DeliberationEvent,
  DeliberationStatus,
  FinalVerdict,
} from '../types/deliberation';

interface State {
  id: string | null;
  problem: string;
  status: DeliberationStatus;
  events: DeliberationEvent[];
  finalVerdict: FinalVerdict | null;
  reasoningByAgent: Record<string, string>;
  activeAgent: 'alpha' | 'beta' | 'charlie' | null;
  replayDone: boolean;
  error: string | null;
}

interface Actions {
  reset: (id: string, problem: string) => void;
  hydrate: (detail: DeliberationDetail) => void;
  applyEvent: (event: DeliberationEvent) => void;
  setReplayDone: (count: number) => void;
  setActiveAgent: (agent: State['activeAgent']) => void;
  setError: (msg: string) => void;
}

export const useDeliberationStore = create<State & Actions>((set) => ({
  id: null,
  problem: '',
  status: 'running',
  events: [],
  finalVerdict: null,
  reasoningByAgent: { alpha: '', beta: '', charlie: '' },
  activeAgent: null,
  replayDone: false,
  error: null,

  reset: (id, problem) =>
    set({
      id,
      problem,
      status: 'running',
      events: [],
      finalVerdict: null,
      reasoningByAgent: { alpha: '', beta: '', charlie: '' },
      activeAgent: null,
      replayDone: false,
      error: null,
    }),

  hydrate: (detail) =>
    set({
      id: detail.id,
      problem: detail.problem,
      status: detail.status,
      events: detail.events,
      finalVerdict: detail.final_verdict,
    }),

  applyEvent: (event) =>
    set((s) => {
      const events = [...s.events, event];
      const reasoningByAgent = { ...s.reasoningByAgent };

      if (event.kind === 'token') {
        const agent = event.payload.agent as string;
        const token = event.payload.token as string;
        reasoningByAgent[agent] = (reasoningByAgent[agent] ?? '') + token;
      } else if (event.kind === 'alpha_thinking') {
        return { events, activeAgent: 'alpha' };
      } else if (event.kind === 'beta_thinking') {
        return { events, activeAgent: 'beta' };
      } else if (event.kind === 'charlie_thinking') {
        return { events, activeAgent: 'charlie' };
      } else if (event.kind === 'completed') {
        const fv = event.payload as unknown as FinalVerdict;
        return { events, status: 'completed', finalVerdict: fv, activeAgent: null };
      } else if (event.kind === 'consensus_failed') {
        return { events, status: 'failed', activeAgent: null };
      }
      return { events, reasoningByAgent };
    }),

  setReplayDone: (_count) => set({ replayDone: true }),
  setActiveAgent: (agent) => set({ activeAgent: agent }),
  setError: (msg) => set({ error: msg }),
}));
