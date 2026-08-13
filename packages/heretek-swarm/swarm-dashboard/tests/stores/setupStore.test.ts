import { describe, it, expect, beforeEach } from 'vitest';
import { useSetupStore } from '../../src/stores/setupStore';

describe('setupStore', () => {
  beforeEach(() => {
    useSetupStore.getState().resetSetup();
  });

  it('sets config', () => {
    useSetupStore.getState().setConfig({
      apiHost: 'http://localhost:8000',
      apiKey: 'test-key',
      wsHost: 'ws://localhost:8000',
    });
    const s = useSetupStore.getState();
    expect(s.config.apiHost).toBe('http://localhost:8000');
    expect(s.config.apiKey).toBe('test-key');
    expect(s.config.wsHost).toBe('ws://localhost:8000');
  });

  it('sets current step', () => {
    useSetupStore.getState().setStep('api-key');
    expect(useSetupStore.getState().currentStep).toBe('api-key');
  });

  it('sets rerunning', () => {
    useSetupStore.getState().setRerunning(true);
    expect(useSetupStore.getState().isRerunning).toBe(true);
  });

  it('resets setup', () => {
    useSetupStore.getState().setConfig({
      apiHost: 'http://localhost:8000',
      apiKey: 'test-key',
      wsHost: 'ws://localhost:8000',
    });
    useSetupStore.getState().resetSetup();
    const s = useSetupStore.getState();
    expect(s.config.apiHost).toBe('');
    expect(s.config.apiKey).toBe('');
    expect(s.currentStep).toBe('welcome');
    expect(s.isConfigured).toBe(false);
  });

  it('completes setup and persists to localStorage', () => {
    useSetupStore.getState().setConfig({
      apiHost: 'http://example.com',
      apiKey: 'secret',
      wsHost: 'ws://example.com',
    });
    useSetupStore.getState().completeSetup();
    const s = useSetupStore.getState();
    expect(s.isConfigured).toBe(true);
    expect(s.currentStep).toBe('complete');
    expect(localStorage.getItem('swarm_api_host')).toBe('http://example.com');
    expect(localStorage.getItem('api_key')).toBe('secret');
    expect(localStorage.getItem('swarm_configured')).toBe('true');
  });
});
