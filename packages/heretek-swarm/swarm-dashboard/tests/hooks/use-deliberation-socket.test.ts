import { describe, it, expect } from 'vitest';

describe('useDeliberationSocket', () => {
  it('exports a function', async () => {
    const mod = await import('../../src/hooks/use-deliberation-socket');
    expect(typeof mod.useDeliberationSocket).toBe('function');
  });
});
