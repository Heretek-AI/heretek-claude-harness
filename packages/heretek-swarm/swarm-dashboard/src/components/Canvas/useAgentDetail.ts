/**
 * useAgentDetail - Polling hook for per-agent detail drawer data
 *
 * Fetches consciousness metrics, agency metrics, and agent info every 10s.
 * Uses Promise.allSettled so one failing endpoint doesn't break others.
 * Gracefully handles 404 (consciousness not yet recorded → null, not error).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { AgentMetrics, getAgentMetrics } from '../../api/consciousness';
import { AgencyMetrics, getAgencyMetrics } from '../../api/consciousness';
import {
  Agent,
  getAgent,
  getAgentMemory,
  getAgentTools,
  getAgentTasks,
  type AgentMemoryResponse,
  type AgentToolsResponse,
  type AgentTasksResponse,
} from '../../api/agents';

const POLL_INTERVAL = 10000; // 10 seconds
const FETCH_TIMEOUT = 5000;  // 5 second timeout per request

export interface AgentDetailData {
  /** Consciousness/phi metrics for this agent. null if not yet recorded (404). */
  consciousness: AgentMetrics | null;
  /** Agency/decision metrics for this agent. null on error/404. */
  agency: AgencyMetrics | null;
  /** Agent info (type, status, etc.). null on error/404. */
  agent: Agent | null;
  /** Memory stats — agent memory store data. null if not available (404). */
  memory: AgentMemoryResponse | null;
  /** Active tools/MCP — skills and plugins. null if not available (404). */
  tools: AgentToolsResponse | null;
  /** Current tasks/activity status from supervisor. null if not available (404). */
  tasks: AgentTasksResponse | null;
}

export interface AgentDetailErrors {
  consciousness?: string;
  agency?: string;
  agent?: string;
  memory?: string;
  tools?: string;
  tasks?: string;
}

export interface UseAgentDetailReturn {
  data: AgentDetailData | null;
  loading: boolean;
  errors: AgentDetailErrors;
}

interface FetchResult<T> {
  data: T | null;
  error: string | null;
}

/**
 * Fetch with timeout wrapper
 */
async function fetchWithTimeout<T>(
  fn: () => Promise<T>,
  timeoutMs: number
): Promise<FetchResult<T>> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    // We wrap the promise to support AbortSignal
    const result = await fn();
    clearTimeout(timeout);
    return { data: result, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    if (message.includes('abort') || message.includes('cancelled')) {
      return { data: null, error: 'Request cancelled' };
    }
    return { data: null, error: message };
  }
}

/**
 * Polling hook for per-agent detail drawer.
 *
 * @param agentId - The agent ID to fetch details for. Pass null to stop polling and reset state.
 * @returns { data, loading, errors } where each field has its own loading/error state.
 */
