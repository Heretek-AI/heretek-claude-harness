/**
 * Vitest global setup — extends Jest globals for @testing-library/react compatibility
 * and provides jest global aliases for legacy Jest-style test files.
 */
import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Bridge Jest globals → vitest for pre-existing test files written in Jest style.
// IMPORTANT: Do NOT overwrite vitest-native globals (describe, it, test, expect,
// beforeEach, afterEach). Vitest injects those automatically via globals: true.
//
// jest.fn(), jest.mock(), jest.spyOn(), jest.clearAllMocks(), etc. are bridged
// through `(global as any).jest = vi` and manual aliases below for Jest-only APIs.


(global as any).jest = vi;

// jest only: jest.requireActual / jest.requireMock → vitest equivalents
if (!(vi as any).requireActual) {
  (vi as any).requireActual = vi.importActual;
}
if (!(vi as any).requireMock) {
  (vi as any).requireMock = <T>(path: string): T => {
    // vitest mocks are hoisted; return the module as-is after mock resolution

    return require(path) as T;
  };
}

// Polyfill localStorage for jsdom — useWebSocket reads from it
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', {
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => { store.set(key, value); },
      removeItem: (key: string) => { store.delete(key); },
      clear: () => { store.clear(); },
      get length() { return store.size; },
      key: (index: number) => [...store.keys()][index] ?? null,
    },
    writable: true,
  });
}

// Polyfill ResizeObserver for jsdom — cmdk uses it for the popper-
// position calculations. Without it, every test that mounts a
// CommandPalette throws "ReferenceError: ResizeObserver is not defined".
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

// Polyfill scrollIntoView — cmdk's Command.List uses it to keep the
// highlighted item in view. jsdom doesn't implement it.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {};
}
