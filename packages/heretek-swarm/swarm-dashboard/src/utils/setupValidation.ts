/**
 * Setup Validation Utilities
 *
 * Provides functions for validating API connectivity,
 * WebSocket connections, and agent health checks.
 */

import type { ConnectionTestResult, AgentHealthResult } from '../stores/setupStore';

// =============================================================================
// Types
// =============================================================================

export interface ValidationResult {
  isValid: boolean;
  error?: string;
  details?: string;
}

// =============================================================================
// URL Validation
// =============================================================================

/**
 * Validates a URL format
 */
export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Validates and normalizes a URL (adds protocol if missing)
 */
export function normalizeUrl(url: string): string {
  let normalized = url.trim();

  // Add protocol if missing
  if (normalized && !normalized.startsWith('http://') && !normalized.startsWith('https://')) {
    normalized = `http://${normalized}`;
  }

  // Remove trailing slashes — intentionally safe pattern, not user-controlled input (S5852/SonarJS)
  normalized = normalized.replace(/\/+$/, '');

  return normalized;
}

/**
 * Derives WebSocket URL from HTTP URL
 */
export function deriveWsUrl(httpUrl: string): string {
  const normalized = normalizeUrl(httpUrl);
  return normalized.replace(/^http/, 'ws');
}

// =============================================================================
// API Connection Tests
// =============================================================================

/**
 * Tests API health endpoint connectivity
 */
