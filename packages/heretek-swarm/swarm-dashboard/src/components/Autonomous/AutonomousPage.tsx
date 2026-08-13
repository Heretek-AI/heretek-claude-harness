/**
 * AutonomousPage Component
 *
 * Main page with tab-based navigation for four sub-views:
 * - Analysis History: analysis records from Metis/Empath
 * - Active Tasks: Chronos task snapshots
 * - Goal Pipeline: goal lifecycle states
 * - Events Timeline: chronological event timeline
 */

import React, { useState, useCallback } from 'react';
import { ErrorBoundary, SimpleErrorFallback } from '../UI/ErrorBoundary';
import { AnalysisHistory } from './AnalysisHistory';
import { ActiveTasks } from './ActiveTasks';
import { GoalPipeline } from './GoalPipeline';
import { EventsTimeline } from './EventsTimeline';

// ── Tab definitions ──────────────────────────────────────────────────────────

interface TabDefinition {
  id: string;
  label: string;
  icon: string;
  description: string;
}

const TABS: TabDefinition[] = [
  {
    id: 'analysis',
    label: 'Analysis History',
    icon: '📊',
    description: 'Metis analysis records with Empath responses',
  },
  {
    id: 'tasks',
    label: 'Active Tasks',
    icon: '📋',
    description: 'Chronos task snapshots and status',
  },
  {
    id: 'goals',
    label: 'Goal Pipeline',
    icon: '🎯',
    description: 'Goal lifecycle: proposed → voting → accepted/rejected',
  },
  {
    id: 'events',
    label: 'Events Timeline',
    icon: '📅',
    description: 'Chronological event feed from the autonomous loop',
  },
];

// ── Tab content router ───────────────────────────────────────────────────────

function TabContent({ tabId }: { tabId: string }) {
  switch (tabId) {
    case 'analysis':
      return <AnalysisHistory />;
    case 'tasks':
      return <ActiveTasks />;
    case 'goals':
      return <GoalPipeline />;
    case 'events':
      return <EventsTimeline />;
    default:
      return (
        <div className="text-center py-16 text-gray-400">
          <p>Unknown tab: {tabId}</p>
        </div>
      );
  }
}

// ── Component ────────────────────────────────────────────────────────────────

interface AutonomousPageProps {
  className?: string;
}

export function AutonomousPage({ className = '' }: AutonomousPageProps) {
  const [activeTab, setActiveTab] = useState('analysis');
  const [tabErrors, setTabErrors] = useState<Record<string, Error | null>>({});

  const handleTabError = useCallback((tabId: string) => (error: Error) => {
    setTabErrors((prev) => ({ ...prev, [tabId]: error }));
  }, []);

  const handleRetryTab = useCallback((tabId: string) => {
    setTabErrors((prev) => ({ ...prev, [tabId]: null }));
  }, []);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Autonomous Runtime</h1>
          <p className="text-gray-400 text-sm mt-1">
            Monitor autonomous analysis, tasks, goals, and events
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-700">
        <nav className="flex gap-1" role="tablist" aria-label="Autonomous section tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`tabpanel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-t-lg transition-colors border-b-2 ${
                activeTab === tab.id
                  ? 'text-blue-400 border-blue-500 bg-gray-800/30'
                  : 'text-gray-400 border-transparent hover:text-gray-300 hover:bg-gray-800/20'
              }`}
            >
              <span className="text-base">{tab.icon}</span>
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div
        role="tabpanel"
        id={`tabpanel-${activeTab}`}
        aria-labelledby={`tab-${activeTab}`}
        className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6"
      >
        {/* Tab description */}
        <p className="text-xs text-gray-500 mb-4">
          {TABS.find((t) => t.id === activeTab)?.description}
        </p>

        {tabErrors[activeTab] ? (
          <div className="space-y-4">
            <SimpleErrorFallback
              error={tabErrors[activeTab]!}
              onRetry={() => handleRetryTab(activeTab)}
            />
          </div>
        ) : (
          <ErrorBoundary
            onError={handleTabError(activeTab)}
            fallback={
              <div className="text-center py-12">
                <p className="text-red-400 text-sm mb-2">This tab encountered an error.</p>
                <button
                  onClick={() => handleRetryTab(activeTab)}
                  className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm transition-colors"
                >
                  Retry
                </button>
              </div>
            }
          >
            <TabContent tabId={activeTab} />
          </ErrorBoundary>
        )}
      </div>
    </div>
  );
}

export default AutonomousPage;
