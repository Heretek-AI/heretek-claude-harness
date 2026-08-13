/**
 * Zustand Debug Middleware
 *
 * Provides state transition logging for debugging.
 * Logs previous state, next state, and action type.
 * Only outputs when Developer Mode is enabled.
 */

import { StateCreator } from 'zustand';
import createLogger from '../../utils/logger';

const logger = createLogger('ZustandDebug');

export interface DebugMiddlewareOptions {
  enabled?: boolean;
  logToConsole?: boolean;
  logToWindow?: boolean;
  skipActions?: string[];
}

function isDeveloperMode(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem('developer_mode') === 'true';
}

/**
 * Debug middleware for Zustand stores
 *
 * Wraps the set function to log state transitions.
 *
 * @param config - The Zustand state creator
 * @param options - Debug middleware options
 * @returns Wrapped state creator with debug logging
 */
export function withDebugMiddleware<T extends object>(
  config: StateCreator<T, [], []>,
  options: DebugMiddlewareOptions = {}
): StateCreator<T, [], []> {
  const {
    enabled = true,
    logToConsole = true,
    logToWindow = true,
    skipActions = [],
  } = options;

  return (set, get, api) => {
    const originalSet = set;

    const setWithDebug = (
      partial: T | Partial<T> | ((state: T) => T | Partial<T>),
      replace?: boolean,
      actionType?: string
    ) => {
      const currentState = get();

      // Call original set. Cast replace to the non-replacing overload's type
      // (false | undefined): at runtime the flag is forwarded unchanged; the
      // cast only satisfies zustand's overloaded set() signature.
      originalSet(partial, replace as false | undefined);

      // Get new state after update
      const nextState = get();

      // Only log if enabled and in developer mode
      if (!enabled || !isDeveloperMode()) return;

      // Skip logging for specified actions
      const actionName = actionType || 'setState';
      if (skipActions.includes(actionName)) return;

      // Calculate what changed
      const changes: Record<string, { before: unknown; after: unknown }> = {};
      const allKeys = new Set([
        ...Object.keys(currentState),
        ...Object.keys(nextState),
      ]);

      for (const key of allKeys) {
        const prevValue = currentState[key as keyof typeof currentState];
        const nextValue = nextState[key as keyof typeof nextState];

        if (JSON.stringify(prevValue) !== JSON.stringify(nextValue)) {
          changes[key] = { before: prevValue, after: nextValue };
        }
      }

      const transitionData = {
        timestamp: new Date().toISOString(),
        actionType: actionName,
        previousState: currentState,
        nextState,
        changes,
      };

      // Log to console
      if (logToConsole) {
        logger.debug(`State transition: ${actionName}`, {
          changes,
          previousState: currentState,
          nextState,
        });
      }

      // Dispatch event for DebugPanel
      if (logToWindow && typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('state-transition', { detail: transitionData })
        );
      }
    };

    return config(setWithDebug, get, api);
  };
}

/**
 * Log state transition manually
 */
export function logStateTransition(
  actionType: string,
  previousState: Record<string, unknown>,
  nextState: Record<string, unknown>
) {
  if (!isDeveloperMode()) return;

  const changes: Record<string, { before: unknown; after: unknown }> = {};
  const allKeys = new Set([...Object.keys(previousState), ...Object.keys(nextState)]);

  for (const key of allKeys) {
    const prevValue = previousState[key];
    const nextValue = nextState[key];

    if (JSON.stringify(prevValue) !== JSON.stringify(nextValue)) {
      changes[key] = { before: prevValue, after: nextValue };
    }
  }

  const transitionData = {
    timestamp: new Date().toISOString(),
    actionType,
    previousState,
    nextState,
    changes,
  };

  logger.debug(`State transition: ${actionType}`, { changes, previousState, nextState });

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('state-transition', { detail: transitionData }));
  }
}

export default withDebugMiddleware;