export async function testApiHealth(apiUrl: string, apiKey?: string): Promise<ConnectionTestResult> {
  const startTime = Date.now();

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (apiKey) {
      headers['Authorization'] = `Bearer ${apiKey}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

    const response = await fetch(`${apiUrl}/api/health`, {
      method: 'GET',
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const latency = Date.now() - startTime;

    if (!response.ok) {
      return {
        success: false,
        latency,
        error: `HTTP ${response.status}: ${response.statusText}`,
        details: `Health endpoint returned status ${response.status}`,
      };
    }

    // Try to parse response for more details
    let details = '';
    try {
      const data = await response.json();
      details = typeof data === 'object' && data !== null ? JSON.stringify(data).slice(0, 200) : String(data);
    } catch {
      details = 'Health check passed';
    }

    return {
      success: true,
      latency,
      details,
    };
  } catch (error) {
    const latency = Date.now() - startTime;

    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        return {
          success: false,
          latency,
          error: 'Connection timed out',
          details: 'The request took longer than 10 seconds. Check if the server is accessible.',
        };
      }
      return {
        success: false,
        latency,
        error: error.message,
        details: 'Failed to connect to API health endpoint',
      };
    }

    return {
      success: false,
      latency,
      error: 'Unknown error occurred',
    };
  }
}

/**
 * Tests WebSocket connectivity
 */
export async function testWebSocket(wsUrl: string, apiKey?: string): Promise<ConnectionTestResult> {
  const startTime = Date.now();

  return new Promise((resolve) => {
    try {
      const wsEndpoint = apiKey
        ? `${wsUrl}/ws/dashboard?token=${encodeURIComponent(apiKey)}`
        : `${wsUrl}/ws/dashboard`;
      const ws = new WebSocket(wsEndpoint);
      let hasResponded = false;

      // Timeout after 10 seconds
      const timeoutId = setTimeout(() => {
        if (!hasResponded) {
          ws.close();
          resolve({
            success: false,
            latency: Date.now() - startTime,
            error: 'WebSocket connection timed out',
            details: 'Could not establish WebSocket connection within 10 seconds',
          });
        }
      }, 10000);

      ws.onopen = () => {
        hasResponded = true;
        clearTimeout(timeoutId);
        const latency = Date.now() - startTime;
        ws.close();
        resolve({
          success: true,
          latency,
          details: 'WebSocket connection established successfully',
        });
      };

      ws.onerror = () => {
        hasResponded = true;
        clearTimeout(timeoutId);
        resolve({
          success: false,
          latency: Date.now() - startTime,
          error: 'WebSocket connection failed',
          details: 'Failed to establish WebSocket connection. Check if WebSocket endpoint is enabled.',
        });
      };
    } catch (error) {
      const latency = Date.now() - startTime;
      resolve({
        success: false,
        latency,
        error: error instanceof Error ? error.message : 'Unknown error',
        details: 'Failed to create WebSocket connection',
      });
    }
  });
}

/**
 * Tests API key validity by calling a protected endpoint
 */
export async function testApiKey(apiUrl: string, apiKey: string): Promise<ConnectionTestResult> {
  const startTime = Date.now();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const response = await fetch(`${apiUrl}/api/config`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const latency = Date.now() - startTime;

    if (response.status === 401 || response.status === 403) {
      return {
        success: false,
        latency,
        error: 'Invalid API key',
        details: 'The provided API key was rejected by the server. Please check your key and try again.',
      };
    }

    if (!response.ok) {
      return {
        success: false,
        latency,
        error: `HTTP ${response.status}`,
        details: `API key test returned status ${response.status}`,
      };
    }

    return {
      success: true,
      latency,
      details: 'API key is valid',
    };
  } catch (error) {
    const latency = Date.now() - startTime;

    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        return {
          success: false,
          latency,
          error: 'Request timed out',
          details: 'The API key validation request timed out',
        };
      }
      return {
        success: false,
        latency,
        error: error.message,
        details: 'Failed to validate API key',
      };
    }

    return {
      success: false,
      latency,
      error: 'Unknown error occurred',
    };
  }
}

// =============================================================================
// Agent Health Checks
// =============================================================================

/**
 * Fetches agent instances and their health status
 */
export async function checkAgentHealth(apiUrl: string, apiKey?: string): Promise<AgentHealthResult[]> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    const response = await fetch(`${apiUrl}/api/agents`, {
      method: 'GET',
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      // Return a single "unknown" result if we can't reach the endpoint
      if (response.status === 401 || response.status === 403) {
        return [{
          agentId: 'auth',
          agentType: 'authentication',
          status: 'unknown',
          error: 'Authentication required. Please check your API key.',
        }];
      }
      return [{
        agentId: 'api',
        agentType: 'api',
        status: 'unknown',
        error: `API returned status ${response.status}`,
      }];
    }

    const data = await response.json();
    const instances = data.instances || data.agents || [];

    return instances.map((instance: Record<string, unknown>): AgentHealthResult => {
      const actorStatus = (instance.actor_status as Record<string, unknown>) || {};
      return {
        agentId: (instance.instance_id || instance.id) as string,
        agentType: (instance.agent_type || instance.type) as string,
        status: mapAgentStatus((instance.state || instance.status) as string),
        messageCount: actorStatus.message_count as number | undefined,
        lastActivity: actorStatus.last_activity as string | undefined,
        error: (actorStatus.error_count as number) > 0
          ? `${actorStatus.error_count} errors recorded`
          : undefined,
      };
    });
  } catch (error) {
    return [{
      agentId: 'connection',
      agentType: 'connection',
      status: 'offline',
      error: error instanceof Error ? error.message : 'Failed to check agent health',
    }];
  }
}

/**
 * Maps string status to AgentHealthResult status
 */
function mapAgentStatus(status: string): 'online' | 'offline' | 'degraded' | 'unknown' {
  const statusMap: Record<string, 'online' | 'offline' | 'degraded' | 'unknown'> = {
    running: 'online',
    deployed: 'online',
    available: 'online',
    active: 'online',
    stopped: 'offline',
    error: 'degraded',
    degraded: 'degraded',
    unknown: 'unknown',
  };

  return statusMap[status?.toLowerCase()] || 'unknown';
}

// =============================================================================
// Database Connection Tests
// =============================================================================

/**
 * Tests database connectivity through the API health endpoint
 * Returns details about database services
 */
export async function testDatabaseConnection(apiUrl: string, apiKey?: string): Promise<ConnectionTestResult> {
  const startTime = Date.now();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const response = await fetch(`${apiUrl}/api/health`, {
      method: 'GET',
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const latency = Date.now() - startTime;

    if (!response.ok) {
      return {
        success: false,
        latency,
        error: `HTTP ${response.status}`,
        details: 'Could not retrieve health status',
      };
    }

    const data = await response.json();

    // Check database services from health response
    const dbServices = ['postgres', 'redis', 'qdrant', 'database'];
    const dbResults: string[] = [];
    let allHealthy = true;
    let anyHealthy = false;

    for (const service of dbServices) {
      const serviceData = data[service] || data[service + '_db'];
      if (serviceData) {
        const status = serviceData.status || serviceData;
        const serviceHealthy = status === 'healthy' || status === true;

        if (serviceHealthy) {
          anyHealthy = true;
          dbResults.push(`${service}: ✓ connected`);
        } else {
          allHealthy = false;
          dbResults.push(`${service}: ✗ ${serviceData.error || 'unavailable'}`);
        }
      }
    }

    if (dbResults.length === 0) {
      // No specific database info in health response
      return {
        success: true,
        latency,
        details: 'Database connectivity unknown (no detailed status available)',
      };
    }

    return {
      success: allHealthy || anyHealthy,
      latency,
      details: dbResults.join('\n'),
      error: allHealthy ? undefined : 'Some database services are unavailable',
    };
  } catch (error) {
    const latency = Date.now() - startTime;

    return {
      success: false,
      latency,
      error: error instanceof Error ? error.message : 'Failed to test database connection',
      details: 'Could not connect to API to check database status',
    };
  }
}

/**
 * Validates API host input
 */
export function validateApiHost(host: string): ValidationResult {
  const trimmed = host.trim();

  if (!trimmed) {
    return {
      isValid: false,
      error: 'API host is required',
    };
  }

  const normalized = normalizeUrl(trimmed);

  if (!isValidUrl(normalized)) {
    return {
      isValid: false,
      error: 'Invalid URL format',
    };
  }

  // Check for localhost in production warning
  if (normalized.includes('localhost') || normalized.includes('127.0.0.1')) {
    return {
      isValid: true,
      details: 'Using local development server',
    };
  }

  return { isValid: true };
}

/**
 * Validates API key input
 */
export function validateApiKey(key: string): ValidationResult {
  const trimmed = key.trim();

  if (!trimmed) {
    return {
      isValid: false,
      error: 'API key is required',
    };
  }

  if (trimmed.length < 8) {
    return {
      isValid: false,
      error: 'API key is too short',
    };
  }

  return { isValid: true };
}

// =============================================================================
// Debounced Validation
// =============================================================================

/**
 * Creates a debounced validation function
 */
export function createDebouncedValidation<T>(
  fn: (value: T) => Promise<ValidationResult>,
  delay: number = 500
): (value: T) => Promise<ValidationResult> {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (value: T) => {
    return new Promise((resolve) => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      timeoutId = setTimeout(async () => {
        const result = await fn(value);
        resolve(result);
      }, delay);
    });
  };
}
