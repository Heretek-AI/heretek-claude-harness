/**
 * Configuration API Client
 *
 * TypeScript client for interacting with the configuration API endpoints.
 * LLM and embedding provider management now routes through /api/providers
 * backed by config.json (zero Postgres dependency).
 *
 * Types match the API response shapes:
 * - LLM: snake_case from ProviderConfig.to_dict()
 * - Embedding: camelCase from config.json embeddingProviders
 */

import apiClient from './client';

// =============================================================================
// Raw API Response Types (match on-wire JSON)
// =============================================================================

/** LLM provider as returned by GET /api/providers/llm */
export interface LLMProviderRaw {
  id: string;
  name: string;
  provider_type: string;
  base_url: string;
  api_key: string | null;
  default_model: string | null;
  available_models: string[];
  is_enabled: boolean;
  is_default: boolean;
  priority: number;
  max_rpm: number | null;
  max_tpm: number | null;
  health_status: string;
}

/** Embedding provider as returned by GET /api/providers/embedding */
export interface EmbeddingProviderRaw {
  id: string;
  type: string;
  name: string;
  baseUrl: string;
  apiKey?: string;
  defaultModel?: string;
  models: string[];
  isEnabled: boolean;
  priority: number;
}

/** Test result for LLM providers */
export interface LLMTestResult {
  reachable: boolean;
  latency_ms: number;
  error: string | null;
}

/** Test result for embedding providers */
export interface EmbeddingTestResult {
  reachable: boolean;
  latency_ms: number;
  error: string | null;
}

// =============================================================================
// UI-facing Types (used by components)
// =============================================================================

/**
 * LLMProvider — snake_case for backward compatibility with AgentDefaultsSection
 * and SetupWizard. Matches old provider_name / provider_type convention.
 */
export interface LLMProvider {
  id: string;
  provider_name: string;
  provider_type: string;
  base_url: string;
  api_key_hint?: string;
  default_model?: string;
  available_models: string[];
  is_enabled: boolean;
  is_default: boolean;
  priority: number;
  health_status: string;
}

export interface EmbeddingProvider {
  id: string;
  provider_name: string;
  provider_type: string;
  base_url: string;
  api_key_hint?: string;
  default_model?: string;
  is_enabled: boolean;
  is_default: boolean;
  priority: number;
  health_status: string;
}

