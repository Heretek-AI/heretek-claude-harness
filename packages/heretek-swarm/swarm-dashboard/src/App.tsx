/**
 * Heretek Swarm Dashboard - Main Application
 *
 * Central control panel for deploying, monitoring, and configuring
 * the Heretek Swarm application.
 *
 * Health check pattern (M005/S01): `checkSystemHealth()` reads the top-level
 * `data.status === 'healthy'` as primary signal. Service-level status lives
 * under `data.services.*.status` and is only consulted for 'degraded' detection.
 * This handles `--no-infra` mode where infra services report 'unhealthy' but
 * the top-level status is still 'healthy'.
 */

import { useState, useEffect, useCallback } from 'react';
import { MemoryRouter, Routes, Route, useNavigate, useLocation, Outlet } from 'react-router-dom';
import { HomePage as NewHomePage } from './pages/home-page';
import { DeliberationListPage as NewDeliberationListPage } from './pages/deliberation-list-page';
import { DeliberationPage as NewDeliberationPage } from './pages/deliberation-page';

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
import { DashboardLayout, NavItem } from './components/Dashboard/Layout';
import { AgentsPage } from './components/Agents/AgentsPage';
import { ConsciousnessPage } from './components/Consciousness/ConsciousnessPage';
import { AutonomousPage } from './components/Autonomous/AutonomousPage';
import { ObservabilityPage } from './components/Observability/ObservabilityPage';
import { MessageList } from './components/Chat/MessageList';
import { EnhancedCanvas } from './components/Canvas/EnhancedCanvas';
import { SettingsPage } from './components/Settings/SettingsPage';
import { LogsPage } from './components/Logs/LogsPage';
import { ToastProvider, useToast } from './components/UI/Toast';
import { ErrorBoundary } from './components/UI/ErrorBoundary';
import { DebugPanel } from './components/UI/DebugPanel';
import { PerformanceOverlay } from './components/UI/PerformanceOverlay';
import { SetupWizard } from './components/Setup';
import { useSetupStore } from './stores/setupStore';
import { setToastInstance } from './api/client';

import { WorkflowBuilder } from './components/WorkflowBuilder/WorkflowBuilder';
import { CommandPalette, CommandItem } from './components/UI/CommandPalette';

