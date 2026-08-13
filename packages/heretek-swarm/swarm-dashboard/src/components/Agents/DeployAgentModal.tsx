/**
 * DeployAgentModal Component
 *
 * Modal for deploying new agent instances with configuration options.
 */

import React, { useState, useCallback, useMemo } from 'react';
import { AgentType } from './AgentCard';

export interface DeployConfig {
  name?: string;
  description?: string;
  topics?: string[];
  capabilities?: string[];
  max_mailbox_size?: number;
  heartbeat_interval?: number;
  persistence_interval?: number;
  [key: string]: unknown;
}

interface DeployAgentModalProps {
  agentType: AgentType | null;
  isOpen: boolean;
  onClose: () => void;
  onDeploy: (agentType: string, config: DeployConfig) => Promise<void>;
}

export function DeployAgentModal({
  agentType,
  isOpen,
  onClose,
  onDeploy,
}: DeployAgentModalProps) {
  const [config, setConfig] = useState<DeployConfig>({});
  const [customName, setCustomName] = useState('');
  const [customDescription, setCustomDescription] = useState('');
  const [customTopics, setCustomTopics] = useState('');
  const [maxMailboxSize, setMaxMailboxSize] = useState<number>(1000);
  const [heartbeatInterval, setHeartbeatInterval] = useState<number>(10.0);
  const [persistenceInterval, setPersistenceInterval] = useState<number | ''>('');
  const [isDeploying, setIsDeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens with new agent
  React.useEffect(() => {
    if (isOpen && agentType) {
      setCustomName('');
      setCustomDescription('');
      setCustomTopics('');
      setMaxMailboxSize(1000);
      setHeartbeatInterval(10.0);
      setPersistenceInterval('');
      setConfig({});
      setError(null);
    }
  }, [isOpen, agentType]);

  const handleDeploy = useCallback(async () => {
    if (!agentType) return;

    setIsDeploying(true);
    setError(null);

    try {
      const deployConfig: DeployConfig = {
        ...config,
      };

      // Add custom values if provided
      if (customName) {
        deployConfig.name = customName;
      }
      if (customDescription) {
        deployConfig.description = customDescription;
      }
      if (customTopics.trim()) {
        deployConfig.topics = customTopics.split(',').map(t => t.trim()).filter(Boolean);
      }
      if (maxMailboxSize !== 1000) {
        deployConfig.max_mailbox_size = maxMailboxSize;
      }
      if (heartbeatInterval !== 10.0) {
        deployConfig.heartbeat_interval = heartbeatInterval;
      }
      if (persistenceInterval !== '') {
        deployConfig.persistence_interval = typeof persistenceInterval === 'number' ? persistenceInterval : undefined;
      }

      await onDeploy(agentType.type_name, deployConfig);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to deploy agent');
    } finally {
      setIsDeploying(false);
    }
  }, [agentType, config, customName, customDescription, customTopics, maxMailboxSize, heartbeatInterval, persistenceInterval, onDeploy, onClose]);

  const isFormValid = useMemo(() => {
    return !!agentType;
  }, [agentType]);

  if (!isOpen || !agentType) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-800 border border-gray-700 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700 sticky top-0 bg-gray-800 z-10">
          <div>
            <h2 className="text-xl font-bold text-white">Deploy Agent</h2>
            <p className="text-sm text-gray-400 mt-1">{agentType.type_name}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
            disabled={isDeploying}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Agent Description */}
          <div className="bg-gray-900 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-300 mb-2">About this Agent</h3>
            <p className="text-gray-400 text-sm">{agentType.description || 'No description available'}</p>
            {agentType.capabilities.length > 0 && (
              <div className="mt-3">
                <div className="text-xs text-gray-500 mb-1">Capabilities</div>
                <div className="flex flex-wrap gap-1.5">
                  {agentType.capabilities.map((cap, idx) => (
                    <span key={idx} className="text-xs text-blue-300 bg-blue-900/30 px-2 py-1 rounded">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Basic Configuration */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-300">Basic Configuration</h3>

            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Instance Name <span className="text-gray-600">(optional)</span>
              </label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder={`Auto-generated if empty`}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
                disabled={isDeploying}
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Description <span className="text-gray-600">(optional)</span>
              </label>
              <textarea
                value={customDescription}
                onChange={(e) => setCustomDescription(e.target.value)}
                placeholder="Optional description for this instance"
                rows={2}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors resize-none"
                disabled={isDeploying}
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Topics <span className="text-gray-600">(comma-separated, optional)</span>
              </label>
              <input
                type="text"
                value={customTopics}
                onChange={(e) => setCustomTopics(e.target.value)}
                placeholder="topic1, topic2, topic3"
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
                disabled={isDeploying}
              />
            </div>
          </div>

          {/* Advanced Configuration */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-300">Advanced Settings</h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  Max Mailbox Size
                </label>
                <input
                  type="number"
                  value={maxMailboxSize}
                  onChange={(e) => setMaxMailboxSize(parseInt(e.target.value) || 1000)}
                  min={100}
                  max={10000}
                  step={100}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                  disabled={isDeploying}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  Heartbeat Interval (s)
                </label>
                <input
                  type="number"
                  value={heartbeatInterval}
                  onChange={(e) => setHeartbeatInterval(parseFloat(e.target.value) || 10.0)}
                  min={1}
                  max={60}
                  step={0.5}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
                  disabled={isDeploying}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  Persistence Interval <span className="text-gray-600">(optional)</span>
                </label>
                <input
                  type="number"
                  value={persistenceInterval}
                  onChange={(e) => setPersistenceInterval(e.target.value === '' ? '' : parseInt(e.target.value) || 0)}
                  min={0}
                  placeholder="Messages"
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
                  disabled={isDeploying}
                />
                <p className="text-xs text-gray-500 mt-1">Auto-save state after N messages</p>
              </div>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg p-3">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-700 sticky bottom-0 bg-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
            disabled={isDeploying}
          >
            Cancel
          </button>
          <button
            onClick={handleDeploy}
            disabled={!isFormValid || isDeploying}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            {isDeploying ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Deploying...
              </>
            ) : (
              <>
                🚀 Deploy Agent
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeployAgentModal;
