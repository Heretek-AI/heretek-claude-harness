/**
 * Setup Wizard Component
 *
 * First-run setup wizard for configuring:
 * - Step 1: API Endpoint Configuration
 * - Step 2: API Key Configuration
 * - Step 3: Database Connection Test
 * - Step 4: Agent Health Check
 * - Step 5: Success/Dashboard redirect
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useSetupStore, type WizardStep, type ConnectionTestResult, type AgentHealthResult } from '../../stores/setupStore';
import {
  testApiHealth,
  testWebSocket,
  testApiKey,
  testDatabaseConnection,
  checkAgentHealth,
  validateApiHost,
  validateApiKey,
  normalizeUrl,
  deriveWsUrl,
} from '../../utils/setupValidation';
import { useToast } from '../UI/Toast';

// =============================================================================
// Types
// =============================================================================

interface SetupWizardProps {
  onComplete: () => void;
}

interface StatusIndicatorProps {
  status: 'pending' | 'loading' | 'success' | 'error';
  label?: string;
}

// =============================================================================
// Sub-components
// =============================================================================

/**
 * Animated loading spinner
 */
function LoadingSpinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div className={`${sizeClasses[size]} border-2 border-blue-500 border-t-transparent rounded-full animate-spin`} />
  );
}

/**
 * Status indicator with animation
 */
