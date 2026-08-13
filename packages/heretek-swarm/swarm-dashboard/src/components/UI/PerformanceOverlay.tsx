/**
 * PerformanceOverlay Component
 *
 * Real-time performance monitoring overlay showing:
 * - FPS counter
 * - Component render times
 * - Memory usage (if available)
 * - Network request count and total time
 *
 * Only visible when Developer Mode is enabled.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useDeveloperMode } from '../Settings/DeveloperModeToggle';

export interface PerformanceOverlayProps {
  className?: string;
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
}

interface PerformanceMetrics {
  fps: number;
  frameTime: number;
  memoryUsed?: number;
  memoryTotal?: number;
  networkRequests: number;
  networkTotalTime: number;
  componentRenders: number;
  lastRenderTime?: number;
}

const POSITION_CLASSES: Record<string, string> = {
  'top-left': 'top-4 left-4',
  'top-right': 'top-4 right-4',
  'bottom-left': 'bottom-24 left-4',
  'bottom-right': 'bottom-24 right-4',
};

export function PerformanceOverlay({
  className = '',
  position = 'top-left'
}: PerformanceOverlayProps) {
  const isDeveloperMode = useDeveloperMode();
  const [isVisible, setIsVisible] = useState(true);
  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    fps: 0,
    frameTime: 0,
    networkRequests: 0,
    networkTotalTime: 0,
    componentRenders: 0,
  });
  const [isExpanded, setIsExpanded] = useState(false);

  const frameCountRef = useRef(0);
  const lastFpsUpdateRef = useRef(performance.now());
  const frameTimesRef = useRef<number[]>([]);
  const rafIdRef = useRef<number | undefined>(undefined);
  const componentRendersRef = useRef(0);

  // Track network requests
  useEffect(() => {
    const networkStats = { requests: 0, totalTime: 0 };

    const handleApiRequest = (event: CustomEvent) => {
      const detail = event.detail;
      if (detail.method) {
        networkStats.requests++;
        if (detail.duration) {
          networkStats.totalTime += detail.duration;
        }
        setMetrics(prev => ({
          ...prev,
          networkRequests: networkStats.requests,
          networkTotalTime: networkStats.totalTime,
        }));
      }
    };

    window.addEventListener('api-request', handleApiRequest as EventListener);
    return () => window.removeEventListener('api-request', handleApiRequest as EventListener);
  }, []);

  // Track component renders
  useEffect(() => {
    const handleRender = () => {
      componentRendersRef.current++;
      setMetrics(prev => ({
        ...prev,
        componentRenders: componentRendersRef.current,
      }));
    };

    window.addEventListener('component-render', handleRender as EventListener);
    return () => window.removeEventListener('component-render', handleRender as EventListener);
  }, []);

  // FPS and memory monitoring
  useEffect(() => {
    if (!isDeveloperMode || !isVisible) {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
      return;
    }

    const measureFrame = () => {
      const now = performance.now();
      frameCountRef.current++;

      // Calculate frame time
      const frameTimes = frameTimesRef.current;
      if (frameTimes.length > 0) {
        const lastFrameTime = now - (frameTimes[frameTimes.length - 1] || now);
        frameTimes.push(lastFrameTime);
        // Keep last 60 frame times
        if (frameTimes.length > 60) {
          frameTimes.shift();
        }
      } else {
        frameTimes.push(0);
      }
      frameTimesRef.current = frameTimes;

      // Update FPS every 500ms
      if (now - lastFpsUpdateRef.current >= 500) {
        const avgFrameTime = frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length;
        const fps = Math.round(1000 / avgFrameTime) || 0;

        // Get memory usage if available
        let memoryUsed: number | undefined;
        let memoryTotal: number | undefined;

        if ('performance' in window && 'memory' in performance) {
          const memory = (performance as unknown as { memory?: { usedJSHeapSize: number; totalJSHeapSize: number } }).memory;
          if (memory) {
            memoryUsed = Math.round(memory.usedJSHeapSize / 1024 / 1024);
            memoryTotal = Math.round(memory.totalJSHeapSize / 1024 / 1024);
          }
        }

        setMetrics(prev => ({
          ...prev,
          fps,
          frameTime: Math.round(avgFrameTime * 10) / 10,
          memoryUsed,
          memoryTotal,
        }));

        frameCountRef.current = 0;
        lastFpsUpdateRef.current = now;
      }

      rafIdRef.current = requestAnimationFrame(measureFrame);
    };

    rafIdRef.current = requestAnimationFrame(measureFrame);
    return () => {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [isDeveloperMode, isVisible]);

  const formatDuration = (ms: number): string => {
    if (ms < 1) return `${Math.round(ms * 1000)}μs`;
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getFpsColor = (fps: number): string => {
    if (fps >= 55) return 'text-green-400';
    if (fps >= 30) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getFpsBg = (fps: number): string => {
    if (fps >= 55) return 'bg-green-500';
    if (fps >= 30) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  if (!isDeveloperMode || !isVisible) return null;

  return (
    <div className={`fixed z-50 ${POSITION_CLASSES[position]} ${className}`}>
      {/* Main Toggle Button */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsVisible(false)}
          className="p-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded-lg transition-colors"
          aria-label="Hide performance overlay"
        >
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* FPS Display */}
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-900/90 backdrop-blur-sm border border-gray-700 rounded-lg">
          <div className={`w-3 h-3 rounded-full ${getFpsBg(metrics.fps)} animate-pulse`} />
          <span className={`text-lg font-bold font-mono ${getFpsColor(metrics.fps)}`}>
            {metrics.fps}
          </span>
          <span className="text-xs text-gray-500">FPS</span>
        </div>

        {/* Expand Button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={`p-2 border border-gray-600 rounded-lg transition-colors ${
            isExpanded ? 'bg-purple-600 hover:bg-purple-700' : 'bg-gray-800 hover:bg-gray-700'
          }`}
          aria-label="Toggle detailed metrics"
        >
          <svg
            className={`w-4 h-4 text-white transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Expanded Metrics */}
      {isExpanded && (
        <div className="mt-2 p-4 bg-gray-900/95 backdrop-blur-sm border border-gray-700 rounded-xl min-w-[280px]">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-white font-semibold text-sm">Performance Metrics</h4>
            <span className="text-xs text-gray-500">Real-time</span>
          </div>

          <div className="space-y-3">
            {/* Frame Time */}
            <div className="flex items-center justify-between">
              <span className="text-gray-400 text-sm">Frame Time</span>
              <span className={`font-mono text-sm ${metrics.frameTime <= 16.67 ? 'text-green-400' : metrics.frameTime <= 33.33 ? 'text-yellow-400' : 'text-red-400'}`}>
                {metrics.frameTime}ms
              </span>
            </div>

            {/* Memory Usage */}
            {metrics.memoryUsed && metrics.memoryTotal && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-gray-400 text-sm">Memory</span>
                  <span className="font-mono text-sm text-purple-400">
                    {metrics.memoryUsed}MB / {metrics.memoryTotal}MB
                  </span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 transition-all duration-300"
                    style={{ width: `${Math.min((metrics.memoryUsed / metrics.memoryTotal) * 100, 100)}%` }}
                  />
                </div>
              </div>
            )}

            {/* Network */}
            <div className="flex items-center justify-between">
              <span className="text-gray-400 text-sm">Network</span>
              <div className="text-right">
                <span className="font-mono text-sm text-blue-400">{metrics.networkRequests}</span>
                <span className="text-gray-500 text-xs ml-1">reqs</span>
                <span className="text-gray-600 text-xs mx-1">|</span>
                <span className="font-mono text-sm text-gray-400">{formatDuration(metrics.networkTotalTime)}</span>
              </div>
            </div>

            {/* Component Renders */}
            <div className="flex items-center justify-between">
              <span className="text-gray-400 text-sm">Renders</span>
              <span className="font-mono text-sm text-orange-400">{metrics.componentRenders}</span>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="mt-4 pt-3 border-t border-gray-800">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="text-center p-2 bg-gray-800 rounded">
                <div className="text-gray-500">Target FPS</div>
                <div className="text-green-400 font-mono">60</div>
              </div>
              <div className="text-center p-2 bg-gray-800 rounded">
                <div className="text-gray-500">Frame Budget</div>
                <div className="text-blue-400 font-mono">16.67ms</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * usePerformanceMonitor Hook
 *
 * Hook to track component render performance.
 * Call this in functional components to track their render count.
 */
export function usePerformanceMonitor(componentName: string) {
  const isDeveloperMode = useDeveloperMode();

  useEffect(() => {
    if (!isDeveloperMode) return;

    // Dispatch render event
    window.dispatchEvent(new CustomEvent('component-render', {
      detail: { componentName, timestamp: performance.now() }
    }));
  }, [componentName, isDeveloperMode]);

  // Track render duration
  const renderStartRef = useRef(performance.now());

  useEffect(() => {
    const renderTime = performance.now() - renderStartRef.current;

    window.dispatchEvent(new CustomEvent('component-render-time', {
      detail: { componentName, renderTime }
    }));
  });
}

export default PerformanceOverlay;