const navItems: NavItem[] = [
  { id: 'home', label: 'Home', icon: '🏠' },
  { id: 'agents', label: 'Agents', icon: '🤖' },
  { id: 'deliberations', label: 'Deliberations', icon: '💬' },
  { id: 'consciousness', label: 'Consciousness', icon: '🧠' },
  { id: 'autonomous', label: 'Autonomous', icon: '🔄' },
  { id: 'observability', label: 'Observability', icon: '🔍' },
  { id: 'memory', label: 'Memory', icon: '🧠' },
  { id: 'chat', label: 'Chat', icon: '💬' },
  { id: 'canvas', label: 'Canvas', icon: '🎨' },
  { id: 'workflows', label: 'Workflows', icon: '🔀' },
  { id: 'logs', label: 'Terminal/Logs', icon: '📟' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
];

function DashboardLayoutWrapper({
  systemStatus,
  onRerunSetup,
}: {
  systemStatus: 'healthy' | 'degraded' | 'offline';
  onRerunSetup: () => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();

  // Map pathname to nav ID
  const pathToNav: Record<string, string> = {
    '/': 'home',
    '/agents': 'agents',
    '/consciousness': 'consciousness',
    '/deliberations': 'deliberations',
    '/autonomous': 'autonomous',
    '/observability': 'observability',
    '/chat': 'chat',
    '/canvas': 'canvas',
    '/workflows': 'workflows',
    '/logs': 'logs',
    '/settings': 'settings',
  };

  const activeNav =
    pathToNav[location.pathname] ||
    (location.pathname.startsWith('/deliberations') ? 'deliberations' : 'home');

  const handleNavClick = useCallback(
    (navId: string) => {
      const path = Object.entries(pathToNav).find(([, id]) => id === navId)?.[0] || '/';
      navigate(path);
    },
    [navigate],
  );

  return (
    <DashboardLayout
      activeNav={activeNav}
      onNavClick={handleNavClick}
      navItems={navItems}
      systemStatus={systemStatus}
    >
      <ErrorBoundary>
        <Outlet />
      </ErrorBoundary>
    </DashboardLayout>
  );
}

function DashboardContent() {
  const [systemStatus, setSystemStatus] = useState<'healthy' | 'degraded' | 'offline'>('healthy');
  const toast = useToast();

  // Setup store integration
  const { config, setRerunning, resetSetup } = useSetupStore();

  const [showSetup, setShowSetup] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  // Check if setup is needed on mount
  useEffect(() => {
    const checkConfiguration = () => {
      const storedConfigured = localStorage.getItem('swarm_configured') === 'true';
      const storedApiHost = localStorage.getItem('swarm_api_host');

      const envApiKey = import.meta.env.VITE_API_KEY;
      const envApiHost = import.meta.env.VITE_API_HOST;

      if (!storedConfigured || !storedApiHost) {
        if (envApiKey && envApiHost) {
          localStorage.setItem('swarm_api_host', envApiHost);
          localStorage.setItem('swarm_configured', 'true');
          useSetupStore.getState().setConfig({
            apiHost: envApiHost,
            apiKey: envApiKey,
            wsHost: '',
          });
          setShowSetup(false);
        } else {
          setShowSetup(true);
        }
      } else {
        if (!config.apiHost) {
          useSetupStore.getState().setConfig({
            apiHost: storedApiHost,
            apiKey: '',
            wsHost: localStorage.getItem('swarm_ws_host') || '',
          });
        }
        setShowSetup(false);
      }
      setIsInitialized(true);
    };

    checkConfiguration();
  }, []);

  // Set toast instance for API client
  useEffect(() => {
    setToastInstance({
      error: (title, message) => toast.error(title, message),
    });
  }, [toast]);

  // Check system health periodically
  const checkSystemHealth = useCallback(async () => {
    try {
      const apiHost = _safeUrl(
        localStorage.getItem('swarm_api_host') || import.meta.env.VITE_API_HOST || '',
      );
      if (!apiHost) {
        setSystemStatus('offline');
        return;
      }

      const response = await fetch(`${apiHost}/api/health`);
      if (!response.ok) {
        setSystemStatus('offline');
        return;
      }
      const data = await response.json();

      if (data.status === 'healthy') {
        setSystemStatus('healthy');
        return;
      }

      const svc = data.services || {};
      const anyServiceHealthy =
        svc.gateway?.status === 'healthy' ||
        svc.redis?.status === 'healthy' ||
        svc.postgres?.status === 'healthy' ||
        svc.qdrant?.status === 'healthy';

      setSystemStatus(anyServiceHealthy ? 'degraded' : 'offline');
    } catch {
      setSystemStatus('offline');
    }
  }, []);

  useEffect(() => {
    if (!showSetup && isInitialized) {
      checkSystemHealth();
      const interval = setInterval(checkSystemHealth, 30000);
      return () => clearInterval(interval);
    }
  }, [checkSystemHealth, showSetup, isInitialized]);

  const handleSetupComplete = useCallback(() => {
    setShowSetup(false);
    setTimeout(checkSystemHealth, 1000);
  }, [checkSystemHealth]);

  const handleRerunSetup = useCallback(() => {
    resetSetup();
    setRerunning(true);
    setShowSetup(true);
  }, [resetSetup, setRerunning]);

  // Don't render until we've checked configuration
  if (!isInitialized) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      {showSetup ? (
        <SetupWizard onComplete={handleSetupComplete} />
      ) : (
        <Routes>
          <Route
            element={
              <DashboardLayoutWrapper systemStatus={systemStatus} onRerunSetup={handleRerunSetup} />
            }
          >
            {/* Tier-1 routes */}
            <Route path="/" element={<NewHomePage />} />
            <Route path="/deliberations" element={<NewDeliberationListPage />} />
            <Route path="/deliberations/:id" element={<NewDeliberationPage />} />

            {/* Legacy routes */}
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/consciousness" element={<ConsciousnessPage />} />
            <Route path="/autonomous" element={<AutonomousPage />} />
            <Route path="/observability" element={<ObservabilityPage />} />
            <Route path="/chat" element={<MessageList />} />
            <Route path="/canvas" element={<EnhancedCanvas />} />
            <Route path="/workflows" element={<WorkflowBuilder />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/settings" element={<SettingsPage onRerunSetup={handleRerunSetup} />} />
          </Route>
        </Routes>
      )}
      <CommandPalette
        items={navItems.map<CommandItem>((item) => ({
          id: `nav:${item.id}`,
          label: item.label,
          group: 'Page',
          icon: item.icon,
          keywords: ['navigate', 'go to', item.id],
        }))}
      />
    </>
  );
}

function App() {
  return (
    <ToastProvider>
      <MemoryRouter>
        <DashboardContent />
      </MemoryRouter>
      {/* Debug features - only visible when Developer Mode is enabled */}
      <DebugPanel />
      <PerformanceOverlay position="top-right" />
    </ToastProvider>
  );
}

export default App;
