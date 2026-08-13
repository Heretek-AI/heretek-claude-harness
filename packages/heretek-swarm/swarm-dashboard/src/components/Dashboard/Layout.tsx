/**
 * Dashboard Layout
 *
 * Main layout component with sidebar navigation, header, and content area.
 * Provides a consistent structure across all dashboard views.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { StatusIndicator } from '../UI/StatusBadge';

export interface NavItem {
  id: string;
  label: string;
  icon: string;
  path?: string;
  badge?: number;
}

export interface DashboardLayoutProps {
  children: React.ReactNode;
  activeNav: string;
  onNavClick: (navId: string) => void;
  navItems?: NavItem[];
  systemStatus?: 'healthy' | 'degraded' | 'offline';
  userName?: string;
  showHeader?: boolean;
  showFooter?: boolean;
}

const defaultNavItems: NavItem[] = [
  { id: 'home', label: 'Home', icon: '🏠' },
  { id: 'agents', label: 'Agents', icon: '🤖' },
  { id: 'consciousness', label: 'Consciousness', icon: '🧠' },
  { id: 'workflows', label: 'Workflows', icon: '🔀' },
  { id: 'logs', label: 'Terminal/Logs', icon: '📟' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
];

const systemStatusConfig = {
  healthy: { color: 'bg-green-500', label: 'System Healthy' },
  degraded: { color: 'bg-yellow-500', label: 'System Degraded' },
  offline: { color: 'bg-red-500', label: 'System Offline' },
};

export function DashboardLayout({
  children,
  activeNav,
  onNavClick,
  navItems = defaultNavItems,
  systemStatus = 'healthy',
  userName = 'User',
  showHeader = true,
  showFooter = true,
}: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  // Tier 6.1: on viewports < 768px wide, default the sidebar to
  // collapsed (icon-only) and let the toggle button open it as a
  // slide-over. This makes the dashboard usable on phones and
  // tablets without a separate mobile layout.
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(max-width: 767px)');
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Auto-collapse on small viewports; let the user re-open.
  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [isMobile]);

  const statusConfig = systemStatusConfig[systemStatus];

  return (
    <div className="min-h-screen bg-gray-900 text-white flex">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-64' : 'w-16'
        } bg-gray-800 border-r border-gray-700 transition-all duration-300 flex flex-col fixed h-full z-40`}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤖</span>
            {sidebarOpen && (
              <span className="font-bold text-lg truncate">Heretek Swarm</span>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 overflow-y-auto">
          <ul className="space-y-1 px-2">
            {navItems.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => onNavClick(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                    activeNav === item.id
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                  } ${!sidebarOpen ? 'justify-center' : ''}`}
                  title={!sidebarOpen ? item.label : undefined}
                >
                  <span className="text-xl">{item.icon}</span>
                  {sidebarOpen && (
                    <>
                      <span className="flex-1 text-left font-medium">{item.label}</span>
                      {item.badge !== undefined && item.badge > 0 && (
                        <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Sidebar Toggle */}
        <div className="p-4 border-t border-gray-700">
          <button
            onClick={toggleSidebar}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white transition-colors"
          >
            <span className="text-lg">{sidebarOpen ? '←' : '→'}</span>
            {sidebarOpen && <span className="text-sm">Collapse</span>}
          </button>
        </div>

        {/* Footer */}
        {showFooter && sidebarOpen && (
          <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
            <div className="flex items-center justify-between">
              <span>Version 0.2.0</span>
              <a
                href="https://github.com/heretek/heretek-swarm"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-gray-400"
              >
                GitHub
              </a>
            </div>
          </div>
        )}
      </aside>

      {/* Main Content Area */}
      <div
        className={`flex-1 flex flex-col min-h-screen transition-all duration-300 ${
          sidebarOpen ? 'ml-64' : 'ml-16'
        }`}
      >
        {/* Header */}
        {showHeader && (
          <header className="h-16 bg-gray-800/50 backdrop-blur-sm border-b border-gray-700 sticky top-0 z-30">
            <div className="h-full flex items-center justify-between px-6">
              {/* Left side - Breadcrumb or title could go here */}
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <StatusIndicator status={systemStatus} size="md" />
                  <span className="text-sm text-gray-400">{statusConfig.label}</span>
                </div>
              </div>

              {/* Right side - User info and actions */}
              <div className="flex items-center gap-4">
                {/* API Key Status */}
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-gray-400">API:</span>
                  <span
                    className={`px-2 py-0.5 rounded ${
                      localStorage.getItem('api_key')
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-gray-700 text-gray-500'
                    }`}
                  >
                    {localStorage.getItem('api_key') ? 'Connected' : 'Not configured'}
                  </span>
                </div>

                {/* User Menu */}
                <div className="flex items-center gap-3 pl-4 border-l border-gray-700">
                  <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-medium">
                    {userName.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm text-gray-400">{userName}</span>
                </div>
              </div>
            </div>
          </header>
        )}

        {/* Page Content */}
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

export default DashboardLayout;
