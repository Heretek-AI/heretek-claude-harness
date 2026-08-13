/**
 * Node Configuration Panel - Form-based configuration for workflow nodes
 *
 * Based on Ant-Design Pro-Flow patterns for node configuration panels.
 * Provides type-specific forms for configuring agent nodes in the workflow builder.
 *
 * Features:
 * - Click on agent node → opens configuration panel
 * - Form fields based on agent type (different agents have different configs)
 * - Validation for required fields
 * - Save/Cancel actions
 * - Persist configuration via API to agent_config table
 *
 * Form Fields by Agent Type:
 * - Arbiter: Decision threshold, quorum size, timeout
 * - Prism: Analysis depth, perspective count, confidence threshold
 * - Habit-Forge: Repetition threshold, reward schedule, extinction criteria
 * - All Agents: LLM provider selection, model selection, temperature, max tokens
 */

import React, { useState, useEffect, useCallback } from 'react';

// Agent configuration types
export interface AgentConfig {
  agentId: string;
  agentType: string;
  llmProvider: string;
  model: string;
  temperature: number;
  maxTokens: number;
  // Arbiter-specific
  decisionThreshold?: number;
  quorumSize?: number;
  timeout?: number;
  // Prism-specific
  analysisDepth?: number;
  perspectiveCount?: number;
  confidenceThreshold?: number;
  // Habit-Forge-specific
  repetitionThreshold?: number;
  rewardSchedule?: string;
  extinctionCriteria?: number;
}

interface NodeConfigPanelProps {
  node: {
    id: string;
    type: string;
    data: {
      agentId?: string;
      agentType?: string;
      config?: Record<string, any>;
    };
  } | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (config: AgentConfig) => Promise<void>;
}

const LLM_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google AI' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'local', label: 'Local (LLaMA.cpp)' },
];

