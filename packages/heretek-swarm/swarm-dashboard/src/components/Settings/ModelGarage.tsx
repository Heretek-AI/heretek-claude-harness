/**
 * Model Garage UI
 *
 * LLM Provider Management Interface for Heretek Swarm.
 * Manages connections to OpenAI, Ollama, MiniMax, Z.AI and embedding services
 * via the config.json-backed /api/providers API.
 *
 * Features:
 * - Add/test connections to LLM providers
 * - Embedding service configuration
 * - Model selection and routing
 * - Connection health monitoring
 * - Real provider usage stats (polled from the observability API)
 */

import React, { useState, useCallback, useEffect } from 'react';
import { fetchProviderStats } from '../../api/observability';
import configurationApi from '../../api/configuration';

// =============================================================================
// Types — internal UI representation
// =============================================================================

export interface LLMProvider {
  id: string;
  name: string;
  type: ProviderType;
  baseUrl: string;
  apiKey?: string;
  models: string[];
  selectedModel?: string;
  isEnabled: boolean;
  isDefault: boolean;
  healthStatus: 'healthy' | 'unhealthy' | 'unknown' | 'degraded';
  latencyMs?: number;
  errorMessage?: string;
}

export interface EmbeddingProvider {
  id: string;
  name: string;
  type: EmbeddingProviderType;
  baseUrl: string;
  apiKey?: string;
  model?: string;
  dimensions?: number;
  isEnabled: boolean;
  isDefault: boolean;
  healthStatus: 'healthy' | 'unhealthy' | 'unknown';
}

export type ProviderType = 'openai' | 'ollama' | 'minimax' | 'zai' | 'anthropic' | 'google' | 'groq' | 'azure';
export type EmbeddingProviderType = 'openai' | 'cohere' | 'huggingface' | 'ollama' | 'local';

// =============================================================================
// Transforms: API response ⇄ internal UI shape
// =============================================================================

/** API LLM provider (snake_case from ProviderConfig.to_dict()) → internal LLMProvider */
function _apiToLLM(raw: any): LLMProvider {
  return {
    id: raw.id,
    name: raw.provider_name || raw.name,
    type: raw.provider_type || raw.type || 'ollama',
    baseUrl: raw.base_url || raw.baseUrl,
    apiKey: raw.api_key_hint ?? raw.api_key ?? undefined,
    models: raw.available_models || raw.models || [],
    selectedModel: raw.default_model || raw.defaultModel,
    isEnabled: raw.is_enabled ?? raw.isEnabled ?? true,
    isDefault: raw.is_default ?? raw.isDefault ?? false,
    healthStatus: raw.health_status || 'unknown',
    latencyMs: undefined,
    errorMessage: undefined,
  };
}

/** API embedding provider → internal EmbeddingProvider */
function _apiToEmbedding(raw: any): EmbeddingProvider {
  return {
    id: raw.id,
    name: raw.provider_name || raw.name,
    type: raw.provider_type || raw.type || 'openai',
    baseUrl: raw.base_url || raw.baseUrl,
    apiKey: raw.api_key_hint || raw.apiKey || undefined,
    model: raw.default_model || raw.defaultModel,
    isEnabled: raw.is_enabled ?? raw.isEnabled ?? true,
    isDefault: raw.is_default ?? false,
    healthStatus: raw.health_status || 'unknown',
  };
}

/** Internal LLMProvider → API request body */
function _llmToRequest(provider: Partial<LLMProvider>): Record<string, any> {
  return {
    type: provider.type,
    name: provider.name,
    baseUrl: provider.baseUrl,
    apiKey: provider.apiKey,
    defaultModel: provider.selectedModel || provider.models?.[0],
    models: provider.models,
    isEnabled: provider.isEnabled,
    isDefault: provider.isDefault,
  };
}

/** Internal EmbeddingProvider → API request body */
function _embeddingToRequest(provider: Partial<EmbeddingProvider>): Record<string, any> {
  return {
    type: provider.type,
    name: provider.name,
    baseUrl: provider.baseUrl,
    apiKey: provider.apiKey,
    defaultModel: provider.model,
    isEnabled: provider.isEnabled,
  };
}

// =============================================================================
// Provider Configuration Constants
// =============================================================================

