import { describe, it, expect, beforeEach } from 'vitest';
import { useDeliberationStore } from '../../src/stores/deliberation-store';
import type { DeliberationEvent } from '../../src/types/deliberation';

const evt = (
  kind: DeliberationEvent['kind'],
  payload: Record<string, unknown> = {},
): DeliberationEvent => ({
  seq: 0,
  ts: Date.now(),
  kind,
  payload,
});

describe('deliberationStore', () => {
  beforeEach(() => {
    useDeliberationStore.getState().reset('test-id', 'test problem');
  });

  it('resets to initial state', () => {
    const s = useDeliberationStore.getState();
    expect(s.id).toBe('test-id');
    expect(s.problem).toBe('test problem');
    expect(s.status).toBe('running');
    expect(s.events).toEqual([]);
    expect(s.finalVerdict).toBeNull();
    expect(s.replayDone).toBe(false);
    expect(s.error).toBeNull();
  });

  it('hydrates from detail', () => {
    const { hydrate } = useDeliberationStore.getState();
    hydrate({
      id: 'hydrated-id',
      problem: 'hydrated problem',
      status: 'completed',
      events: [],
      final_verdict: null,
    });
    const s = useDeliberationStore.getState();
    expect(s.id).toBe('hydrated-id');
    expect(s.problem).toBe('hydrated problem');
    expect(s.status).toBe('completed');
  });

  it('appends token events and builds reasoning', () => {
    const { applyEvent } = useDeliberationStore.getState();
    applyEvent(evt('token', { agent: 'alpha', token: 'hello ' }));
    applyEvent(evt('token', { agent: 'alpha', token: 'world' }));
    expect(useDeliberationStore.getState().events).toHaveLength(2);
    expect(useDeliberationStore.getState().reasoningByAgent.alpha).toBe('hello world');
  });

  it('sets activeAgent on alpha_thinking', () => {
    useDeliberationStore.getState().applyEvent(evt('alpha_thinking'));
    expect(useDeliberationStore.getState().activeAgent).toBe('alpha');
  });

  it('sets activeAgent on beta_thinking', () => {
    useDeliberationStore.getState().applyEvent(evt('beta_thinking'));
    expect(useDeliberationStore.getState().activeAgent).toBe('beta');
  });

  it('sets activeAgent on charlie_thinking', () => {
    useDeliberationStore.getState().applyEvent(evt('charlie_thinking'));
    expect(useDeliberationStore.getState().activeAgent).toBe('charlie');
  });

  it('marks completed on completed event', () => {
    useDeliberationStore.getState().applyEvent(
      evt('completed', {
        decision: 'approved',
        summary: 'ok',
        votes: {},
        rounds: 1,
      }),
    );
    const s = useDeliberationStore.getState();
    expect(s.status).toBe('completed');
    expect(s.finalVerdict).not.toBeNull();
    expect(s.activeAgent).toBeNull();
  });

  it('marks failed on consensus_failed event', () => {
    useDeliberationStore.getState().applyEvent(evt('consensus_failed'));
    const s = useDeliberationStore.getState();
    expect(s.status).toBe('failed');
    expect(s.activeAgent).toBeNull();
  });

  it('sets active agent directly', () => {
    useDeliberationStore.getState().setActiveAgent('beta');
    expect(useDeliberationStore.getState().activeAgent).toBe('beta');
  });

  it('sets replay done', () => {
    useDeliberationStore.getState().setReplayDone(5);
    expect(useDeliberationStore.getState().replayDone).toBe(true);
  });

  it('sets error', () => {
    useDeliberationStore.getState().setError('something went wrong');
    expect(useDeliberationStore.getState().error).toBe('something went wrong');
  });
});