const OPENAI_MODELS = [
  { value: 'gpt-4', label: 'GPT-4' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
];

const ANTHROPIC_MODELS = [
  { value: 'claude-3-opus', label: 'Claude 3 Opus' },
  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
  { value: 'claude-3-haiku', label: 'Claude 3 Haiku' },
];

const GOOGLE_MODELS = [
  { value: 'gemini-pro', label: 'Gemini Pro' },
  { value: 'gemini-ultra', label: 'Gemini Ultra' },
];

const AGENT_TYPES = [
  { value: 'arbiter', label: 'Arbiter', icon: '⚖️' },
  { value: 'prism', label: 'Prism', icon: '🔮' },
  { value: 'habit-forge', label: 'Habit-Forge', icon: '🔨' },
  { value: 'steward', label: 'Steward', icon: '🎯' },
  { value: 'coordinator', label: 'Coordinator', icon: '📊' },
  { value: 'sentinel', label: 'Sentinel', icon: '🛡️' },
];

/**
 * Node Configuration Panel Component
 */
export const NodeConfigPanel: React.FC<NodeConfigPanelProps> = ({
  node,
  isOpen,
  onClose,
  onSave,
}) => {
  const [config, setConfig] = useState<AgentConfig>({
    agentId: '',
    agentType: 'steward',
    llmProvider: 'openai',
    model: 'gpt-4',
    temperature: 0.7,
    maxTokens: 4096,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);

  // Initialize config from node data
  useEffect(() => {
    if (node) {
      const nodeData = node.data;
      setConfig({
        agentId: nodeData.agentId || node.id,
        agentType: nodeData.agentType || 'steward',
        llmProvider: nodeData.config?.llmProvider || 'openai',
        model: nodeData.config?.model || 'gpt-4',
        temperature: nodeData.config?.temperature ?? 0.7,
        maxTokens: nodeData.config?.maxTokens ?? 4096,
        // Arbiter-specific
        decisionThreshold: nodeData.config?.decisionThreshold ?? 0.75,
        quorumSize: nodeData.config?.quorumSize ?? 3,
        timeout: nodeData.config?.timeout ?? 30,
        // Prism-specific
        analysisDepth: nodeData.config?.analysisDepth ?? 3,
        perspectiveCount: nodeData.config?.perspectiveCount ?? 4,
        confidenceThreshold: nodeData.config?.confidenceThreshold ?? 0.6,
        // Habit-Forge-specific
        repetitionThreshold: nodeData.config?.repetitionThreshold ?? 21,
        rewardSchedule: nodeData.config?.rewardSchedule || 'variable',
        extinctionCriteria: nodeData.config?.extinctionCriteria ?? 7,
      });
    }
  }, [node]);

  // Validate configuration
  const validateConfig = useCallback((cfg: AgentConfig): Record<string, string> => {
    const newErrors: Record<string, string> = {};

    // Required fields
    if (!cfg.agentId || cfg.agentId.trim() === '') {
      newErrors.agentId = 'Agent ID is required';
    }

    // Numeric validations
    if (cfg.temperature < 0 || cfg.temperature > 2) {
      newErrors.temperature = 'Temperature must be between 0 and 2';
    }

    if (cfg.maxTokens < 1 || cfg.maxTokens > 128000) {
      newErrors.maxTokens = 'Max tokens must be between 1 and 128000';
    }

    // Agent-specific validations
    if (cfg.agentType === 'arbiter') {
      if (cfg.decisionThreshold !== undefined && (cfg.decisionThreshold < 0 || cfg.decisionThreshold > 1)) {
        newErrors.decisionThreshold = 'Decision threshold must be between 0 and 1';
      }
      if (cfg.quorumSize !== undefined && (cfg.quorumSize < 1 || cfg.quorumSize > 10)) {
        newErrors.quorumSize = 'Quorum size must be between 1 and 10';
      }
      if (cfg.timeout !== undefined && (cfg.timeout < 1 || cfg.timeout > 300)) {
        newErrors.timeout = 'Timeout must be between 1 and 300 seconds';
      }
    }

    if (cfg.agentType === 'prism') {
      if (cfg.analysisDepth !== undefined && (cfg.analysisDepth < 1 || cfg.analysisDepth > 10)) {
        newErrors.analysisDepth = 'Analysis depth must be between 1 and 10';
      }
      if (cfg.perspectiveCount !== undefined && (cfg.perspectiveCount < 1 || cfg.perspectiveCount > 12)) {
        newErrors.perspectiveCount = 'Perspective count must be between 1 and 12';
      }
      if (cfg.confidenceThreshold !== undefined && (cfg.confidenceThreshold < 0 || cfg.confidenceThreshold > 1)) {
        newErrors.confidenceThreshold = 'Confidence threshold must be between 0 and 1';
      }
    }

    if (cfg.agentType === 'habit-forge') {
      if (cfg.repetitionThreshold !== undefined && (cfg.repetitionThreshold < 1 || cfg.repetitionThreshold > 365)) {
        newErrors.repetitionThreshold = 'Repetition threshold must be between 1 and 365 days';
      }
      if (cfg.extinctionCriteria !== undefined && (cfg.extinctionCriteria < 1 || cfg.extinctionCriteria > 90)) {
        newErrors.extinctionCriteria = 'Extinction criteria must be between 1 and 90 days';
      }
    }

    return newErrors;
  }, []);

  // Handle field changes
  const handleFieldChange = useCallback((field: keyof AgentConfig, value: any) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
    // Clear error for this field
    setErrors((prev) => {
      const newErrors = { ...prev };
      delete newErrors[field];
      return newErrors;
    });
  }, []);

  // Handle save
  const handleSave = useCallback(async () => {
    const validationErrors = validateConfig(config);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setIsSaving(true);
    try {
      await onSave(config);
      onClose();
    } catch (error) {
      console.error('Failed to save configuration:', error);
      setErrors({ submit: 'Failed to save configuration. Please try again.' });
    } finally {
      setIsSaving(false);
    }
  }, [config, validateConfig, onSave, onClose]);

  // Get available models for selected provider
  const getAvailableModels = useCallback(() => {
    switch (config.llmProvider) {
      case 'openai':
        return OPENAI_MODELS;
      case 'anthropic':
        return ANTHROPIC_MODELS;
      case 'google':
        return GOOGLE_MODELS;
      default:
        return [];
    }
  }, [config.llmProvider]);

  if (!isOpen || !node) {
    return null;
  }

  const agentTypeInfo = AGENT_TYPES.find((t) => t.value === config.agentType);

  return (
    <div className="node-config-panel-overlay" onClick={onClose}>
      <div className="node-config-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="config-panel-header">
          <div className="config-panel-title">
            <span className="agent-icon">{agentTypeInfo?.icon || '🤖'}</span>
            <h3>Configure {agentTypeInfo?.label || 'Agent'}</h3>
          </div>
          <button className="config-panel-close" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="config-panel-content">
          {/* General Error */}
          {errors.submit && (
            <div className="config-error-banner">{errors.submit}</div>
          )}

          {/* Agent Type Selection */}
          <div className="config-section">
            <h4 className="config-section-title">Agent Type</h4>
            <div className="agent-type-grid">
              {AGENT_TYPES.map((type) => (
                <button
                  key={type.value}
                  className={`agent-type-option ${config.agentType === type.value ? 'selected' : ''}`}
                  onClick={() => handleFieldChange('agentType', type.value)}
                >
                  <span className="agent-type-icon">{type.icon}</span>
                  <span className="agent-type-label">{type.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Agent Identity */}
          <div className="config-section">
            <h4 className="config-section-title">Identity</h4>
            <div className="config-field">
              <label htmlFor="agent-id">Agent ID</label>
              <input
                id="agent-id"
                type="text"
                value={config.agentId}
                onChange={(e) => handleFieldChange('agentId', e.target.value)}
                className={errors.agentId ? 'error' : ''}
                placeholder="Enter agent ID"
              />
              {errors.agentId && (
                <span className="field-error">{errors.agentId}</span>
              )}
            </div>
          </div>

          {/* LLM Configuration */}
          <div className="config-section">
            <h4 className="config-section-title">LLM Configuration</h4>
            <div className="config-field">
              <label htmlFor="llm-provider">Provider</label>
              <select
                id="llm-provider"
                value={config.llmProvider}
                onChange={(e) => handleFieldChange('llmProvider', e.target.value)}
              >
                {LLM_PROVIDERS.map((provider) => (
                  <option key={provider.value} value={provider.value}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="config-field">
              <label htmlFor="llm-model">Model</label>
              <select
                id="llm-model"
                value={config.model}
                onChange={(e) => handleFieldChange('model', e.target.value)}
              >
                {getAvailableModels().map((model) => (
                  <option key={model.value} value={model.value}>
                    {model.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="config-field-row">
              <div className="config-field">
                <label htmlFor="temperature">Temperature</label>
                <input
                  id="temperature"
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  value={config.temperature}
                  onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value))}
                  className={errors.temperature ? 'error' : ''}
                />
                {errors.temperature && (
                  <span className="field-error">{errors.temperature}</span>
                )}
              </div>

              <div className="config-field">
                <label htmlFor="max-tokens">Max Tokens</label>
                <input
                  id="max-tokens"
                  type="number"
                  min="1"
                  max="128000"
                  value={config.maxTokens}
                  onChange={(e) => handleFieldChange('maxTokens', parseInt(e.target.value, 10))}
                  className={errors.maxTokens ? 'error' : ''}
                />
                {errors.maxTokens && (
                  <span className="field-error">{errors.maxTokens}</span>
                )}
              </div>
            </div>
          </div>

          {/* Agent-Specific Configuration */}
          {config.agentType === 'arbiter' && (
            <div className="config-section">
              <h4 className="config-section-title">⚖️ Arbiter Configuration</h4>
              <div className="config-field-row">
                <div className="config-field">
                  <label htmlFor="decision-threshold">Decision Threshold</label>
                  <input
                    id="decision-threshold"
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={config.decisionThreshold ?? 0.75}
                    onChange={(e) => handleFieldChange('decisionThreshold', parseFloat(e.target.value))}
                    className={errors.decisionThreshold ? 'error' : ''}
                  />
                  {errors.decisionThreshold && (
                    <span className="field-error">{errors.decisionThreshold}</span>
                  )}
                </div>

                <div className="config-field">
                  <label htmlFor="quorum-size">Quorum Size</label>
                  <input
                    id="quorum-size"
                    type="number"
                    min="1"
                    max="10"
                    value={config.quorumSize ?? 3}
                    onChange={(e) => handleFieldChange('quorumSize', parseInt(e.target.value, 10))}
                    className={errors.quorumSize ? 'error' : ''}
                  />
                  {errors.quorumSize && (
                    <span className="field-error">{errors.quorumSize}</span>
                  )}
                </div>
              </div>

              <div className="config-field">
                <label htmlFor="timeout">Timeout (seconds)</label>
                <input
                  id="timeout"
                  type="number"
                  min="1"
                  max="300"
                  value={config.timeout ?? 30}
                  onChange={(e) => handleFieldChange('timeout', parseInt(e.target.value, 10))}
                  className={errors.timeout ? 'error' : ''}
                />
                {errors.timeout && (
                  <span className="field-error">{errors.timeout}</span>
                )}
              </div>
            </div>
          )}

          {config.agentType === 'prism' && (
            <div className="config-section">
              <h4 className="config-section-title">🔮 Prism Configuration</h4>
              <div className="config-field-row">
                <div className="config-field">
                  <label htmlFor="analysis-depth">Analysis Depth</label>
                  <input
                    id="analysis-depth"
                    type="number"
                    min="1"
                    max="10"
                    value={config.analysisDepth ?? 3}
                    onChange={(e) => handleFieldChange('analysisDepth', parseInt(e.target.value, 10))}
                    className={errors.analysisDepth ? 'error' : ''}
                  />
                  {errors.analysisDepth && (
                    <span className="field-error">{errors.analysisDepth}</span>
                  )}
                </div>

                <div className="config-field">
                  <label htmlFor="perspective-count">Perspective Count</label>
                  <input
                    id="perspective-count"
                    type="number"
                    min="1"
                    max="12"
                    value={config.perspectiveCount ?? 4}
                    onChange={(e) => handleFieldChange('perspectiveCount', parseInt(e.target.value, 10))}
                    className={errors.perspectiveCount ? 'error' : ''}
                  />
                  {errors.perspectiveCount && (
                    <span className="field-error">{errors.perspectiveCount}</span>
                  )}
                </div>
              </div>

              <div className="config-field">
                <label htmlFor="confidence-threshold">Confidence Threshold</label>
                <input
                  id="confidence-threshold"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={config.confidenceThreshold ?? 0.6}
                  onChange={(e) => handleFieldChange('confidenceThreshold', parseFloat(e.target.value))}
                  className={errors.confidenceThreshold ? 'error' : ''}
                />
                {errors.confidenceThreshold && (
                  <span className="field-error">{errors.confidenceThreshold}</span>
                )}
              </div>
            </div>
          )}

          {config.agentType === 'habit-forge' && (
            <div className="config-section">
              <h4 className="config-section-title">🔨 Habit-Forge Configuration</h4>
              <div className="config-field">
                <label htmlFor="repetition-threshold">Repetition Threshold (days)</label>
                <input
                  id="repetition-threshold"
                  type="number"
                  min="1"
                  max="365"
                  value={config.repetitionThreshold ?? 21}
                  onChange={(e) => handleFieldChange('repetitionThreshold', parseInt(e.target.value, 10))}
                  className={errors.repetitionThreshold ? 'error' : ''}
                />
                {errors.repetitionThreshold && (
                  <span className="field-error">{errors.repetitionThreshold}</span>
                )}
              </div>

              <div className="config-field">
                <label htmlFor="reward-schedule">Reward Schedule</label>
                <select
                  id="reward-schedule"
                  value={config.rewardSchedule || 'variable'}
                  onChange={(e) => handleFieldChange('rewardSchedule', e.target.value)}
                >
                  <option value="fixed">Fixed Interval</option>
                  <option value="variable">Variable Interval</option>
                  <option value="fixed-ratio">Fixed Ratio</option>
                  <option value="variable-ratio">Variable Ratio</option>
                </select>
              </div>

              <div className="config-field">
                <label htmlFor="extinction-criteria">Extinction Criteria (days)</label>
                <input
                  id="extinction-criteria"
                  type="number"
                  min="1"
                  max="90"
                  value={config.extinctionCriteria ?? 7}
                  onChange={(e) => handleFieldChange('extinctionCriteria', parseInt(e.target.value, 10))}
                  className={errors.extinctionCriteria ? 'error' : ''}
                />
                {errors.extinctionCriteria && (
                  <span className="field-error">{errors.extinctionCriteria}</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="config-panel-footer">
          <button className="config-btn config-btn-cancel" onClick={onClose} disabled={isSaving}>
            Cancel
          </button>
          <button className="config-btn config-btn-save" onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>

      <style>{`
        .node-config-panel-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          justify-content: flex-end;
          z-index: 1000;
        }

        .node-config-panel {
          width: 450px;
          max-width: 90vw;
          height: 100vh;
          max-height: 100vh;
          background: #ffffff;
          box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .config-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px;
          border-bottom: 1px solid #e5e7eb;
          background: #f9fafb;
        }

        .config-panel-title {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .config-panel-title h3 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: #1f2937;
        }

        .agent-icon {
          font-size: 24px;
        }

        .config-panel-close {
          background: none;
          border: none;
          font-size: 20px;
          cursor: pointer;
          color: #6b7280;
          padding: 4px;
          border-radius: 4px;
          transition: all 0.2s;
        }

        .config-panel-close:hover {
          background: #e5e7eb;
          color: #1f2937;
        }

        .config-panel-content {
          flex: 1;
          overflow-y: auto;
          padding: 20px;
        }

        .config-section {
          margin-bottom: 24px;
        }

        .config-section-title {
          font-size: 14px;
          font-weight: 600;
          color: #374151;
          margin: 0 0 12px 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .config-field {
          margin-bottom: 16px;
        }

        .config-field label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          color: #4b5563;
          margin-bottom: 6px;
        }

        .config-field input,
        .config-field select {
          width: 100%;
          padding: 10px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-size: 14px;
          transition: all 0.2s;
          box-sizing: border-box;
        }

        .config-field input:focus,
        .config-field select:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        .config-field input.error,
        .config-field select.error {
          border-color: #ef4444;
        }

        .config-field input.error:focus,
        .config-field select.error:focus {
          box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
        }

        .field-error {
          display: block;
          font-size: 12px;
          color: #ef4444;
          margin-top: 4px;
        }

        .config-field-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .agent-type-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
        }

        .agent-type-option {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 12px 8px;
          border: 2px solid #e5e7eb;
          border-radius: 8px;
          background: #f9fafb;
          cursor: pointer;
          transition: all 0.2s;
        }

        .agent-type-option:hover {
          border-color: #3b82f6;
          background: #eff6ff;
        }

        .agent-type-option.selected {
          border-color: #3b82f6;
          background: #dbeafe;
        }

        .agent-type-icon {
          font-size: 24px;
          margin-bottom: 4px;
        }

        .agent-type-label {
          font-size: 11px;
          font-weight: 500;
          color: #4b5563;
        }

        .config-error-banner {
          background: #fee2e2;
          border: 1px solid #fecaca;
          color: #991b1b;
          padding: 12px;
          border-radius: 6px;
          margin-bottom: 16px;
          font-size: 14px;
        }

        .config-panel-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding: 16px 20px;
          border-top: 1px solid #e5e7eb;
          background: #f9fafb;
        }

        .config-btn {
          padding: 10px 20px;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          border: none;
        }

        .config-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .config-btn-cancel {
          background: #e5e7eb;
          color: #374151;
        }

        .config-btn-cancel:hover:not(:disabled) {
          background: #d1d5db;
        }

        .config-btn-save {
          background: #3b82f6;
          color: white;
        }

        .config-btn-save:hover:not(:disabled) {
          background: #2563eb;
        }
      `}</style>
    </div>
  );
};

export default NodeConfigPanel;
