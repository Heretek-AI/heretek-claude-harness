/**
 * Agent Defaults Section
 *
 * Component for managing default agent configurations.
 * Allows users to set default LLM and embedding providers for agent types.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useToast } from '../UI/Toast';
import configurationApi, { AgentConfig, LLMProvider, EmbeddingProvider } from '../../api/configuration';

interface AgentDefaultsSectionProps {
  onConfigChange?: () => void;
}

interface AgentTypeConfig {
  agentType: string;
  llmProviderId?: string;
  embeddingProviderId?: string;
  configData: Record<string, any>;
}

const AGENT_TYPES = [
  'coordinator',
  'coder',
  'explorer',
  'sentinel',
  'empath',
  'historian',
  'nexus',
  'perceiver',
  'prism',
  'catalyst',
  'chronos',
  'dreamer',
  'echo',
  'examiner',
  'metis',
  'arbiter',
];

export function AgentDefaultsSection({ onConfigChange }: AgentDefaultsSectionProps) {
  const [agentConfigs, setAgentConfigs] = useState<AgentConfig[]>([]);
  const [llmProviders, setLlmProviders] = useState<LLMProvider[]>([]);
  const [embeddingProviders, setEmbeddingProviders] = useState<EmbeddingProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const toast = useToast();

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [configs, llms, embeddings] = await Promise.all([
        configurationApi.listAgentConfigs(),
        configurationApi.listLLMProviders(undefined, true),
        configurationApi.listEmbeddingProviders(undefined, true),
      ]);
      setAgentConfigs(configs);
      setLlmProviders(llms);
      setEmbeddingProviders(embeddings);
    } catch (error) {
      toast.error('Failed to load data', 'Could not fetch agent configurations');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const getConfigForType = useCallback((agentType: string) => {
    return agentConfigs.find(
      (config) => config.agent_type === agentType && config.is_default_for_type
    );
  }, [agentConfigs]);

  const handleSave = useCallback(async (agentType: string, updates: Partial<AgentConfig>) => {
    try {
      setSaving(agentType);
      const existing = getConfigForType(agentType);

      if (existing) {
        await configurationApi.updateAgentConfig(existing.id, {
          ...existing,
          ...updates,
        });
        toast.success('Configuration updated', `${agentType} defaults saved`);
      } else {
        await configurationApi.createAgentConfig({
          agent_type: agentType,
          config_name: `${agentType}-defaults`,
          is_default_for_type: true,
          is_active: true,
          ...updates,
        });
        toast.success('Configuration created', `${agentType} defaults saved`);
      }

      loadData();
      onConfigChange?.();
    } catch (error: any) {
      toast.error('Failed to save configuration', error.message || 'An error occurred');
    } finally {
      setSaving(null);
    }
  }, [toast, getConfigForType, loadData, onConfigChange]);

  const getProviderName = useCallback((id: string | undefined, providers: any[]) => {
    if (!id) return 'Not configured';
    const provider = providers.find((p) => p.id === id);
    return provider ? provider.provider_name : 'Unknown';
  }, []);

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading agent configurations...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-white">Agent Defaults</h2>
        <p className="text-sm text-gray-400 mt-1">
          Configure default LLM and embedding providers for each agent type
        </p>
      </div>

      {/* Agent Type Configurations */}
      <div className="grid gap-4">
        {AGENT_TYPES.map((agentType) => {
          const config = getConfigForType(agentType);
          const isSaving = saving === agentType;

          return (
            <div
              key={agentType}
              className="p-4 bg-gray-900/50 border border-gray-700 rounded-xl hover:border-gray-600 transition-colors"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-white capitalize">
                  {agentType.replace(/_/g, ' ')}
                </h3>
                {isSaving && (
                  <span className="text-xs text-blue-400">Saving...</span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* LLM Provider */}
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">
                    LLM Provider
                  </label>
                  <select
                    value={config?.llm_provider_id || ''}
                    onChange={(e) =>
                      handleSave(agentType, {
                        llm_provider_id: e.target.value || undefined,
                      })
                    }
                    disabled={isSaving}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                  >
                    <option value="">Not configured</option>
                    {llmProviders.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.provider_name} ({provider.default_model})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Embedding Provider */}
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">
                    Embedding Provider
                  </label>
                  <select
                    value={config?.embedding_provider_id || ''}
                    onChange={(e) =>
                      handleSave(agentType, {
                        embedding_provider_id: e.target.value || undefined,
                      })
                    }
                    disabled={isSaving}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                  >
                    <option value="">Not configured</option>
                    {embeddingProviders.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.provider_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Current Configuration Summary */}
              {config && (
                <div className="mt-3 pt-3 border-t border-gray-700 text-xs text-gray-500">
                  <div className="flex items-center gap-4">
                    <span>
                      LLM: {getProviderName(config.llm_provider_id, llmProviders)}
                    </span>
                    <span>
                      Embedding: {getProviderName(config.embedding_provider_id, embeddingProviders)}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Info Box */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <span className="text-blue-400 text-lg">ℹ️</span>
          <div>
            <h4 className="text-sm font-medium text-blue-400 mb-1">
              Default Provider Fallback
            </h4>
            <p className="text-xs text-gray-400">
              If no default is configured for an agent type, the system will use the default
              LLM and embedding providers from the provider settings. Changes are saved automatically.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AgentDefaultsSection;
