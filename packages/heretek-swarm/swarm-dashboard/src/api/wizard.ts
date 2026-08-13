/**
 * Wizard API Client
 *
 * API client functions for the Configuration Wizard endpoints.
 * Provides typed access to wizard configuration, provider validation, etc.
 */

// =============================================================================
// Types
// =============================================================================

export interface Provider {
  id: string;
  name: string;
  type: string;
  icon: string;
  description: string;
  default_model: string;
  supports_streaming: boolean;
  supports_function_calling: boolean;
  supports_vision: boolean;
  requires_api_key: boolean;
  api_key_label: string;
  api_key_env_var: string;
  base_url: string;
  color: string;
}

export interface AgentTier {
  id: string;
  name: string;
  description: string;
  agent_count: number;
  agents: string[];
  memory_enabled: boolean;
  consciousness_enabled: boolean;
}

export interface ConfigStatus {
  wizard_completed: boolean;
  wizard_state: {
    providers_configured: string[];
    config: Record<string, unknown>;
  };
  database_configured: {
    providers: Array<{
      id: string;
      name: string;
      type: string;
      is_enabled: boolean;
      is_default: boolean;
    }>;
    total_providers: number;
  };
  system_config: {
    database: boolean;
    redis: boolean;
    qdrant: boolean;
  };
  needs_setup: {
    providers: boolean;
    agents: boolean;
    api_keys: boolean;
  };
}

export interface ValidationResult {
  valid: boolean;
  error?: string;
  provider_id?: string;
  message?: string;
  available_models?: string[];
}

export interface ProviderConfig {
  provider_id: string;
  api_key?: string;
  model?: string;
  base_url?: string;
  is_default?: boolean;
  extra_config?: Record<string, unknown>;
}

export interface WizardConfig {
  providers: ProviderConfig[];
  tier: string;
  preferences?: {
    streaming?: boolean;
    function_calling?: boolean;
    vision?: boolean;
  };
}

export interface SubmitResult {
  success: boolean;
  providers_created: Array<{
    id: string;
    name: string;
    type: string;
    model: string;
  }>;
  config: {
    tier?: string;
    agent_count?: number;
  };
  errors: string[];
}

// Infrastructure types
export interface InfrastructureConfig {
  id: string;
  service: string;
  host: string;
  port: number;
  connection_url?: string;
  is_enabled: boolean;
  health_status: 'healthy' | 'unhealthy' | 'unknown' | 'degraded';
  last_health_check?: string;
  health_check_latency_ms?: number;
  health_check_error?: string;
}

export interface InfrastructureCreate {
  service: string;
  host: string;
  port: number;
  connection_url?: string;
  is_enabled?: boolean;
}

export interface HealthCheckResult {
  service: string;
  status: 'healthy' | 'unhealthy' | 'unknown' | 'degraded';
  latency_ms: number;
  error?: string;
}

// Provisioning types
export type RuntimeChoice = 'auto' | 'podman' | 'docker';

export interface ProvisionRequest {
  services: string[];
  runtime?: RuntimeChoice;
}

export interface ProvisionResult {
  success: boolean;
  host: string;
  port: number;
  connection_string?: string;
  latency_ms: number;
  error?: string;
}

export interface ProvisionResponse {
  status: 'provisioning' | 'completed' | 'failed';
  results: Record<string, ProvisionResult>;
  connection_strings: Record<string, string>;
  errors: string[];
  total_provisioned: number;
  total_failed: number;
}

// =============================================================================
// API Functions
// =============================================================================

import apiClient from './client';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const method = (options?.method || 'GET') as string;
  const body = options?.body ? JSON.parse(options.body as string) : undefined;

  const response = await apiClient.request<T>({
    method,
    url,
    data: body,
  });

  return response.data;
}

/**
 * Get list of available providers
 */
export async function getProviders(): Promise<{ providers: Provider[]; total: number }> {
  return fetchJson<{ providers: Provider[]; total: number }>('/api/wizard/providers');
}

/**
 * Get a specific provider
 */
export async function getProvider(providerId: string): Promise<Provider> {
  return fetchJson<Provider>(`/api/wizard/providers/${providerId}`);
}

/**
 * Get list of available agent tiers
 */
