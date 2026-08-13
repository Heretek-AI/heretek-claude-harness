/**
 * Settings Page
 *
 * Configuration management for Heretek Swarm.
 * Provides UI for managing system settings, agent defaults, and configuration import/export.
 */

import React, { useState, useCallback } from 'react';

/**
 * Validates that a URL is safe for use in client-side requests.
 * Returns the URL if it starts with '/' (relative) or http(s):// (absolute),
 * otherwise returns empty string to prevent javascript: or data: URLs.
 */
function _safeUrl(raw: string): string {
  if (!raw || typeof raw !== 'string') return '';
  const trimmed = raw.trim();
  if (trimmed.startsWith('/') || /^https?:\/\//i.test(trimmed)) return trimmed;
  return '';
}
import { useToast } from '../UI/Toast';
import { DeveloperModeToggle } from './DeveloperModeToggle';
import {
  SystemConfigSection,
  AgentDefaultsSection,
  ImportExportSection,
  MCPToolsSection,
  ModelGarage,
} from '.';

interface TabConfig {
  id: string;
  label: string;
  icon: string;
}

interface SettingsPageProps {
  onRerunSetup?: () => void;
}

const tabs: TabConfig[] = [
  { id: 'system', label: 'System', icon: '⚙️' },
  { id: 'providers', label: 'Providers', icon: '🧠' },
  { id: 'agents', label: 'Agent Defaults', icon: '👥' },
  { id: 'mcp', label: 'MCP Tools', icon: '🔧' },
  { id: 'import', label: 'Import/Export', icon: '📁' },
];

export function SettingsPage({ onRerunSetup }: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState<string>('system');
  const [apiKey, setApiKey] = useState('');
  const [apiUrl, setApiUrl] = useState(localStorage.getItem('swarm_api_host') || '');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const toast = useToast();

  const handleSaveApiKey = useCallback(() => {
    localStorage.setItem('api_key', apiKey);
    toast.success('API Key Saved', 'Your API key is available for this session');
  }, [apiKey, toast]);

  const handleSaveApiUrl = useCallback(() => {
    const validatedUrl = _safeUrl(apiUrl);
    localStorage.setItem('swarm_api_host', validatedUrl);
    // Also update WebSocket URL
    const wsUrl = validatedUrl.replace(/^http/, 'ws');
    localStorage.setItem('swarm_ws_host', wsUrl);
    toast.success('API URL Saved', 'The API URL will be used on next refresh');
  }, [apiUrl, toast]);

  const handleClearApiKey = useCallback(() => {
    localStorage.removeItem('api_key');
    setApiKey('');
    toast.info('API Key Cleared', 'Your API key has been removed');
  }, [toast]);

  const handleResetConfiguration = useCallback(() => {
    // Clear all configuration
    localStorage.removeItem('swarm_api_host');
    localStorage.removeItem('api_key');
    localStorage.removeItem('swarm_ws_host');
    localStorage.removeItem('swarm_configured');
    toast.info('Configuration Reset', 'Setup wizard will run on next load');
    setShowResetConfirm(false);
    if (onRerunSetup) {
      onRerunSetup();
    }
  }, [toast, onRerunSetup]);

  const renderTabContent = () => {
    switch (activeTab) {
      case 'system':
        return <SystemConfigSection />;
      case 'providers':
        return <ModelGarage />;
      case 'agents':
        return <AgentDefaultsSection />;
      case 'mcp':
        return <MCPToolsSection />;
      case 'import':
        return <ImportExportSection />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-gray-400 text-sm mt-1">
          System configuration and provider management
        </p>
      </div>


      {/* Developer Mode Toggle */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span>🔧</span> Developer Tools
        </h2>

        <DeveloperModeToggle />
      </div>


      {/* Connection Settings */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span>🔌</span> Connection Settings
        </h2>

        <div className="space-y-4">
          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              API Key
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your API key"
                className="flex-1 px-4 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              <button
                onClick={handleSaveApiKey}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
              >
                Save
              </button>

              {apiKey && (
                <button
                  onClick={handleClearApiKey}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors"
                >
                  Clear
                </button>

              )}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Your API key is stored locally in your browser and used for authenticated requests.
            </p>

          </div>


          {/* API URL */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              API URL
            </label>

            <div className="flex gap-2">
              <input
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="Leave empty for relative path (nginx proxy)"
                className="flex-1 px-4 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              <button
                onClick={handleSaveApiUrl}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
              >
                Save
              </button>
            </div>

            <p className="text-xs text-gray-500 mt-1">
              Leave empty to use the relative path (recommended for nginx proxy setup).
            </p>
          </div>
        </div>

      </div>


      {/* Reset Configuration */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span>🔄</span> Configuration Management
        </h2>

        {!showResetConfirm ? (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-300">Reset Configuration</p>
              <p className="text-xs text-gray-500">
                Run the setup wizard again to reconfigure your connection settings
              </p>
            </div>
            <button
              onClick={() => setShowResetConfirm(true)}
              className="px-4 py-2 bg-yellow-600/20 hover:bg-yellow-600/30 border border-yellow-600/50 hover:border-yellow-500 text-yellow-400 rounded-lg text-sm font-medium transition-colors"
            >
              Reset Wizard
            </button>
          </div>
        ) : (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
            <p className="text-sm text-yellow-300 mb-3">
              Are you sure you want to reset the configuration? The setup wizard will run again on the next page load.
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleResetConfiguration}
                className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Yes, Reset
              </button>
              <button
                onClick={() => setShowResetConfirm(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>


      {/* Tab Navigation */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl">
        <div className="border-b border-gray-700">
          <nav className="flex overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>

              </button>

            ))}
          </nav>

        </div>


        {/* Tab Content */}
        <div className="p-6">
          {renderTabContent()}
        </div>

      </div>


      {/* About Section */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span>ℹ️</span> About
        </h2>

        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between py-2 border-b border-gray-700">
            <span className="text-gray-400">Version</span>
            <span className="text-white font-mono">0.2.0</span>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-gray-700">
            <span className="text-gray-400">Build</span>
            <span className="text-white font-mono">2026.04</span>
          </div>

          <div className="flex items-center justify-between py-2">
            <span className="text-gray-400">Repository</span>
            <a
              href="https://github.com/heretek/heretek-swarm"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 hover:underline"
            >
              GitHub →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SettingsPage;