export const LLM_PROVIDER_CONFIGS: Record<ProviderType, {
  name: string;
  defaultUrl: string;
  models: string[];
  supportsStreaming: boolean;
  supportsFunctionCalling: boolean;
  requiresApiKey: boolean;
  color: string;
}> = {
  openai: {
    name: 'OpenAI',
    defaultUrl: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o1-preview', 'o1-mini'],
    supportsStreaming: true,
    supportsFunctionCalling: true,
    requiresApiKey: true,
    color: '#10a37f',
  },
  anthropic: {
    name: 'Anthropic',
    defaultUrl: 'https://api.anthropic.com/v1',
    models: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
    supportsStreaming: true,
    supportsFunctionCalling: true,
    requiresApiKey: true,
    color: '#d4a574',
  },
  google: {
    name: 'Google',
    defaultUrl: 'https://generativelanguage.googleapis.com/v1beta',
    models: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro'],
    supportsStreaming: true,
    supportsFunctionCalling: true,
    requiresApiKey: true,
    color: '#4285f4',
  },
  ollama: {
    name: 'Ollama',
    defaultUrl: 'http://localhost:11434',
    models: ['llama3.1', 'llama3', 'mistral', 'codellama', 'phi3', 'qwen2', 'deepseek-coder'],
    supportsStreaming: true,
    supportsFunctionCalling: false,
    requiresApiKey: false,
    color: '#354545',
  },
  minimax: {
    name: 'MiniMax',
    defaultUrl: 'https://api.minimax.chat/v1',
    models: ['abab6.5s', 'abab6.5', 'abab5.5s', 'abab5.5'],
    supportsStreaming: true,
    supportsFunctionCalling: false,
    requiresApiKey: true,
    color: '#00d2d3',
  },
  zai: {
    name: 'Z.AI (Zhipu)',
    defaultUrl: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-4', 'glm-4-flash', 'glm-4-plus', 'glm-3-turbo'],
    supportsStreaming: true,
    supportsFunctionCalling: true,
    requiresApiKey: true,
    color: '#00bfff',
  },
  groq: {
    name: 'Groq',
    defaultUrl: 'https://api.groq.com/openai/v1',
    models: ['llama-3.1-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
    supportsStreaming: true,
    supportsFunctionCalling: true,
    requiresApiKey: true,
    color: '#e63946',
  },
  azure: {
    name: 'Azure OpenAI',
    defaultUrl: 'https://YOUR_RESOURCE.openai.azure.com',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-35-turbo'],
    supportsStreaming: true,
    supportsFunctionCalling: true,
    requiresApiKey: true,
    color: '#0078d4',
  },
};

export const EMBEDDING_PROVIDER_CONFIGS: Record<EmbeddingProviderType, {
  name: string;
  defaultUrl: string;
  models: string[];
  color: string;
}> = {
  openai: {
    name: 'OpenAI',
    defaultUrl: 'https://api.openai.com/v1',
    models: ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002'],
    color: '#10a37f',
  },
  cohere: {
    name: 'Cohere',
    defaultUrl: 'https://api.cohere.ai/v1',
    models: ['embed-english-v3.0', 'embed-multilingual-v3.0', 'embed-english-light-v3.0'],
    color: '#f5a623',
  },
  huggingface: {
    name: 'HuggingFace',
    defaultUrl: 'https://api-inference.huggingface.co/pipeline/feature-extraction',
    models: ['sentence-transformers/all-MiniLM-L6-v2', 'sentence-transformers/all-mpnet-base-v2'],
    color: '#ffd21e',
  },
  ollama: {
    name: 'Ollama',
    defaultUrl: 'http://localhost:11434',
    models: ['nomic-embed-text', 'mxbai-embed-large'],
    color: '#354545',
  },
  local: {
    name: 'Local',
    defaultUrl: 'http://localhost:8080',
    models: ['all-MiniLM-L6-v2', 'all-mpnet-base-v2'],
    color: '#6b7280',
  },
};

// =============================================================================
// Sub-Components
// =============================================================================

const ProviderCard: React.FC<{
  provider: LLMProvider;
  onEdit: (provider: LLMProvider) => void;
  onTest: (id: string) => void;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
  isTesting: boolean;
}> = ({ provider, onEdit, onTest, onToggle, onDelete, isTesting }) => {
  const config = LLM_PROVIDER_CONFIGS[provider.type];

  const getStatusColor = () => {
    switch (provider.healthStatus) {
      case 'healthy': return 'bg-green-500';
      case 'degraded': return 'bg-yellow-500';
      case 'unhealthy': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: config?.color || '#6366f1' }}>
            <span className="text-xl">{config?.name.charAt(0) || '?'}</span>
          </div>
          <div>
            <h3 className="font-medium text-white">{provider.name}</h3>
            <p className="text-sm text-gray-400">{config?.name || provider.type}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} title={provider.healthStatus} />
          {provider.latencyMs && (
            <span className="text-xs text-gray-400">{provider.latencyMs}ms</span>
          )}
        </div>
      </div>

      <div className="mb-3">
        <p className="text-xs text-gray-500 mb-1">Selected Model</p>
        <p className="text-sm text-white font-mono">
          {provider.selectedModel || provider.models[0] || 'No model selected'}
        </p>
      </div>

      {provider.errorMessage && (
        <div className="mb-3 p-2 bg-red-900/30 border border-red-500/50 rounded text-xs text-red-400">
          {provider.errorMessage}
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-gray-700">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={provider.isEnabled}
            onChange={() => onToggle(provider.id)}
            className="rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-400">Enabled</span>
        </label>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onTest(provider.id)}
            disabled={isTesting || !provider.isEnabled}
            className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded transition-colors"
          >
            {isTesting ? 'Testing...' : 'Test'}
          </button>
          <button
            onClick={() => onEdit(provider)}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(provider.id)}
            className="px-3 py-1 text-xs bg-red-600/50 hover:bg-red-600 text-white rounded transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};

const ProviderForm: React.FC<{
  provider?: LLMProvider;
  onSave: (provider: Partial<LLMProvider>) => void;
  onCancel: () => void;
}> = ({ provider, onSave, onCancel }) => {
  const [formData, setFormData] = useState<{
    name: string;
    type: ProviderType;
    baseUrl: string;
    apiKey: string;
    selectedModel: string;
    isEnabled: boolean;
    isDefault: boolean;
  }>({
    name: provider?.name || '',
    type: provider?.type || 'openai',
    baseUrl: provider?.baseUrl || LLM_PROVIDER_CONFIGS.openai.defaultUrl,
    apiKey: provider?.apiKey || '',
    selectedModel: provider?.selectedModel || LLM_PROVIDER_CONFIGS.openai.models[0],
    isEnabled: provider?.isEnabled ?? true,
    isDefault: provider?.isDefault ?? false,
  });

  const handleTypeChange = (type: ProviderType) => {
    const config = LLM_PROVIDER_CONFIGS[type];
    setFormData((prev) => ({
      ...prev,
      type,
      baseUrl: config?.defaultUrl || prev.baseUrl,
      selectedModel: config?.models[0] || prev.selectedModel,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const config = LLM_PROVIDER_CONFIGS[formData.type];
    onSave({
      id: provider?.id || `provider-${Date.now()}`,
      name: formData.name || config?.name || formData.type,
      type: formData.type,
      baseUrl: formData.baseUrl,
      apiKey: formData.apiKey,
      models: config?.models || [],
      selectedModel: formData.selectedModel,
      isEnabled: formData.isEnabled,
      isDefault: formData.isDefault,
      healthStatus: 'unknown',
    });
  };

  const config = LLM_PROVIDER_CONFIGS[formData.type];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Provider Type</label>
          <select
            value={formData.type}
            onChange={(e) => handleTypeChange(e.target.value as ProviderType)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {Object.entries(LLM_PROVIDER_CONFIGS).map(([type, cfg]) => (
              <option key={type} value={type}>{cfg.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Display Name</label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
            placeholder={config?.name}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Base URL</label>
        <input
          type="text"
          value={formData.baseUrl}
          onChange={(e) => setFormData((prev) => ({ ...prev, baseUrl: e.target.value }))}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {config?.requiresApiKey && (
        <div>
          <label className="block text-sm text-gray-400 mb-1">API Key</label>
          <input
            type="password"
            value={formData.apiKey}
            onChange={(e) => setFormData((prev) => ({ ...prev, apiKey: e.target.value }))}
            placeholder="sk-..."
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      )}

      <div>
        <label className="block text-sm text-gray-400 mb-1">Default Model</label>
        <input
          type="text"
          value={formData.selectedModel}
          onChange={(e) => setFormData((prev) => ({ ...prev, selectedModel: e.target.value }))}
          placeholder="Type or select a model..."
          list={`model-list-${formData.type}`}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <datalist id={`model-list-${formData.type}`}>
          {config?.models.map((model) => (
            <option key={model} value={model} />
          ))}
        </datalist>
        {config?.models.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {config.models.map((model) => (
              <button
                key={model}
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, selectedModel: model }))}
                className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded text-gray-300 transition-colors"
              >
                {model}
              </button>
            ))}
          </div>
        )}
        <p className="text-xs text-gray-500 mt-1">
          Type any model name — not limited to the suggestions above.
        </p>
      </div>

      <div className="flex items-center gap-6">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={formData.isEnabled}
            onChange={(e) => setFormData((prev) => ({ ...prev, isEnabled: e.target.checked }))}
            className="rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
          />
          <span className="text-sm text-white">Enabled</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={formData.isDefault}
            onChange={(e) => setFormData((prev) => ({ ...prev, isDefault: e.target.checked }))}
            className="rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
          />
          <span className="text-sm text-white">Set as Default</span>
        </label>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          {provider ? 'Update Provider' : 'Add Provider'}
        </button>
      </div>
    </form>
  );
};

const EmbeddingProviderCard: React.FC<{
  provider: EmbeddingProvider;
  onEdit: (provider: EmbeddingProvider) => void;
  onTest: (id: string) => void;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
  isTesting: boolean;
}> = ({ provider, onEdit, onTest, onToggle, onDelete, isTesting }) => {
  const config = EMBEDDING_PROVIDER_CONFIGS[provider.type];

  const getStatusColor = () => {
    switch (provider.healthStatus) {
      case 'healthy': return 'bg-green-500';
      case 'unhealthy': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: config?.color || '#6366f1' }}>
            <span className="text-xl">E</span>
          </div>
          <div>
            <h3 className="font-medium text-white">{provider.name}</h3>
            <p className="text-sm text-gray-400">{config?.name || provider.type}</p>
          </div>
        </div>
        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
        <div>
          <span className="text-gray-500">Model:</span>
          <span className="ml-1 text-white font-mono">{provider.model || 'default'}</span>
        </div>
        <div>
          <span className="text-gray-500">Dimensions:</span>
          <span className="ml-1 text-white">{provider.dimensions || 1536}</span>
        </div>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-gray-700">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={provider.isEnabled}
            onChange={() => onToggle(provider.id)}
            className="rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-400">Enabled</span>
        </label>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onTest(provider.id)}
            disabled={isTesting}
            className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded"
          >
            Test
          </button>
          <button
            onClick={() => onEdit(provider)}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(provider.id)}
            className="px-3 py-1 text-xs bg-red-600/50 hover:bg-red-600 text-white rounded transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};

const EmbeddingProviderForm: React.FC<{
  provider?: EmbeddingProvider;
  onSave: (provider: Partial<EmbeddingProvider>) => void;
  onCancel: () => void;
}> = ({ provider, onSave, onCancel }) => {
  const [formData, setFormData] = useState<{
    name: string;
    type: EmbeddingProviderType;
    baseUrl: string;
    apiKey: string;
    model: string;
    isEnabled: boolean;
    isDefault: boolean;
  }>({
    name: provider?.name || '',
    type: provider?.type || 'openai',
    baseUrl: provider?.baseUrl || EMBEDDING_PROVIDER_CONFIGS.openai.defaultUrl,
    apiKey: provider?.apiKey || '',
    model: provider?.model || EMBEDDING_PROVIDER_CONFIGS.openai.models[0],
    isEnabled: provider?.isEnabled ?? true,
    isDefault: provider?.isDefault ?? false,
  });

  const handleTypeChange = (type: EmbeddingProviderType) => {
    const config = EMBEDDING_PROVIDER_CONFIGS[type];
    setFormData((prev) => ({
      ...prev,
      type,
      baseUrl: config?.defaultUrl || prev.baseUrl,
      model: config?.models[0] || prev.model,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const config = EMBEDDING_PROVIDER_CONFIGS[formData.type];
    onSave({
      id: provider?.id || `embed-${Date.now()}`,
      name: formData.name || config?.name || formData.type,
      type: formData.type,
      baseUrl: formData.baseUrl,
      apiKey: formData.apiKey,
      model: formData.model,
      isEnabled: formData.isEnabled,
      isDefault: formData.isDefault,
      healthStatus: 'unknown',
    });
  };

  const config = EMBEDDING_PROVIDER_CONFIGS[formData.type];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Provider Type</label>
          <select
            value={formData.type}
            onChange={(e) => handleTypeChange(e.target.value as EmbeddingProviderType)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {Object.entries(EMBEDDING_PROVIDER_CONFIGS).map(([type, cfg]) => (
              <option key={type} value={type}>{cfg.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Display Name</label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
            placeholder={config?.name}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Base URL</label>
        <input
          type="text"
          value={formData.baseUrl}
          onChange={(e) => setFormData((prev) => ({ ...prev, baseUrl: e.target.value }))}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">API Key</label>
        <input
          type="password"
          value={formData.apiKey}
          onChange={(e) => setFormData((prev) => ({ ...prev, apiKey: e.target.value }))}
          placeholder="sk-..."
          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Default Model</label>
        <input
          type="text"
          value={formData.model}
          onChange={(e) => setFormData((prev) => ({ ...prev, model: e.target.value }))}
          placeholder="Type or select a model..."
          list={`embedding-model-list-${formData.type}`}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <datalist id={`embedding-model-list-${formData.type}`}>
          {config?.models.map((model) => (
            <option key={model} value={model} />
          ))}
        </datalist>
        {config?.models.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {config.models.map((model) => (
              <button
                key={model}
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, model }))}
                className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded text-gray-300 transition-colors"
              >
                {model}
              </button>
            ))}
          </div>
        )}
        <p className="text-xs text-gray-500 mt-1">
          Type any model name — not limited to the suggestions above.
        </p>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          {provider ? 'Update Provider' : 'Add Provider'}
        </button>
      </div>
    </form>
  );
};

// =============================================================================
// Main Component
// =============================================================================

export function ModelGarage() {
  const [llmProviders, setLlmProviders] = useState<LLMProvider[]>([]);
  const [embeddingProviders, setEmbeddingProviders] = useState<EmbeddingProvider[]>([]);
  const [activeTab, setActiveTab] = useState<'llm' | 'embedding'>('llm');
  const [showLlmForm, setShowLlmForm] = useState(false);
  const [showEmbeddingForm, setShowEmbeddingForm] = useState(false);
  const [editingLlmProvider, setEditingLlmProvider] = useState<LLMProvider | undefined>();
  const [editingEmbeddingProvider, setEditingEmbeddingProvider] = useState<EmbeddingProvider | undefined>();
  const [testingId, setTestingId] = useState<string | null>(null);
  const [loadingLlm, setLoadingLlm] = useState(true);
  const [loadingEmbedding, setLoadingEmbedding] = useState(true);
  const [apiError, setApiError] = useState(false);
  const [globalStats, setGlobalStats] = useState({
    totalRequests: 0,
    totalTokens: 0,
    avgLatency: 245,
    costEstimate: 0,
  });
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState(false);

  // ---- Fetch LLM providers from API ----
  const loadLLMProviders = useCallback(async () => {
    try {
      setApiError(false);
      const rawProviders = await configurationApi.fetchLLMProviders();
      const mapped = rawProviders.map((p: any) => _apiToLLM(p));
      setLlmProviders(mapped);
      setLoadingLlm(false);
    } catch (err) {
      console.error('Failed to fetch LLM providers:', err);
      setApiError(true);
      setLoadingLlm(false);
    }
  }, []);

  // ---- Fetch Embedding providers from API ----
  const loadEmbeddingProviders = useCallback(async () => {
    try {
      setApiError(false);
      const rawProviders = await configurationApi.fetchEmbeddingProviders();
      const mapped = rawProviders.map((p: any) => _apiToEmbedding(p));
      setEmbeddingProviders(mapped);
      setLoadingEmbedding(false);
    } catch (err) {
      console.error('Failed to fetch embedding providers:', err);
      setApiError(true);
      setLoadingEmbedding(false);
    }
  }, []);

  // Load both on mount
  useEffect(() => {
    loadLLMProviders();
    loadEmbeddingProviders();
  }, [loadLLMProviders, loadEmbeddingProviders]);

  // ---- Poll provider stats from the observability API ----
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const data = await fetchProviderStats();
        if (cancelled) return;
        setGlobalStats({
          totalRequests: data.total_requests,
          totalTokens: data.total_tokens,
          avgLatency: 245,
          costEstimate: data.total_cost,
        });
        setStatsLoading(false);
        setStatsError(false);
      } catch (err) {
        if (cancelled) return;
        console.warn('Failed to fetch provider stats:', err);
        setStatsError(true);
        setStatsLoading(false);
      }
      if (!cancelled) {
        timer = setTimeout(poll, 5000);
      }
    };

    poll();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  // ---- LLM CRUD handlers ----

  const handleSaveLlmProvider = useCallback(async (provider: Partial<LLMProvider>) => {
    try {
      if (editingLlmProvider) {
        await configurationApi.updateLLMProvider(editingLlmProvider.id, {
          type: provider.type!,
          name: provider.name!,
          baseUrl: provider.baseUrl!,
          apiKey: provider.apiKey,
          defaultModel: provider.selectedModel,
          models: provider.models,
          isEnabled: provider.isEnabled,
          isDefault: provider.isDefault,
          priority: 100,
        });
      } else {
        await configurationApi.createLLMProvider({
          type: provider.type!,
          name: provider.name!,
          baseUrl: provider.baseUrl!,
          apiKey: provider.apiKey,
          defaultModel: provider.selectedModel,
          models: provider.models,
          isEnabled: provider.isEnabled,
          isDefault: provider.isDefault,
          priority: 100,
        });
      }
      setShowLlmForm(false);
      setEditingLlmProvider(undefined);
      await loadLLMProviders();
    } catch (err: any) {
      console.error('Failed to save LLM provider:', err);
      setApiError(true);
    }
  }, [editingLlmProvider, loadLLMProviders]);

  const handleDeleteLlm = useCallback(async (id: string) => {
    if (!confirm('Are you sure you want to delete this provider?')) return;
    try {
      await configurationApi.deleteLLMProvider(id);
      await loadLLMProviders();
    } catch (err: any) {
      console.error('Failed to delete LLM provider:', err);
      setApiError(true);
    }
  }, [loadLLMProviders]);

  const handleTestLlm = useCallback(async (id: string) => {
    setTestingId(id);
    try {
      const result = await configurationApi.testLLMProvider(id);
      // Map test result to UI state
      const isHealthy = result.success;
      setLlmProviders((prev) =>
        prev.map((p) =>
          p.id === id
            ? {
                ...p,
                healthStatus: isHealthy ? 'healthy' : 'unhealthy',
                latencyMs: result.latency_ms,
                errorMessage: isHealthy ? undefined : (result.error || 'Connection failed'),
              }
            : p
        )
      );
    } catch (err: any) {
      console.error('Failed to test LLM provider:', err);
      // Mark as unhealthy on fetch error too
      setLlmProviders((prev) =>
        prev.map((p) =>
          p.id === id
            ? {
                ...p,
                healthStatus: 'unhealthy',
                errorMessage: err.message || 'Test request failed',
              }
            : p
        )
      );
    } finally {
      setTestingId(null);
    }
  }, []);

  const handleToggleLlm = useCallback(async (id: string) => {
    // Optimistic update for snappy UX
    setLlmProviders((prev) =>
      prev.map((p) => (p.id === id ? { ...p, isEnabled: !p.isEnabled } : p))
    );
    const current = llmProviders.find((p) => p.id === id);
    if (!current) return;
    try {
      await configurationApi.updateLLMProvider(id, {
        type: current.type,
        name: current.name,
        baseUrl: current.baseUrl,
        isEnabled: !current.isEnabled,
      });
    } catch (err: any) {
      console.error('Failed to toggle LLM provider:', err);
      // Revert on failure
      setLlmProviders((prev) =>
        prev.map((p) => (p.id === id ? { ...p, isEnabled: current.isEnabled } : p))
      );
      setApiError(true);
    }
  }, [llmProviders]);

  // ---- Embedding CRUD handlers ----

  const handleSaveEmbeddingProvider = useCallback(async (provider: Partial<EmbeddingProvider>) => {
    try {
      if (editingEmbeddingProvider) {
        await configurationApi.updateEmbeddingProvider(editingEmbeddingProvider.id, {
          type: provider.type!,
          name: provider.name!,
          baseUrl: provider.baseUrl!,
          apiKey: provider.apiKey,
          defaultModel: provider.model,
          isEnabled: provider.isEnabled,
        });
      } else {
        await configurationApi.createEmbeddingProvider({
          type: provider.type!,
          name: provider.name!,
          baseUrl: provider.baseUrl!,
          apiKey: provider.apiKey,
          defaultModel: provider.model,
          isEnabled: provider.isEnabled,
        });
      }
      setShowEmbeddingForm(false);
      setEditingEmbeddingProvider(undefined);
      await loadEmbeddingProviders();
    } catch (err: any) {
      console.error('Failed to save embedding provider:', err);
      setApiError(true);
    }
  }, [editingEmbeddingProvider, loadEmbeddingProviders]);

  const handleDeleteEmbedding = useCallback(async (id: string) => {
    if (!confirm('Are you sure you want to delete this provider?')) return;
    try {
      await configurationApi.deleteEmbeddingProvider(id);
      await loadEmbeddingProviders();
    } catch (err: any) {
      console.error('Failed to delete embedding provider:', err);
      setApiError(true);
    }
  }, [loadEmbeddingProviders]);

  const handleTestEmbedding = useCallback(async (id: string) => {
    setTestingId(id);
    try {
      const result = await configurationApi.testEmbeddingProvider(id);
      const isHealthy = result.success;
      setEmbeddingProviders((prev) =>
        prev.map((p) =>
          p.id === id
            ? {
                ...p,
                healthStatus: isHealthy ? 'healthy' : 'unhealthy',
              }
            : p
        )
      );
    } catch (err: any) {
      console.error('Failed to test embedding provider:', err);
      setEmbeddingProviders((prev) =>
        prev.map((p) =>
          p.id === id
            ? { ...p, healthStatus: 'unhealthy' }
            : p
        )
      );
    } finally {
      setTestingId(null);
    }
  }, []);

  const handleToggleEmbedding = useCallback(async (id: string) => {
    setEmbeddingProviders((prev) =>
      prev.map((p) => (p.id === id ? { ...p, isEnabled: !p.isEnabled } : p))
    );
    const current = embeddingProviders.find((p) => p.id === id);
    if (!current) return;
    try {
      await configurationApi.updateEmbeddingProvider(id, {
        type: current.type,
        name: current.name,
        baseUrl: current.baseUrl,
        isEnabled: !current.isEnabled,
      });
    } catch (err: any) {
      console.error('Failed to toggle embedding provider:', err);
      setEmbeddingProviders((prev) =>
        prev.map((p) => (p.id === id ? { ...p, isEnabled: current.isEnabled } : p))
      );
      setApiError(true);
    }
  }, [embeddingProviders]);

  // UI
  const defaultProvider = llmProviders.find((p) => p.isDefault && p.isEnabled);

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-white">Model Garage</h2>
          <p className="text-sm text-gray-400">Manage LLM and embedding provider connections</p>
          {apiError && (
            <span className="ml-2 inline-block px-2 py-0.5 text-xs bg-orange-900/40 border border-orange-500/40 text-orange-400 rounded">
              offline
            </span>
          )}
        </div>
        {defaultProvider && (
          <div className="text-right">
            <div className="text-xs text-gray-400">Default Provider</div>
            <div className="text-white font-medium">{defaultProvider.name}</div>
            <div className="text-xs text-gray-500 font-mono">{defaultProvider.selectedModel}</div>
          </div>
        )}
      </div>

      {/* Global Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6 p-4 bg-gray-800 rounded-lg relative">
        {statsLoading && (
          <div className="absolute top-2 right-2 text-xs text-gray-500 animate-pulse">loading...</div>
        )}
        {statsError && (
          <div className="absolute top-2 right-2 text-xs text-orange-400" title="Could not reach the observability API">offline</div>
        )}
        <div>
          <div className="text-xs text-gray-400">Total Requests</div>
          <div className="text-xl font-bold text-blue-400">{globalStats.totalRequests.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Total Tokens</div>
          <div className="text-xl font-bold text-green-400">{globalStats.totalTokens.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Avg Latency</div>
          <div className="text-xl font-bold text-yellow-400">{globalStats.avgLatency}ms</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Est. Cost</div>
          <div className="text-xl font-bold text-purple-400">${globalStats.costEstimate.toFixed(2)}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 mb-6">
        <button
          onClick={() => setActiveTab('llm')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === 'llm'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          LLM Providers ({llmProviders.length})
        </button>
        <button
          onClick={() => setActiveTab('embedding')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === 'embedding'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          Embedding Providers ({embeddingProviders.length})
        </button>
      </div>

      {/* Content */}
      {activeTab === 'llm' && (
        <div>
          {loadingLlm ? (
            <div className="text-center py-8 text-gray-400">
              <div className="animate-spin inline-block w-5 h-5 border-2 border-gray-400 border-t-blue-400 rounded-full mr-2" />
              Loading providers...
            </div>
          ) : (
            <>
              {/* Provider List */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                {llmProviders.map((provider) => (
                  <ProviderCard
                    key={provider.id}
                    provider={provider}
                    onEdit={setEditingLlmProvider}
                    onTest={handleTestLlm}
                    onToggle={handleToggleLlm}
                    onDelete={handleDeleteLlm}
                    isTesting={testingId === provider.id}
                  />
                ))}
                {llmProviders.length === 0 && !loadingLlm && (
                  <div className="col-span-full text-center py-8 text-gray-500">
                    <p className="text-lg">No LLM providers configured</p>
                    <p className="text-sm mt-1">Click "Add LLM Provider" below to add your first provider.</p>
                  </div>
                )}
              </div>

              {/* Add/Edit Form */}
              {showLlmForm || editingLlmProvider ? (
                <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <h3 className="text-lg font-medium text-white mb-4">
                    {editingLlmProvider ? 'Edit LLM Provider' : 'Add LLM Provider'}
                  </h3>
                  <ProviderForm
                    provider={editingLlmProvider}
                    onSave={handleSaveLlmProvider}
                    onCancel={() => {
                      setShowLlmForm(false);
                      setEditingLlmProvider(undefined);
                    }}
                  />
                </div>
              ) : (
                <button
                  onClick={() => setShowLlmForm(true)}
                  className="w-full py-4 border-2 border-dashed border-gray-600 rounded-lg text-gray-400 hover:text-white hover:border-gray-500 transition-colors flex items-center justify-center gap-2"
                >
                  <span className="text-xl">+</span>
                  <span>Add LLM Provider</span>
                </button>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === 'embedding' && (
        <div>
          {loadingEmbedding ? (
            <div className="text-center py-8 text-gray-400">
              <div className="animate-spin inline-block w-5 h-5 border-2 border-gray-400 border-t-blue-400 rounded-full mr-2" />
              Loading providers...
            </div>
          ) : (
            <>
              {/* Provider List */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                {embeddingProviders.map((provider) => (
                  <EmbeddingProviderCard
                    key={provider.id}
                    provider={provider}
                    onEdit={setEditingEmbeddingProvider}
                    onTest={handleTestEmbedding}
                    onToggle={handleToggleEmbedding}
                    onDelete={handleDeleteEmbedding}
                    isTesting={testingId === provider.id}
                  />
                ))}
                {embeddingProviders.length === 0 && !loadingEmbedding && (
                  <div className="col-span-full text-center py-8 text-gray-500">
                    <p className="text-lg">No embedding providers configured</p>
                    <p className="text-sm mt-1">Click "Add Embedding Provider" below to add one.</p>
                  </div>
                )}
              </div>

              {/* Add/Edit Form */}
              {showEmbeddingForm || editingEmbeddingProvider ? (
                <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <h3 className="text-lg font-medium text-white mb-4">
                    {editingEmbeddingProvider ? 'Edit Embedding Provider' : 'Add Embedding Provider'}
                  </h3>
                  <EmbeddingProviderForm
                    provider={editingEmbeddingProvider}
                    onSave={handleSaveEmbeddingProvider}
                    onCancel={() => {
                      setShowEmbeddingForm(false);
                      setEditingEmbeddingProvider(undefined);
                    }}
                  />
                </div>
              ) : (
                <button
                  onClick={() => setShowEmbeddingForm(true)}
                  className="w-full py-4 border-2 border-dashed border-gray-600 rounded-lg text-gray-400 hover:text-white hover:border-gray-500 transition-colors flex items-center justify-center gap-2"
                >
                  <span className="text-xl">+</span>
                  <span>Add Embedding Provider</span>
                </button>
              )}
            </>
          )}
        </div>
      )}

      {/* Quick Add Buttons */}
      <div className="mt-6 pt-6 border-t border-gray-700">
        <h4 className="text-sm font-medium text-gray-400 mb-3">Quick Add</h4>
        <div className="flex flex-wrap gap-2">
          {(Object.entries(LLM_PROVIDER_CONFIGS) as [ProviderType, typeof LLM_PROVIDER_CONFIGS.openai][]).map(([type, config]) => (
            <button
              key={type}
              onClick={() => {
                setEditingLlmProvider({
                  id: `${type}-${Date.now()}`,
                  name: config.name,
                  type,
                  baseUrl: config.defaultUrl,
                  models: config.models,
                  selectedModel: config.models[0],
                  isEnabled: true,
                  isDefault: false,
                  healthStatus: 'unknown',
                });
              }}
              className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg border border-gray-700 transition-colors"
              style={{ borderLeftColor: config.color, borderLeftWidth: 3 }}
            >
              + {config.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default ModelGarage;
