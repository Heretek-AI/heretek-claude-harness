/**
 * System Configuration Section
 *
 * Component for managing system-wide configurations.
 * Allows users to view and edit system settings.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useToast } from '../UI/Toast';
import configurationApi, { UserConfiguration } from '../../api/configuration';

interface SystemConfigSectionProps {
  onConfigChange?: () => void;
}

interface ConfigField {
  key: string;
  label: string;
  description: string;
  type: 'string' | 'number' | 'boolean';
  category: string;
  min?: number;
  max?: number;
}

const CONFIG_FIELDS: ConfigField[] = [
  {
    key: 'rate_limit.enabled',
    label: 'Enable Rate Limiting',
    description: 'Control API request rate limiting',
    type: 'boolean',
    category: 'rate_limiting',
  },
  {
    key: 'rate_limit.default_rpm',
    label: 'Default Rate Limit (requests/min)',
    description: 'Maximum requests per minute per client',
    type: 'number',
    category: 'rate_limiting',
    min: 1,
    max: 10000,
  },
  {
    key: 'rate_limit.default_tpm',
    label: 'Default Token Limit (tokens/min)',
    description: 'Maximum tokens per minute per client',
    type: 'number',
    category: 'rate_limiting',
    min: 1000,
    max: 1000000,
  },
  {
    key: 'memory.max_size',
    label: 'Memory Max Size',
    description: 'Maximum memory entries per agent',
    type: 'number',
    category: 'memory',
    min: 100,
    max: 100000,
  },
  {
    key: 'memory.default_ttl',
    label: 'Memory Default TTL (seconds)',
    description: 'Default time-to-live for memory entries',
    type: 'number',
    category: 'memory',
    min: 60,
    max: 86400,
  },
  {
    key: 'consciousness.phi_threshold',
    label: 'Consciousness Phi Threshold',
    description: 'Threshold for phi consciousness calculation',
    type: 'number',
    category: 'consciousness',
    min: 0,
    max: 1,
  },
  {
    key: 'consensus.min_votes',
    label: 'Consensus Minimum Votes',
    description: 'Minimum votes required for consensus',
    type: 'number',
    category: 'consensus',
    min: 1,
    max: 100,
  },
  {
    key: 'consensus.confidence_threshold',
    label: 'Consensus Confidence Threshold',
    description: 'Confidence threshold for consensus decisions',
    type: 'number',
    category: 'consensus',
    min: 0,
    max: 1,
  },
];

export function SystemConfigSection({ onConfigChange }: SystemConfigSectionProps) {
  const [configs, setConfigs] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const toast = useToast();

  const loadConfigs = useCallback(async () => {
    try {
      setLoading(true);
      const allConfigs = await configurationApi.getConfigs();
      const configMap: Record<string, any> = {};
      allConfigs.forEach((config: UserConfiguration) => {
        configMap[config.config_key] = config.config_value;
      });
      setConfigs(configMap);
    } catch (error) {
      toast.error('Failed to load configurations', 'Could not fetch system settings');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  const handleSave = useCallback(async (key: string, value: any) => {
    try {
      setSaving(key);
      await configurationApi.updateConfig(key, value);
      toast.success('Configuration saved', `${key} has been updated`);
      setConfigs(prev => ({ ...prev, [key]: value }));
      onConfigChange?.();
    } catch (error: any) {
      toast.error('Failed to save configuration', error.message || 'An error occurred');
    } finally {
      setSaving(null);
    }
  }, [toast, onConfigChange]);

  const handleMigrateFromEnv = useCallback(async () => {
    if (!confirm('This will migrate environment variables to database configurations. Continue?')) return;

    try {
      const result = await configurationApi.migrateFromEnv();
      const migrated = result.migrated?.length || 0;
      const skipped = result.skipped?.length || 0;

      if (migrated > 0) {
        toast.success('Migration complete', `Migrated ${migrated} configurations, skipped ${skipped}`);
        loadConfigs();
        onConfigChange?.();
      } else {
        toast.info('Migration complete', 'No new configurations to migrate');
      }
    } catch (error: any) {
      toast.error('Migration failed', error.message || 'An error occurred');
    }
  }, [toast, loadConfigs, onConfigChange]);

  const renderValue = useCallback((field: ConfigField) => {
    const value = configs[field.key];
    const isSaving = saving === field.key;

    if (field.type === 'boolean') {
      return (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => handleSave(field.key, e.target.checked)}
            disabled={isSaving}
            className="w-4 h-4 rounded border-gray-600 bg-gray-900 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
          />
          <span className="text-sm text-gray-400">{value ? 'Enabled' : 'Disabled'}</span>
        </label>
      );
    }

    if (field.type === 'number') {
      return (
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={value ?? ''}
            onChange={(e) => {
              const numValue = e.target.value === '' ? '' : Number(e.target.value);
              handleSave(field.key, numValue);
            }}
            min={field.min}
            max={field.max}
            disabled={isSaving}
            placeholder="Not set"
            className="w-32 px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          {isSaving && (
            <span className="text-xs text-blue-400">Saving...</span>
          )}
        </div>
      );
    }

    return (
      <input
        type="text"
        value={value ?? ''}
        onChange={(e) => handleSave(field.key, e.target.value)}
        disabled={isSaving}
        placeholder="Not set"
        className="w-full max-w-xs px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
      />
    );
  }, [configs, saving, handleSave]);

  const groupedConfigs = CONFIG_FIELDS.reduce((acc, field) => {
    if (!acc[field.category]) {
      acc[field.category] = [];
    }
    acc[field.category].push(field);
    return acc;
  }, {} as Record<string, ConfigField[]>);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">System Configuration</h2>
          <p className="text-sm text-gray-400 mt-1">
            Manage system-wide settings and preferences
          </p>
        </div>
        <button
          onClick={handleMigrateFromEnv}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors"
        >
          Migrate from .env
        </button>
      </div>

      {/* Configuration Sections */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">Loading configurations...</div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedConfigs).map(([category, fields]) => (
            <div
              key={category}
              className="bg-gray-900/50 border border-gray-700 rounded-xl p-6"
            >
              <h3 className="text-md font-semibold text-white capitalize mb-4">
                {category.replace('_', ' ')}
              </h3>
              <div className="space-y-4">
                {fields.map((field) => (
                  <div key={field.key}>
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <label className="text-sm font-medium text-gray-300">
                          {field.label}
                        </label>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {field.description}
                        </p>
                      </div>
                      {renderValue(field)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info Box */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <span className="text-blue-400 text-lg">ℹ️</span>
          <div>
            <h4 className="text-sm font-medium text-blue-400 mb-1">
              Configuration Storage
            </h4>
            <p className="text-xs text-gray-400">
              System configurations are stored in the database and persist across restarts.
              Use "Migrate from .env" to transfer existing environment variable configurations.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SystemConfigSection;