export interface UserConfiguration {
  id: string;
  config_key: string;
  config_value: unknown;
  config_type: 'string' | 'integer' | 'float' | 'boolean' | 'json' | 'array';
  description?: string;
  category: string;
  is_sensitive: boolean;
  is_editable: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentConfig {
  id: string;
  agent_type: string;
  agent_id?: string;
  config_name: string;
  config_data: Record<string, any>;
  llm_provider_id?: string;
  embedding_provider_id?: string;
  is_active: boolean;
  is_default_for_type: boolean;
  description?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

/** Request body for creating an LLM provider (matches API POST /api/providers/llm) */
export interface LLMProviderCreate {
  type: string;
  name: string;
  baseUrl: string;
  apiKey?: string;
  apiKey_hint?: string;
  defaultModel?: string;
  models?: string[];
  isEnabled?: boolean;
  isDefault?: boolean;
  priority?: number;
}

/** Request body for creating an embedding provider (matches API POST /api/providers/embedding) */
export interface EmbeddingProviderCreate {
  type: string;
  name: string;
  baseUrl: string;
  apiKey?: string;
  apiKey_hint?: string;
  defaultModel?: string;
  models?: string[];
  isEnabled?: boolean;
  priority?: number;
}

export interface ProviderTestResult {
  success: boolean;
  provider_name: string;
  model_used: string;
  latency_ms: number;
  response_text?: string;
  error?: string;
}

export interface EmbeddingProviderTestResult {
  success: boolean;
  provider_name: string;
  model_used: string;
  dimensions?: number;
  latency_ms: number;
  error?: string;
}

// =============================================================================
// Transforms
// =============================================================================

/** Convert API (LLMProviderRaw) → UI (LLMProvider) preserving snake_case convention */
function _transformLLM(raw: LLMProviderRaw): LLMProvider {
  return {
    id: raw.id,
    provider_name: raw.name,
    provider_type: raw.provider_type,
    base_url: raw.base_url,
    api_key_hint: raw.api_key ? (raw.api_key.length > 4 ? '***' + raw.api_key.slice(-4) : '***') : undefined,
    default_model: raw.default_model ?? undefined,
    available_models: raw.available_models,
    is_enabled: raw.is_enabled,
    is_default: raw.is_default,
    priority: raw.priority,
    health_status: raw.health_status,
  };
}

/** Convert API (EmbeddingProviderRaw) → UI (EmbeddingProvider) */
function _transformEmbedding(raw: EmbeddingProviderRaw): EmbeddingProvider {
  return {
    id: raw.id,
    provider_name: raw.name,
    provider_type: raw.type,
    base_url: raw.baseUrl,
    api_key_hint: raw.apiKey
      ? (raw.apiKey.length > 4 ? '***' + raw.apiKey.slice(-4) : '***')
      : undefined,
    default_model: raw.defaultModel,
    is_enabled: raw.isEnabled,
    is_default: false, // Embedding API doesn't expose isDefault
    priority: raw.priority,
    health_status: 'unknown',
  };
}

/** Build request body for LLM provider create/update */
function _llmToRequestBody(data: LLMProviderCreate | Partial<LLMProviderCreate>) {
  return {
    type: data.type,
    name: data.name,
    baseUrl: data.baseUrl,
    apiKey: data.apiKey,
    defaultModel: data.defaultModel,
    models: data.models,
    isEnabled: data.isEnabled,
    isDefault: data.isDefault,
    priority: data.priority,
  };
}

function _embeddingToRequestBody(data: EmbeddingProviderCreate | Partial<EmbeddingProviderCreate>) {
  return {
    type: data.type,
    name: data.name,
    baseUrl: data.baseUrl,
    apiKey: data.apiKey,
    defaultModel: data.defaultModel,
    models: data.models,
    isEnabled: data.isEnabled,
    priority: data.priority,
  };
}

// =============================================================================
// Configuration Endpoints
// =============================================================================

export const configurationApi = {
  // ---- LLM Providers (config.json via /api/providers) ----

  fetchLLMProviders: async (): Promise<LLMProvider[]> => {
    const response = await apiClient.get('/api/providers/llm');
    const providers: LLMProviderRaw[] = response.data.providers;
    return providers.map(_transformLLM);
  },

  /** Alias for backward compat: AgentDefaultsSection, SetupWizard use listLLMProviders */
  listLLMProviders: async (_providerType?: string, _enabledOnly?: boolean): Promise<LLMProvider[]> => {
    return configurationApi.fetchLLMProviders();
  },

  createLLMProvider: async (provider: LLMProviderCreate): Promise<LLMProvider> => {
    const response = await apiClient.post('/api/providers/llm', _llmToRequestBody(provider));
    return _transformLLM(response.data);
  },

  updateLLMProvider: async (id: string, provider: Partial<LLMProviderCreate>): Promise<LLMProvider> => {
    const response = await apiClient.put(`/api/providers/llm/${id}`, _llmToRequestBody(provider));
    return _transformLLM(response.data);
  },

  deleteLLMProvider: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/providers/llm/${id}`);
  },

  testLLMProvider: async (id: string, _prompt?: string, _model?: string): Promise<ProviderTestResult> => {
    const response = await apiClient.post(`/api/providers/llm/${id}/test`);
    const data: LLMTestResult = response.data;
    // Map test result to shape expected by callers
    return {
      success: data.reachable,
      provider_name: id,
      model_used: '',
      latency_ms: data.latency_ms,
      error: data.error ?? undefined,
    };
  },

  // ---- Embedding Providers (config.json via /api/providers) ----

  fetchEmbeddingProviders: async (): Promise<EmbeddingProvider[]> => {
    const response = await apiClient.get('/api/providers/embedding');
    const providers: EmbeddingProviderRaw[] = response.data.providers;
    return providers.map(_transformEmbedding);
  },

  /** Alias for backward compat */
  listEmbeddingProviders: async (_providerType?: string, _enabledOnly?: boolean): Promise<EmbeddingProvider[]> => {
    return configurationApi.fetchEmbeddingProviders();
  },

  createEmbeddingProvider: async (provider: EmbeddingProviderCreate): Promise<EmbeddingProvider> => {
    const response = await apiClient.post('/api/providers/embedding', _embeddingToRequestBody(provider));
    return _transformEmbedding(response.data);
  },

  updateEmbeddingProvider: async (id: string, provider: Partial<EmbeddingProviderCreate>): Promise<EmbeddingProvider> => {
    const response = await apiClient.put(`/api/providers/embedding/${id}`, _embeddingToRequestBody(provider));
    return _transformEmbedding(response.data);
  },

  deleteEmbeddingProvider: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/providers/embedding/${id}`);
  },