function StatusIndicator({ status, label }: StatusIndicatorProps) {
  const statusConfig = {
    pending: {
      icon: (
        <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" strokeWidth="2" />
        </svg>
      ),
      textClass: 'text-gray-400',
    },
    loading: {
      icon: <LoadingSpinner size="sm" />,
      textClass: 'text-blue-400',
    },
    success: {
      icon: (
        <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
        </svg>
      ),
      textClass: 'text-green-400',
    },
    error: {
      icon: (
        <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
      textClass: 'text-red-400',
    },
    valid: {
      icon: (
        <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
        </svg>
      ),
      textClass: 'text-green-400',
    },
    invalid: {
      icon: (
        <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
      textClass: 'text-red-400',
    },
  };

  const config = statusConfig[status];

  return (
    <div className="flex items-center gap-2">
      {config.icon}
      {label && <span className={`text-sm ${config.textClass}`}>{label}</span>}
    </div>
  );
}

/**
 * Progress bar showing current step
 */
function StepProgress({ currentStep, totalSteps, currentStepIndex }: {
  currentStep: WizardStep;
  totalSteps: number;
  currentStepIndex: number;
}) {
  const progress = ((currentStepIndex) / (totalSteps - 1)) * 100;

  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-gray-500 mb-2">
        <span>Step {currentStepIndex + 1} of {totalSteps - 1}</span>
        <span>{Math.round(progress)}% complete</span>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-600 to-purple-600 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Navigation buttons
 */
function WizardNav({
  onBack,
  onNext,
  nextLabel = 'Next',
  nextDisabled = false,
  nextLoading = false,
  hideBack = false,
}: {
  onBack?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  nextLoading?: boolean;
  hideBack?: boolean;
}) {
  return (
    <div className="flex justify-between items-center pt-8 border-t border-gray-800">
      {!hideBack ? (
        <button
          onClick={onBack}
          className="px-6 py-2.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        >
          ← Back
        </button>
      ) : (
        <div />
      )}

      {onNext && (
        <button
          onClick={onNext}
          disabled={nextDisabled || nextLoading}
          className="px-8 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-semibold transition-colors flex items-center gap-2"
        >
          {nextLoading && <LoadingSpinner size="sm" />}
          {nextLabel}
        </button>
      )}
    </div>
  );
}

/**
 * Info card component
 */
function InfoCard({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
      <div className="flex items-center gap-3 mb-2">
        <span className="text-2xl">{icon}</span>
        <h3 className="font-semibold text-white">{title}</h3>
      </div>
      <div className="text-sm text-gray-400">
        {children}
      </div>
    </div>
  );
}

/**
 * Result card for connection tests
 */
function ResultCard({
  title,
  result,
  details
}: {
  title: string;
  result: ConnectionTestResult | null;
  details?: string
}) {
  const status = result === null ? 'pending' : result.success ? 'success' : 'error';

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-white">{title}</span>
        <StatusIndicator
          status={status}
          label={result ? (result.success ? `${result.latency}ms` : 'Failed') : 'Waiting'}
        />
      </div>
      {result?.error && (
        <p className="text-sm text-red-400 mt-1">{result.error}</p>
      )}
      {result?.details && (
        <p className="text-sm text-gray-400 mt-1 whitespace-pre-line">{result.details}</p>
      )}
      {details && !result?.details && (
        <p className="text-sm text-gray-400 mt-1">{details}</p>
      )}
    </div>
  );
}

/**
 * Agent health card
 */
function AgentHealthCard({ agent }: { agent: AgentHealthResult }) {
  const statusConfig = {
    online: { color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30', icon: '●' },
    offline: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', icon: '○' },
    degraded: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', icon: '◐' },
    unknown: { color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/30', icon: '?' },
  };

  const config = statusConfig[agent.status];

  return (
    <div className={`${config.bg} ${config.border} border rounded-lg p-3 flex items-center justify-between`}>
      <div className="flex items-center gap-3">
        <span className={`${config.color} text-lg`}>{config.icon}</span>
        <div>
          <div className="font-medium text-white">{agent.agentType}</div>
          <div className="text-xs text-gray-500">ID: {agent.agentId}</div>
        </div>
      </div>
      <div className="text-right">
        <div className={`font-medium ${config.color}`}>
          {agent.status.charAt(0).toUpperCase() + agent.status.slice(1)}
        </div>
        {agent.messageCount !== undefined && (
          <div className="text-xs text-gray-500">{agent.messageCount} messages</div>
        )}
        {agent.lastActivity && (
          <div className="text-xs text-gray-500">
            Last: {new Date(agent.lastActivity).toLocaleTimeString()}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Step Components
// =============================================================================

/**
 * Welcome step
 */
function WelcomeStep({ onStart }: { onStart: () => void }) {
  return (
    <div className="text-center space-y-8 py-8">
      {/* Hero icon */}
      <div className="relative mx-auto w-24 h-24">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl blur-lg opacity-30" />
        <div className="relative w-full h-full bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center">
          <span className="text-4xl">🚀</span>
        </div>
      </div>

      {/* Title */}
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
          Welcome to Heretek Swarm
        </h1>
        <p className="text-gray-400 mt-2">Intelligent Agent Orchestration Platform</p>
      </div>

      {/* Description */}
      <p className="text-gray-400 max-w-lg mx-auto leading-relaxed">
        Let's configure your swarm dashboard to connect to the Heretek backend services.
        This wizard will guide you through setting up API connectivity and verifying
        your agent infrastructure.
      </p>

      {/* Feature highlights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto pt-4">
        <InfoCard icon="🔗" title="API Setup">
          Connect to your Heretek Swarm backend with secure API credentials.
        </InfoCard>
        <InfoCard icon="📊" title="Health Check">
          Verify all agent services are running and responsive.
        </InfoCard>
        <InfoCard icon="🎯" title="Ready to Go">
          Get instant access to your swarm dashboard upon completion.
        </InfoCard>
      </div>

      {/* Start button */}
      <button
        onClick={onStart}
        className="px-10 py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 rounded-xl font-semibold text-lg transition-all transform hover:scale-105 shadow-lg shadow-blue-500/25"
      >
        Get Started →
      </button>

      <p className="text-xs text-gray-600">
        This setup takes approximately 2 minutes
      </p>
    </div>
  );
}

/**
 * API Endpoint Configuration step
 */
function ApiEndpointStep({
  apiHost,
  onChange,
  onNext,
  onBack,
}: {
  apiHost: string;
  onChange: (host: string) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const [localValue, setLocalValue] = useState(apiHost);
  const [validationStatus, setValidationStatus] = useState<'pending' | 'valid' | 'invalid'>('pending');
  const [validationError, setValidationError] = useState<string | null>(null);

  // Debounced validation
  useEffect(() => {
    const timer = setTimeout(() => {
      const result = validateApiHost(localValue);
      if (result.isValid) {
        setValidationStatus('valid');
        setValidationError(null);
      } else if (localValue.trim()) {
        setValidationStatus('invalid');
        setValidationError(result.error || 'Invalid URL');
      } else {
        setValidationStatus('pending');
        setValidationError(null);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [localValue]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setLocalValue(value);
    onChange(value);
  };

  const handleNext = () => {
    if (validationStatus === 'valid') {
      onChange(normalizeUrl(localValue));
      onNext();
    }
  };

  const presets = [
    { label: 'Local Development', value: 'http://localhost:8000', icon: '🏠' },
    { label: 'Docker Compose', value: 'http://localhost', icon: '🐳' },
    { label: 'Production', value: 'https://api.example.com', icon: '☁️' },
  ];

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-500/20 rounded-xl mb-4">
          <span className="text-3xl">🔗</span>
        </div>
        <h2 className="text-2xl font-bold text-white">API Endpoint Configuration</h2>
        <p className="text-gray-400 mt-2">Enter the base URL of your Heretek Swarm API</p>
      </div>

      {/* Input */}
      <div className="max-w-lg mx-auto">
        <label className="block text-sm font-medium text-gray-300 mb-2">
          API Host URL
        </label>
        <div className="relative">
          <input
            type="text"
            value={localValue}
            onChange={handleChange}
            placeholder="http://localhost:8000"
            className={`w-full px-4 py-3 bg-gray-800 border ${
              validationStatus === 'invalid' ? 'border-red-500' :
              validationStatus === 'valid' ? 'border-green-500' :
              'border-gray-700'
            } rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors`}
          />
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <StatusIndicator status={validationStatus === 'pending' ? 'pending' : validationStatus === 'valid' ? 'success' : 'error'} />
          </div>
        </div>
        {validationError && (
          <p className="mt-2 text-sm text-red-400">{validationError}</p>
        )}
        <p className="mt-2 text-xs text-gray-500">
          Include the protocol (http:// or https://) and port if needed
        </p>
      </div>

      {/* Presets */}
      <div className="max-w-lg mx-auto">
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Quick Presets
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {presets.map((preset) => (
            <button
              key={preset.label}
              onClick={() => {
                setLocalValue(preset.value);
                onChange(preset.value);
              }}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-sm transition-colors flex items-center gap-2"
            >
              <span>{preset.icon}</span>
              <span>{preset.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Info */}
      <div className="max-w-lg mx-auto">
        <InfoCard icon="💡" title="Finding Your API URL">
          If running locally with Docker Compose, use <code className="text-blue-400">http://localhost</code>.
          For local development, use <code className="text-blue-400">http://localhost:8000</code>.
        </InfoCard>
      </div>

      <WizardNav
        onBack={onBack}
        onNext={handleNext}
        nextLabel="Continue"
        nextDisabled={validationStatus !== 'valid'}
        hideBack
      />
    </div>
  );
}

/**
 * API Key Configuration step
 */
function ApiKeyStep({
  apiKey,
  apiHost,
  onChange,
  onNext,
  onBack,
}: {
  apiKey: string;
  apiHost: string;
  onChange: (key: string) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const [localValue, setLocalValue] = useState(apiKey);
  const [showKey, setShowKey] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [validationStatus, setValidationStatus] = useState<'pending' | 'valid' | 'invalid'>('pending');

  const { setProviders } = useSetupStore();

  // Debounced validation
  useEffect(() => {
    const timer = setTimeout(() => {
      const result = validateApiKey(localValue);
      setValidationStatus(result.isValid ? 'valid' : localValue.trim() ? 'invalid' : 'pending');
    }, 300);

    return () => clearTimeout(timer);
  }, [localValue]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalValue(e.target.value);
    onChange(e.target.value);
    setTestResult(null);
  };

  const handleTestKey = async () => {
    if (!localValue.trim() || !apiHost) return;

    setIsTesting(true);
    setTestResult(null);

    try {
      const result = await testApiKey(apiHost, localValue);
      setTestResult(result);

      // If test succeeded, fetch provider info from backend
      if (result.success) {
        try {
          const configModule = await import('../../api/configuration');
          const api = configModule.default || configModule.configurationApi;
          const llmProviders = await api.listLLMProviders();
          const embeddingProviders = await api.listEmbeddingProviders();
          // Convert LLMProvider[] to LLMProviderInfo[] for store compatibility
          const llmProviderInfos = llmProviders.map((p: { provider_name: string; provider_type: string; base_url: string; default_model?: string; is_default: boolean; is_enabled: boolean }) => ({
            provider_name: p.provider_name,
            provider_type: p.provider_type,
            base_url: p.base_url,
            default_model: p.default_model || '',
            is_default: p.is_default,
            is_enabled: p.is_enabled,
          }));
          const embeddingProviderInfos = embeddingProviders.map((p: { provider_name: string; provider_type: string; base_url: string; default_model?: string; is_default: boolean; is_enabled: boolean }) => ({
            provider_name: p.provider_name,
            provider_type: p.provider_type,
            base_url: p.base_url,
            default_model: p.default_model || '',
            is_default: p.is_default,
            is_enabled: p.is_enabled,
          }));
          setProviders(llmProviderInfos, embeddingProviderInfos);
        } catch (providerErr) {
          console.warn('Failed to fetch provider info:', providerErr);
        }
      }
    } catch {
      setTestResult({
        success: false,
        error: 'Failed to test API key',
      });
    }

    setIsTesting(false);
  };

  const handleNext = () => {
    onNext();
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-purple-500/20 rounded-xl mb-4">
          <span className="text-3xl">🔑</span>
        </div>
        <h2 className="text-2xl font-bold text-white">API Key Configuration</h2>
        <p className="text-gray-400 mt-2">Enter your Heretek Swarm API key for authentication</p>
      </div>

      {/* Input */}
      <div className="max-w-lg mx-auto">
        <label className="block text-sm font-medium text-gray-300 mb-2">
          API Key
        </label>
        <div className="relative">
          <input
            type={showKey ? 'text' : 'password'}
            value={localValue}
            onChange={handleChange}
            placeholder="Enter your API key"
            className={`w-full px-4 py-3 pr-20 bg-gray-800 border ${
              validationStatus === 'invalid' ? 'border-red-500' :
              validationStatus === 'valid' ? 'border-green-500' :
              'border-gray-700'
            } rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-colors font-mono`}
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
          >
            {showKey ? '🙈' : '👁️'}
          </button>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          Your API key is stored locally and never sent to external servers
        </p>
      </div>

      {/* Test button and result */}
      <div className="max-w-lg mx-auto">
        <button
          onClick={handleTestKey}
          disabled={!localValue.trim() || isTesting}
          className="w-full px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
        >
          {isTesting ? (
            <>
              <LoadingSpinner size="sm" />
              Testing...
            </>
          ) : (
            'Test API Key'
          )}
        </button>

        {testResult && (
          <div className={`mt-3 p-3 rounded-lg border ${
            testResult.success ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'
          }`}>
            <div className="flex items-center gap-2">
              <StatusIndicator status={testResult.success ? 'success' : 'error'} />
              <span className={testResult.success ? 'text-green-400' : 'text-red-400'}>
                {testResult.success ? 'API key is valid!' : testResult.error}
              </span>
            </div>
            {testResult.latency && (
              <p className="text-xs text-gray-500 mt-1">Response time: {testResult.latency}ms</p>
            )}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="max-w-lg mx-auto">
        <InfoCard icon="🔒" title="Security">
          Your API key is encrypted and stored only in your browser's local storage.
          It is transmitted securely to authenticate with your Heretek Swarm backend.
        </InfoCard>
      </div>

      <WizardNav
        onBack={onBack}
        onNext={handleNext}
        nextLabel="Continue"
        nextDisabled={validationStatus !== 'valid'}
      />
    </div>
  );
}

/**
 * Database Connection Test step
 */
function DatabaseTestStep({
  apiHost,
  apiKey,
  onNext,
  onBack,
}: {
  apiHost: string;
  apiKey: string;
  onNext: () => void;
  onBack: () => void;
}) {
  const [isTesting, setIsTesting] = useState(false);
  const [apiResult, setApiResult] = useState<ConnectionTestResult | null>(null);
  const [wsResult, setWsResult] = useState<ConnectionTestResult | null>(null);
  const [dbResult, setDbResult] = useState<ConnectionTestResult | null>(null);
  const [hasRunTests, setHasRunTests] = useState(false);

  const runTests = useCallback(async () => {
    setIsTesting(true);
    setApiResult(null);
    setWsResult(null);
    setDbResult(null);

    // Run tests in parallel
    const [api, ws, db] = await Promise.all([
      testApiHealth(apiHost, apiKey).catch((e) => ({ success: false, error: e.message })),
      testWebSocket(deriveWsUrl(apiHost), apiKey).catch((e) => ({ success: false, error: e.message })),
      testDatabaseConnection(apiHost, apiKey).catch((e) => ({ success: false, error: e.message })),
    ]);

    setApiResult(api);
    setWsResult(ws);
    setDbResult(db);
    setHasRunTests(true);
    setIsTesting(false);
  }, [apiHost, apiKey]);

  // Auto-run tests on mount
  useEffect(() => {
    if (!hasRunTests && apiHost) {
      runTests();
    }
  }, [apiHost, apiKey, hasRunTests, runTests]);

  const allPassed = apiResult?.success && wsResult?.success && dbResult?.success;
  const corePassed = apiResult?.success && dbResult?.success;
  const anyPassed = apiResult?.success || dbResult?.success;

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-green-500/20 rounded-xl mb-4">
          <span className="text-3xl">📊</span>
        </div>
        <h2 className="text-2xl font-bold text-white">Connection Verification</h2>
        <p className="text-gray-400 mt-2">Testing API, WebSocket, and database connectivity</p>
      </div>

      {/* Connection cards */}
      <div className="max-w-lg mx-auto space-y-3">
        <ResultCard
          title="REST API"
          result={apiResult}
          details="Testing /api/health endpoint"
        />
        <ResultCard
          title="WebSocket"
          result={wsResult}
          details="Testing WebSocket connection"
        />
        <ResultCard
          title="Database Services"
          result={dbResult}
          details="Checking Postgres, Redis, Qdrant"
        />
      </div>

      {/* Re-test button */}
      <div className="max-w-lg mx-auto">
        <button
          onClick={runTests}
          disabled={isTesting}
          className="w-full px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
        >
          {isTesting ? (
            <>
              <LoadingSpinner size="sm" />
              Running tests...
            </>
          ) : (
            '↻ Re-run Tests'
          )}
        </button>
      </div>

      {/* Summary */}
      {hasRunTests && (
        <div className={`max-w-lg mx-auto p-4 rounded-lg border ${
          allPassed || corePassed ? 'bg-green-500/10 border-green-500/30' :
          anyPassed ? 'bg-yellow-500/10 border-yellow-500/30' :
          'bg-red-500/10 border-red-500/30'
        }`}>
          <div className="flex items-center gap-3">
            {allPassed ? (
              <>
                <span className="text-2xl">🎉</span>
                <div>
                  <div className="font-medium text-green-400">All connections verified</div>
                  <div className="text-sm text-gray-400">Ready to continue</div>
                </div>
              </>
            ) : corePassed ? (
              <>
                <span className="text-2xl">✅</span>
                <div>
                  <div className="font-medium text-green-400">Core connections verified</div>
                  <div className="text-sm text-gray-400">API and database ready — WebSocket is optional</div>
                </div>
              </>
            ) : anyPassed ? (
              <>
                <span className="text-2xl">⚠️</span>
                <div>
                  <div className="font-medium text-yellow-400">Partial connectivity</div>
                  <div className="text-sm text-gray-400">Some services may be unavailable</div>
                </div>
              </>
            ) : (
              <>
                <span className="text-2xl">❌</span>
                <div>
                  <div className="font-medium text-red-400">Connection failed</div>
                  <div className="text-sm text-gray-400">Check your API endpoint and key</div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <WizardNav
        onBack={onBack}
        onNext={onNext}
        nextLabel="Continue"
        nextDisabled={!anyPassed}
      />
    </div>
  );
}

/**
 * Agent Health Check step
 */
function AgentHealthStep({
  apiHost,
  apiKey,
  onNext,
  onBack,
}: {
  apiHost: string;
  apiKey: string;
  onNext: () => void;
  onBack: () => void;
}) {
  const [agents, setAgents] = useState<AgentHealthResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const results = await checkAgentHealth(apiHost, apiKey);
      setAgents(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to check agent health');
      setAgents([]);
    }

    setIsLoading(false);
  }, [apiHost, apiKey]);

  // Auto-check on mount
  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  const onlineCount = agents.filter(a => a.status === 'online').length;
  const totalCount = agents.length;

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-cyan-500/20 rounded-xl mb-4">
          <span className="text-3xl">🤖</span>
        </div>
        <h2 className="text-2xl font-bold text-white">Agent Health Check</h2>
        <p className="text-gray-400 mt-2">Verifying swarm agent status</p>
      </div>

      {/* Status summary */}
      <div className="max-w-lg mx-auto">
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-400">Agent Status</div>
              <div className="text-2xl font-bold text-white">
                {isLoading ? (
                  <span className="text-gray-400">Checking...</span>
                ) : (
                  <>
                    <span className={onlineCount > 0 ? 'text-green-400' : 'text-gray-400'}>
                      {onlineCount}
                    </span>
                    <span className="text-gray-500"> / {totalCount}</span>
                  </>
                )}
              </div>
            </div>
            <div className="text-right">
              <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
                isLoading ? 'bg-blue-500/20 text-blue-400' :
                onlineCount > 0 ? 'bg-green-500/20 text-green-400' :
                'bg-gray-500/20 text-gray-400'
              }`}>
                {isLoading ? (
                  <LoadingSpinner size="sm" />
                ) : onlineCount > 0 ? (
                  '● Online'
                ) : (
                  '○ No Agents'
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Agent list */}
      <div className="max-w-lg mx-auto space-y-2">
        {isLoading ? (
          <div className="text-center py-8 text-gray-400">
            <LoadingSpinner size="md" />
            <p className="mt-4">Checking agent health...</p>
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <p className="text-red-400">{error}</p>
            <button
              onClick={checkHealth}
              className="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg"
            >
              Try Again
            </button>
          </div>
        ) : agents.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <p>No agent instances found</p>
            <p className="text-sm mt-2">Deploy agents to see them here</p>
          </div>
        ) : (
          agents.map((agent) => (
            <AgentHealthCard key={agent.agentId} agent={agent} />
          ))
        )}
      </div>

      {/* Re-check button */}
      <div className="max-w-lg mx-auto">
        <button
          onClick={checkHealth}
          disabled={isLoading}
          className="w-full px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <LoadingSpinner size="sm" />
              Checking...
            </>
          ) : (
            '↻ Refresh Status'
          )}
        </button>
      </div>

      <WizardNav
        onBack={onBack}
        onNext={onNext}
        nextLabel="Complete Setup"
        nextDisabled={isLoading}
      />
    </div>
  );
}

/**
 * Success/Complete step
 */
function CompleteStep({ onFinish }: { onFinish: () => void }) {
  const [countdown, setCountdown] = useState(5);

  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    } else {
      onFinish();
    }
  }, [countdown, onFinish]);

  return (
    <div className="text-center space-y-8 py-8">
      {/* Success animation */}
      <div className="relative mx-auto w-32 h-32">
        <div className="absolute inset-0 bg-gradient-to-br from-green-400 to-emerald-600 rounded-full blur-xl opacity-30 animate-pulse" />
        <div className="relative w-full h-full bg-gradient-to-br from-green-400 to-emerald-600 rounded-full flex items-center justify-center animate-bounce">
          <span className="text-5xl">✓</span>
        </div>
      </div>

      {/* Title */}
      <div>
        <h1 className="text-3xl font-bold text-white">
          Setup Complete!
        </h1>
        <p className="text-gray-400 mt-2">Your Heretek Swarm is ready to use</p>
      </div>

      {/* Summary */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 max-w-md mx-auto">
        <h3 className="font-medium text-white mb-4">Configuration Summary</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">API Connected</span>
            <span className="text-green-400">✓</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">WebSocket Active</span>
            <span className="text-green-400">✓</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Credentials Saved</span>
            <span className="text-green-400">✓</span>
          </div>
        </div>
      </div>

      {/* Redirect message */}
      <p className="text-gray-400">
        Redirecting to dashboard in <span className="text-blue-400 font-mono">{countdown}</span> seconds...
      </p>

      {/* Manual continue button */}
      <button
        onClick={onFinish}
        className="px-8 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold transition-colors"
      >
        Go to Dashboard Now
      </button>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

const STEPS: WizardStep[] = ['welcome', 'api-endpoint', 'api-key', 'database-test', 'agent-health', 'complete'];

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const {
    currentStep,
    config,
    isConfigured,
    isRerunning,
    nextStep,
    prevStep,
    setConfig,
    completeSetup,
    resetSetup,
    setRerunning,
  } = useSetupStore();

  const toast = useToast();

  // Check if already configured on mount
  useEffect(() => {
    const configured = localStorage.getItem('swarm_configured') === 'true';
    if (configured && !isRerunning) {
      onComplete();
    }
  }, [isConfigured, isRerunning, onComplete]);

  const currentStepIndex = STEPS.indexOf(currentStep);

  const handleComplete = useCallback(() => {
    completeSetup();
    toast.success('Setup Complete', 'Heretek Swarm is now configured!');
    onComplete();
  }, [completeSetup, toast, onComplete]);

  const handleFinish = useCallback(() => {
    onComplete();
  }, [onComplete]);

  const renderStep = () => {
    switch (currentStep) {
      case 'welcome':
        return <WelcomeStep onStart={nextStep} />;

      case 'api-endpoint':
        return (
          <ApiEndpointStep
            apiHost={config.apiHost}
            onChange={(host) => setConfig({ apiHost: host, wsHost: deriveWsUrl(host) })}
            onNext={nextStep}
            onBack={prevStep}
          />
        );

      case 'api-key':
        return (
          <ApiKeyStep
            apiKey={config.apiKey}
            apiHost={config.apiHost}
            onChange={(key) => setConfig({ apiKey: key })}
            onNext={nextStep}
            onBack={prevStep}
          />
        );

      case 'database-test':
        return (
          <DatabaseTestStep
            apiHost={config.apiHost}
            apiKey={config.apiKey}
            onNext={nextStep}
            onBack={prevStep}
          />
        );

      case 'agent-health':
        return (
          <AgentHealthStep
            apiHost={config.apiHost}
            apiKey={config.apiKey}
            onNext={handleComplete}
            onBack={prevStep}
          />
        );

      case 'complete':
        return <CompleteStep onFinish={handleFinish} />;

      default:
        return <WelcomeStep onStart={nextStep} />;
    }
  };

  const showProgress = currentStep !== 'welcome' && currentStep !== 'complete';

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <span className="text-lg">🧠</span>
            </div>
            <span className="font-semibold">Heretek Swarm</span>
          </div>

          {showProgress && (
            <StepProgress
              currentStep={currentStep}
              totalSteps={STEPS.length}
              currentStepIndex={currentStepIndex}
            />
          )}

          {/* Reset button */}
          <button
            onClick={() => {
              resetSetup();
              setRerunning(true);
            }}
            className="text-xs text-gray-500 hover:text-gray-300"
          >
            Reset
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-2xl">
          {renderStep()}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-4">
        <div className="max-w-4xl mx-auto px-6 text-center text-xs text-gray-600">
          Heretek Swarm Dashboard • First-run Setup Wizard
        </div>
      </footer>
    </div>
  );
}

export default SetupWizard;