export async function getTiers(): Promise<{ tiers: AgentTier[]; total: number }> {
  return fetchJson<{ tiers: AgentTier[]; total: number }>('/api/wizard/tiers');
}

/**
 * Get a specific tier
 */
export async function getTier(tierId: string): Promise<AgentTier> {
  return fetchJson<AgentTier>(`/api/wizard/tiers/${tierId}`);
}

/**
 * Get current configuration status
 */
export async function getConfigStatus(): Promise<ConfigStatus> {
  return fetchJson<ConfigStatus>('/api/wizard/config');
}

/**
 * Validate provider credentials
 */
export async function validateCredentials(
  providerId: string,
  apiKey?: string,
  baseUrl?: string,
): Promise<ValidationResult> {
  const params = new URLSearchParams();
  if (apiKey) params.append('api_key', apiKey);
  if (baseUrl) params.append('base_url', baseUrl);

  return fetchJson<ValidationResult>(`/api/wizard/validate/${providerId}?${params.toString()}`, {
    method: 'POST',
  });
}

/**
 * Submit wizard configuration
 */
export async function submitConfig(config: WizardConfig): Promise<SubmitResult> {
  return fetchJson<SubmitResult>('/api/wizard/config', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

/**
 * Reset wizard state
 */
export async function resetWizard(): Promise<{ success: boolean; message: string }> {
  return fetchJson<{ success: boolean; message: string }>('/api/wizard/reset', {
    method: 'POST',
  });
}

// =============================================================================
// Infrastructure API Functions
// =============================================================================

/**
 * Get list of infrastructure service configurations
 */
export async function getInfrastructureConfigs(): Promise<{
  infrastructure: InfrastructureConfig[];
  total: number;
}> {
  return fetchJson<{ infrastructure: InfrastructureConfig[]; total: number }>(
    '/api/wizard/infrastructure',
  );
}

/**
 * Create or update infrastructure service configuration
 */
export async function saveInfrastructureConfig(config: InfrastructureCreate): Promise<{
  id: string;
  service: string;
  host: string;
  port: number;
  connection_url?: string;
  is_enabled: boolean;
  message: string;
}> {
  return fetchJson<{
    id: string;
    service: string;
    host: string;
    port: number;
    connection_url?: string;
    is_enabled: boolean;
    message: string;
  }>('/api/wizard/infrastructure', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

/**
 * Get infrastructure configuration for a specific service
 */
export async function getInfrastructureConfig(service: string): Promise<InfrastructureConfig> {
  return fetchJson<InfrastructureConfig>(`/api/wizard/infrastructure/${service}`);
}

/**
 * Run health check for a specific infrastructure service
 */
export async function checkInfrastructureHealth(service: string): Promise<HealthCheckResult> {
  return fetchJson<HealthCheckResult>(`/api/wizard/infrastructure/${service}/health-check`, {
    method: 'POST',
  });
}

/**
 * Run health check for all configured infrastructure services
 */
export async function checkAllInfrastructureHealth(): Promise<{
  results: HealthCheckResult[];
  summary:
    | {
        total: number;
        healthy: number;
        unhealthy: number;
        degraded: number;
      }
    | string;
}> {
  return fetchJson<{
    results: HealthCheckResult[];
    summary:
      | {
          total: number;
          healthy: number;
          unhealthy: number;
          degraded: number;
        }
      | string;
  }>('/api/wizard/infrastructure/health-check-all', {
    method: 'POST',
  });
}

/**
 * Delete infrastructure configuration for a service
 */
export async function deleteInfrastructureConfig(service: string): Promise<{ success: boolean }> {
  const response = await apiClient.delete(`/api/wizard/infrastructure/${service}`);
  // Axios returns 204 with empty data — treat as success
  if (!response.data || Object.keys(response.data).length === 0) {
    return { success: true };
  }
  return response.data;
}

/**
 * Provision infrastructure services locally via Docker/Podman.
 * Stops any existing heretek-* containers, starts new ones,
 * and polls health checks until all services are healthy (up to 60s).
 */
export async function provisionInfrastructure(
  services: string[],
  runtime?: RuntimeChoice,
): Promise<ProvisionResponse> {
  return fetchJson<ProvisionResponse>('/api/wizard/provision', {
    method: 'POST',
    body: JSON.stringify({ services, runtime: runtime || 'auto' }),
  });
}