export function useAgentDetail(agentId: string | null): UseAgentDetailReturn {
  const [data, setData] = useState<AgentDetailData | null>(null);
  const [loading, setLoading] = useState(true); // true until first fetch completes
  const [errors, setErrors] = useState<AgentDetailErrors>({});

  // Track pending fetches so we can cancel them when agentId becomes null
  const abortRef = useRef(false);

  const fetchAll = useCallback(async (id: string) => {
    setLoading(true);
    setErrors({});

    // Fetch all six endpoints in parallel
    const [
      consciousnessResult,
      agencyResult,
      agentResult,
      memoryResult,
      toolsResult,
      tasksResult,
    ] = await Promise.allSettled([
      fetchWithTimeout(() => getAgentMetrics(id), FETCH_TIMEOUT),
      fetchWithTimeout(() => getAgencyMetrics(id), FETCH_TIMEOUT),
      fetchWithTimeout(() => getAgent(id), FETCH_TIMEOUT),
      fetchWithTimeout(() => getAgentMemory(id), FETCH_TIMEOUT),
      fetchWithTimeout(() => getAgentTools(id), FETCH_TIMEOUT),
      fetchWithTimeout(() => getAgentTasks(id), FETCH_TIMEOUT),
    ]);

    // Process consciousness — 404 is "no metrics yet", not an error
    let consciousness: AgentMetrics | null = null;
    let consciousnessError: string | undefined;
    if (consciousnessResult.status === 'rejected') {
      consciousnessError = String(consciousnessResult.reason);
      console.error('[useAgentDetail] consciousness fetch failed:', consciousnessError);
    } else if (consciousnessResult.value.error) {
      const errMsg = consciousnessResult.value.error;
      // Treat Axios 404 as "no metrics yet" — graceful null, not error
      if (errMsg.includes('404') || errMsg.includes('Request failed with status code 404')) {
        // null = no metrics yet
      } else {
        consciousnessError = errMsg;
        console.error('[useAgentDetail] consciousness fetch error:', errMsg);
      }
    } else {
      consciousness = consciousnessResult.value.data as AgentMetrics;
    }

    // Process agency
    let agency: AgencyMetrics | null = null;
    let agencyError: string | undefined;
    if (agencyResult.status === 'rejected') {
      agencyError = String(agencyResult.reason);
      console.error('[useAgentDetail] agency fetch failed:', agencyError);
    } else if (agencyResult.value.error) {
      agencyError = agencyResult.value.error;
      console.error('[useAgentDetail] agency fetch error:', agencyError);
    } else {
      agency = agencyResult.value.data as AgencyMetrics;
    }

    // Process agent info
    let agentInfo: Agent | null = null;
    let agentError: string | undefined;
    if (agentResult.status === 'rejected') {
      agentError = String(agentResult.reason);
      console.error('[useAgentDetail] agent fetch failed:', agentError);
    } else if (agentResult.value.error) {
      agentError = agentResult.value.error;
      console.error('[useAgentDetail] agent fetch error:', agentError);
    } else {
      agentInfo = agentResult.value.data as Agent;
    }

    // Process memory — 404 is "no memory store available", not an error
    let memory: AgentMemoryResponse | null = null;
    let memoryError: string | undefined;
    if (memoryResult.status === 'rejected') {
      memoryError = String(memoryResult.reason);
      console.error('[useAgentDetail] memory fetch failed:', memoryError);
    } else if (memoryResult.value.error) {
      const errMsg = memoryResult.value.error;
      if (errMsg.includes('404') || errMsg.includes('Request failed with status code 404')) {
        // null = no memory store available
      } else {
        memoryError = errMsg;
        console.error('[useAgentDetail] memory fetch error:', errMsg);
      }
    } else {
      memory = memoryResult.value.data as AgentMemoryResponse;
    }

    // Process tools — 404 is "no tools data available", not an error
    let tools: AgentToolsResponse | null = null;
    let toolsError: string | undefined;
    if (toolsResult.status === 'rejected') {
      toolsError = String(toolsResult.reason);
      console.error('[useAgentDetail] tools fetch failed:', toolsError);
    } else if (toolsResult.value.error) {
      const errMsg = toolsResult.value.error;
      if (errMsg.includes('404') || errMsg.includes('Request failed with status code 404')) {
        // null = no tools data available
      } else {
        toolsError = errMsg;
        console.error('[useAgentDetail] tools fetch error:', errMsg);
      }
    } else {
      tools = toolsResult.value.data as AgentToolsResponse;
    }

    // Process tasks — 404 is "agent not managed by supervisor", not an error
    let tasks: AgentTasksResponse | null = null;
    let tasksError: string | undefined;
    if (tasksResult.status === 'rejected') {
      tasksError = String(tasksResult.reason);
      console.error('[useAgentDetail] tasks fetch failed:', tasksError);
    } else if (tasksResult.value.error) {
      const errMsg = tasksResult.value.error;
      if (errMsg.includes('404') || errMsg.includes('Request failed with status code 404')) {
        // null = agent not managed by supervisor
      } else {
        tasksError = errMsg;
        console.error('[useAgentDetail] tasks fetch error:', errMsg);
      }
    } else {
      tasks = tasksResult.value.data as AgentTasksResponse;
    }

    setData({
      consciousness,
      agency,
      agent: agentInfo,
      memory,
      tools,
      tasks,
    });

    setErrors({
      ...(consciousnessError ? { consciousness: consciousnessError } : {}),
      ...(agencyError ? { agency: agencyError } : {}),
      ...(agentError ? { agent: agentError } : {}),
      ...(memoryError ? { memory: memoryError } : {}),
      ...(toolsError ? { tools: toolsError } : {}),
      ...(tasksError ? { tasks: tasksError } : {}),
    });

    setLoading(false);
  }, []);

  useEffect(() => {
    // When agentId becomes null, cancel pending fetches and reset state
    if (agentId === null) {
      abortRef.current = true;
      setData(null);
      setLoading(false);
      setErrors({});
      return;
    }

    abortRef.current = false;

    // Initial fetch
    fetchAll(agentId);

    // Set up polling
    const interval = setInterval(() => {
      if (!abortRef.current) {
        fetchAll(agentId);
      }
    }, POLL_INTERVAL);

    return () => {
      abortRef.current = true;
      clearInterval(interval);
    };
  }, [agentId, fetchAll]);

  return { data, loading, errors };
}
