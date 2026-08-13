/**
 * DeveloperModeToggle Component
 *
 * Toggle switch for enabling/disabling Developer Mode.
 * Persists preference in localStorage and triggers debug features.
 */

import React, { useState, useEffect, useCallback } from 'react';

export interface DeveloperModeToggleProps {
  onDeveloperModeChange?: (enabled: boolean) => void;
}

export function DeveloperModeToggle({ onDeveloperModeChange }: DeveloperModeToggleProps) {
  const [isDeveloperMode, setIsDeveloperMode] = useState<boolean>(() => {
    const stored = localStorage.getItem('developer_mode');
    return stored === 'true';
  });

  useEffect(() => {
    // Sync with storage changes from other tabs/windows
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'developer_mode') {
        setIsDeveloperMode(e.newValue === 'true');
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const toggleDeveloperMode = useCallback(() => {
    const newValue = !isDeveloperMode;
    setIsDeveloperMode(newValue);
    localStorage.setItem('developer_mode', String(newValue));

    // Dispatch custom event for other components to listen to
    window.dispatchEvent(new CustomEvent('developer-mode-change', {
      detail: { enabled: newValue }
    }));

    onDeveloperModeChange?.(newValue);
  }, [isDeveloperMode, onDeveloperModeChange]);

  return (
    <div className="flex items-center justify-between py-4 px-4 bg-gray-900/50 rounded-lg border border-gray-700">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-white font-medium">Developer Mode</span>
          <span className="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-full border border-purple-500/30">
            DEBUG
          </span>
        </div>
        <p className="text-gray-400 text-sm mt-1">
          Enable debug panel, detailed logging, and performance monitoring
        </p>
      </div>

      <button
        onClick={toggleDeveloperMode}
        className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-gray-800 ${
          isDeveloperMode ? 'bg-purple-600' : 'bg-gray-600'
        }`}
        aria-pressed={isDeveloperMode}
        aria-label="Toggle developer mode"
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white transition duration-200 ease-in-out ${
            isDeveloperMode ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

/**
 * useDeveloperMode Hook
 *
 * Custom hook to access developer mode state in any component.
 */
export function useDeveloperMode(): boolean {
  const [isDeveloperMode, setIsDeveloperMode] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('developer_mode');
      return stored === 'true';
    }
    return false;
  });

  useEffect(() => {
    const handleDeveloperModeChange = (e: CustomEvent) => {
      setIsDeveloperMode(e.detail.enabled);
    };

    window.addEventListener('developer-mode-change', handleDeveloperModeChange as EventListener);
    return () => window.removeEventListener('developer-mode-change', handleDeveloperModeChange as EventListener);
  }, []);

  return isDeveloperMode;
}

export default DeveloperModeToggle;
