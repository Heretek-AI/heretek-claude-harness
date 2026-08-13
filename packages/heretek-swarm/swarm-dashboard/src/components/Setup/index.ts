/**
 * Setup Components
 *
 * Exports for the setup wizard system including:
 * - Main SetupWizard component
 * - Setup store for state management
 * - Validation utilities
 */

export { SetupWizard } from './SetupWizard';

// Re-export types and utilities for external use
export {
  useSetupStore,
  useCurrentStep,
  useIsConfigured,
  useConfig,
  useApiConnection,
  useWsConnection,
  useAgentHealth,
  useIsCheckingAgents,
  useValidationErrors,
  useIsValidating,
} from '../../stores/setupStore';

export type {
  WizardStep,
  ConnectionTestResult,
  AgentHealthResult,
  SetupConfig,
  SetupState,
} from '../../stores/setupStore';

export {
  testApiHealth,
  testWebSocket,
  testApiKey,
  testDatabaseConnection,
  checkAgentHealth,
  validateApiHost,
  validateApiKey,
  normalizeUrl,
  deriveWsUrl,
  isValidUrl,
} from '../../utils/setupValidation';

export type {
  ValidationResult,
} from '../../utils/setupValidation';
