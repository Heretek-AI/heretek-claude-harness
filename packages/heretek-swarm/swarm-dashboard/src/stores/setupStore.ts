/**
 * Setup Store - Zustand store for wizard state management
 *
 * Manages setup wizard state including:
 * - Current step tracking
 * - Configuration values (API endpoint, API key)
 * - Validation status
 * - Connection test results
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// =============================================================================
// Types
// =============================================================================

export type WizardStep =
  | 'welcome'
  | 'api-endpoint'
  | 'api-key'
  | 'database-test'
  | 'agent-health'
  | 'complete';

export interface ConnectionTestResult {
  success: boolean;
  latency?: number;
  error?: string;
  details?: string;
}

export interface AgentHealthResult {
  agentId: string;
  agentType: string;
  status: 'online' | 'offline' | 'degraded' | 'unknown';
  messageCount?: number;
  lastActivity?: string;
  error?: string;
}

export interface SetupConfig {
  apiHost: string;
  apiKey: string;
  wsHost: string;
}

export interface SetupState {
  // Current wizard state
  currentStep: WizardStep;
  isConfigured: boolean;
  isRerunning: boolean;

  // Configuration
  config: SetupConfig;

  // Validation state
  isValidating: boolean;
  validationErrors: Record<string, string>;

  // Connection test results
  apiConnection: ConnectionTestResult | null;
  wsConnection: ConnectionTestResult | null;

  // Agent health results
  agentHealth: AgentHealthResult[];
  isCheckingAgents: boolean;

  // Provider info from backend
  llmProviders: LLMProviderInfo[];
  embeddingProviders: EmbeddingProviderInfo[];

  // Actions
  setStep: (step: WizardStep) => void;
  nextStep: () => void;
  prevStep: () => void;
  setConfig: (config: Partial<SetupConfig>) => void;
  setApiConnection: (result: ConnectionTestResult) => void;
  setWsConnection: (result: ConnectionTestResult) => void;
  setAgentHealth: (results: AgentHealthResult[]) => void;
  setIsCheckingAgents: (checking: boolean) => void;
  setIsValidating: (validating: boolean) => void;
  setValidationError: (field: string, error: string) => void;
  clearValidationError: (field: string) => void;
  clearValidationErrors: () => void;
  completeSetup: () => void;
  resetSetup: () => void;
  setRerunning: (rerunning: boolean) => void;
  setProviders: (llm: LLMProviderInfo[], embedding: EmbeddingProviderInfo[]) => void;
}

// Provider info types
export interface LLMProviderInfo {
  provider_name: string;
  provider_type: string;
  base_url: string;
  default_model: string;
  is_default: boolean;
  is_enabled: boolean;
}

export interface EmbeddingProviderInfo {
  provider_name: string;
  provider_type: string;
  base_url: string;
  default_model: string;
  is_default: boolean;
  is_enabled: boolean;
}

// Step order for navigation
const STEP_ORDER: WizardStep[] = [
  'welcome',
  'api-endpoint',
  'api-key',
  'database-test',
  'agent-health',
  'complete',
];

// =============================================================================
// Store Implementation
// =============================================================================

export const useSetupStore = create<SetupState>()(
  persist(
    (set, get) => ({
      // Initial state
      currentStep: 'welcome',
      isConfigured: false,
      isRerunning: false,

      config: {
        apiHost: '',
        apiKey: '',
        wsHost: '',
      },

      isValidating: false,
      validationErrors: {},

      apiConnection: null,
      wsConnection: null,

      agentHealth: [],
      isCheckingAgents: false,

      llmProviders: [],
      embeddingProviders: [],

      // Actions
      setStep: (step: WizardStep) => {
        set({ currentStep: step });
      },

      nextStep: () => {
        const { currentStep } = get();
        const currentIndex = STEP_ORDER.indexOf(currentStep);
        if (currentIndex < STEP_ORDER.length - 1) {
          set({ currentStep: STEP_ORDER[currentIndex + 1] });
        }
      },

      prevStep: () => {
        const { currentStep } = get();
        const currentIndex = STEP_ORDER.indexOf(currentStep);
        if (currentIndex > 0) {
          set({ currentStep: STEP_ORDER[currentIndex - 1] });
        }
      },

      setConfig: (configUpdate: Partial<SetupConfig>) => {
        set((state) => ({
          config: { ...state.config, ...configUpdate },
        }));
      },

      setApiConnection: (result: ConnectionTestResult) => {
        set({ apiConnection: result });
      },

      setWsConnection: (result: ConnectionTestResult) => {
        set({ wsConnection: result });
      },

      setAgentHealth: (results: AgentHealthResult[]) => {
        set({ agentHealth: results });
      },

      setIsCheckingAgents: (checking: boolean) => {
        set({ isCheckingAgents: checking });
      },

      setIsValidating: (validating: boolean) => {
        set({ isValidating: validating });
      },

      setValidationError: (field: string, error: string) => {
        set((state) => ({
          validationErrors: { ...state.validationErrors, [field]: error },
        }));
      },

      clearValidationError: (field: string) => {
        set((state) => {
          const { [field]: _, ...rest } = state.validationErrors;
          return { validationErrors: rest };
        });
      },

      clearValidationErrors: () => {
        set({ validationErrors: {} });
      },

      completeSetup: () => {
        const { config } = get();

        // Persist setup values. The API key must live under 'api_key' because
        // the API client interceptor and every data-fetching hook read it from
        // there to attach the Bearer token; without it the whole dashboard 401s.
        localStorage.setItem('swarm_api_host', config.apiHost);
        localStorage.setItem('swarm_ws_host', config.wsHost);
        localStorage.setItem('swarm_configured', 'true');
        if (config.apiKey) {
          localStorage.setItem('api_key', config.apiKey);
        }

        set({
          isConfigured: true,
          currentStep: 'complete',
        });
      },

      resetSetup: () => {
        // Clear all setup-related localStorage
        localStorage.removeItem('swarm_api_host');
        localStorage.removeItem('swarm_ws_host');
        localStorage.removeItem('api_key');
        localStorage.removeItem('swarm_configured');

        set({
          currentStep: 'welcome',
          isConfigured: false,
          isRerunning: true,
          config: {
            apiHost: '',
            apiKey: '',
            wsHost: '',
          },
          isValidating: false,
          validationErrors: {},
          apiConnection: null,
          wsConnection: null,
          agentHealth: [],
          isCheckingAgents: false,
        });
      },

      setRerunning: (rerunning: boolean) => {
        set({ isRerunning: rerunning });
      },

      setProviders: (llm: LLMProviderInfo[], embedding: EmbeddingProviderInfo[]) => {
        set({ llmProviders: llm, embeddingProviders: embedding });
      },
    }),
    {
      name: 'heretek-setup-storage',
      partialize: (state) => ({
        isConfigured: state.isConfigured,
        config: {
          ...state.config,
          apiKey: '',
        },
        isRerunning: state.isRerunning,
      }),
    }
  )
);

// =============================================================================
// Selector Hooks
// =============================================================================

export const useCurrentStep = () => useSetupStore((state) => state.currentStep);
export const useIsConfigured = () => useSetupStore((state) => state.isConfigured);
export const useConfig = () => useSetupStore((state) => state.config);
export const useApiConnection = () => useSetupStore((state) => state.apiConnection);
export const useWsConnection = () => useSetupStore((state) => state.wsConnection);
export const useAgentHealth = () => useSetupStore((state) => state.agentHealth);
export const useIsCheckingAgents = () => useSetupStore((state) => state.isCheckingAgents);
export const useValidationErrors = () => useSetupStore((state) => state.validationErrors);
export const useIsValidating = () => useSetupStore((state) => state.isValidating);