  testEmbeddingProvider: async (id: string, _text?: string, _model?: string): Promise<EmbeddingProviderTestResult> => {
    const response = await apiClient.post(`/api/providers/embedding/${id}/test`);
    const data: EmbeddingTestResult = response.data;
    return {
      success: data.reachable,
      provider_name: id,
      model_used: '',
      latency_ms: data.latency_ms,
      error: data.error ?? undefined,
    };
  },

  // ---- User Configurations (kept as-is) ----

  getConfigs: async (category?: string): Promise<UserConfiguration[]> => {
    const params = category ? { category } : {};
    const response = await apiClient.get('/api/config', { params });
    return response.data.configurations;
  },

  getConfig: async (key: string): Promise<UserConfiguration> => {
    const response = await apiClient.get(`/api/config/${key}`);
    return response.data;
  },

  updateConfig: async (key: string, value: unknown): Promise<UserConfiguration> => {
    const response = await apiClient.put(`/api/config/${key}`, { config_value: value });
    return response.data;
  },

  createConfig: async (config: Partial<UserConfiguration>): Promise<UserConfiguration> => {
    const response = await apiClient.post('/api/config', config);
    return response.data;
  },

  deleteConfig: async (key: string): Promise<void> => {
    await apiClient.delete(`/api/config/${key}`);
  },

  // ---- Agent Configurations ----

  listAgentConfigs: async (agentType?: string, activeOnly?: boolean): Promise<AgentConfig[]> => {
    const params: Record<string, string> = {};
    if (agentType) params.agent_type = agentType;
    if (activeOnly !== undefined) params.active_only = String(activeOnly);
    const response = await apiClient.get('/api/config/agent/configs', { params });
    return response.data.configs;
  },

  getAgentConfig: async (id: string): Promise<AgentConfig> => {
    const response = await apiClient.get(`/api/config/agent/configs/${id}`);
    return response.data;
  },

  createAgentConfig: async (config: Partial<AgentConfig>): Promise<AgentConfig> => {
    const response = await apiClient.post('/api/config/agent/configs', config);
    return response.data;
  },

  updateAgentConfig: async (id: string, config: Partial<AgentConfig>): Promise<AgentConfig> => {
    const response = await apiClient.put(`/api/config/agent/configs/${id}`, config);
    return response.data;
  },

  deleteAgentConfig: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/config/agent/configs/${id}`);
  },

  // ---- Import/Export ----

  exportConfigurations: async (): Promise<any> => {
    const response = await apiClient.get('/api/config/export');
    return response.data;
  },

  importConfigurations: async (data: unknown, options?: Record<string, unknown>): Promise<unknown> => {
    const response = await apiClient.post('/api/config/import', {
      import_data: data,
      options: options || {},
    });
    return response.data;
  },

  migrateFromEnv: async (): Promise<any> => {
    const response = await apiClient.post('/api/config/migrate-from-env');
    return response.data;
  },
};

export default configurationApi;
