/**
 * AgentConfigPanel Component
 *
 * Configuration editor for agent instances.
 */

import React, { useState, useCallback, useEffect } from 'react';

export interface AgentConfig {
  agent_id: string;
  name?: string;
  description?: string;
  topics?: string[];
  capabilities?: string[];
  max_mailbox_size?: number;
  heartbeat_interval?: number;
  persistence_interval?: number;
  [key: string]: unknown;
}

interface AgentConfigPanelProps {
  instanceId: string;
  config: AgentConfig;
  onUpdate: (instanceId: string, config: AgentConfig) => Promise<void>;
  onClose: () => void;
}

export function AgentConfigPanel({
  instanceId,
  config,
  onUpdate,
  onClose,
}: AgentConfigPanelProps) {
  const [editedConfig, setEditedConfig] = useState<AgentConfig>({ ...config });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    setEditedConfig({ ...config });
    setHasChanges(false);
    setError(null);
  }, [config]);

  const updateConfigValue = useCallback((key: string, value: unknown) => {
    setEditedConfig(prev => ({ ...prev, [key]: value }));
    setHasChanges(true);
  }, []);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    setError(null);

    try {
      await onUpdate(instanceId, editedConfig);
      setHasChanges(false);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  }, [instanceId, editedConfig, onUpdate, onClose]);

  const handleReset = useCallback(() => {
    setEditedConfig({ ...config });
    setHasChanges(false);
    setError(null);
  }, [config]);

  const renderConfigField = (key: string, value: unknown) => {
    if (key === 'agent_id') {
      return (
        <div key={key}>
          <label className="block text-sm text-gray-400 mb-1">Agent ID</label>
          <input
            type="text"
            value={value as string}
            disabled
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-gray-500 cursor-not-allowed"
          />
          <p className="text-xs text-gray-500 mt-1">Cannot be changed</p>
        </div>
      );
    }

    if (key === 'name' || key === 'description') {
      return (
        <div key={key}>
          <label className="block text-sm text-gray-400 mb-1 capitalize">
            {key.replace(/_/g, ' ')}
          </label>
          {key === 'description' ? (
            <textarea
              value={value as string || ''}
              onChange={(e) => updateConfigValue(key, e.target.value)}
              rows={3}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors resize-none"
            />
          ) : (
            <input
              type="text"
              value={value as string || ''}
              onChange={(e) => updateConfigValue(key, e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
            />
          )}
        </div>
      );
    }

    if (key === 'max_mailbox_size' || key === 'heartbeat_interval' || key === 'persistence_interval') {
      return (
        <div key={key}>
          <label className="block text-sm text-gray-400 mb-1 capitalize">
            {key.replace(/_/g, ' ')}
          </label>
          <input
            type="number"
            value={value as number || 0}
            onChange={(e) => updateConfigValue(key, parseFloat(e.target.value) || 0)}
            min={0}
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
      );
    }

    if (Array.isArray(value)) {
      return (
        <div key={key}>
          <label className="block text-sm text-gray-400 mb-1 capitalize">
            {key.replace(/_/g, ' ')}
          </label>
          <textarea
            value={value.join(', ')}
            onChange={(e) => updateConfigValue(key, e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
            rows={3}
            placeholder="item1, item2, item3"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors resize-none"
          />
          <p className="text-xs text-gray-500 mt-1">Comma-separated values</p>
        </div>
      );
    }

    // Default: read-only display for unknown types
    return (
      <div key={key}>
        <label className="block text-sm text-gray-400 mb-1 capitalize">
          {key.replace(/_/g, ' ')}
        </label>
        <div className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-gray-400">
          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
        </div>
      </div>
    );
  };

  // Sort config keys: agent_id first, then alphabetically
  const configKeys = Object.keys(editedConfig).sort((a, b) => {
    if (a === 'agent_id') return -1;
    if (b === 'agent_id') return 1;
    return a.localeCompare(b);
  });

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-800 border border-gray-700 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700 sticky top-0 bg-gray-800 z-10">
          <div>
            <h2 className="text-xl font-bold text-white">Configure Agent</h2>
            <p className="text-sm text-gray-400 mt-1 font-mono">{instanceId}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Basic Settings */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Basic Settings</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {configKeys.filter(k => ['agent_id', 'name', 'description'].includes(k)).map(key => (
                renderConfigField(key, editedConfig[key])
              ))}
            </div>
          </div>

          {/* Runtime Settings */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Runtime Settings</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {configKeys.filter(k => ['max_mailbox_size', 'heartbeat_interval', 'persistence_interval'].includes(k)).map(key => (
                renderConfigField(key, editedConfig[key])
              ))}
            </div>
          </div>

          {/* Topics & Capabilities */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Topics & Capabilities</h3>
            <div className="grid grid-cols-1 gap-4">
              {configKeys.filter(k => ['topics', 'capabilities'].includes(k)).map(key => (
                renderConfigField(key, editedConfig[key])
              ))}
            </div>
          </div>

          {/* Other Settings */}
          {configKeys.filter(k => !['agent_id', 'name', 'description', 'max_mailbox_size', 'heartbeat_interval', 'persistence_interval', 'topics', 'capabilities'].includes(k)).length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-300 mb-4">Other Settings</h3>
              <div className="grid grid-cols-1 gap-4">
                {configKeys.filter(k => !['agent_id', 'name', 'description', 'max_mailbox_size', 'heartbeat_interval', 'persistence_interval', 'topics', 'capabilities'].includes(k)).map(key => (
                  renderConfigField(key, editedConfig[key])
                ))}
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg p-3">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {/* Info Note */}
          <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-3">
            <p className="text-blue-400 text-sm">
              💡 <strong>Note:</strong> Some configuration changes may require restarting the agent to take effect.
            </p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between p-6 border-t border-gray-700 sticky bottom-0 bg-gray-800">
          <button
            onClick={handleReset}
            disabled={!hasChanges || isSaving}
            className="px-4 py-2 text-gray-400 hover:text-white disabled:text-gray-600 transition-colors"
          >
            Reset
          </button>
          <div className="flex items-center gap-3">
            {hasChanges && (
              <span className="text-sm text-yellow-400">Unsaved changes</span>
            )}
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!hasChanges || isSaving}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {isSaving ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Saving...
                </>
              ) : (
                <>
                  💾 Save Changes
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AgentConfigPanel;
