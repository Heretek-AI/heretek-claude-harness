/**
 * CanvasToolbar - Canvas Controls Toolbar
 *
 * Provides canvas controls including zoom, fit, save/load workflow, execute, and clear.
 */

import React from 'react';

export interface CanvasToolbarProps {
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFitView?: () => void;
  onSaveWorkflow?: () => void;
  onLoadWorkflow?: () => void;
  onExecuteWorkflow?: () => void;
  onClearCanvas?: () => void;
  onToggleGrid?: () => void;
  gridEnabled?: boolean;
  isExecuting?: boolean;
  disabled?: boolean;
}

export function CanvasToolbar({
  onZoomIn,
  onZoomOut,
  onFitView,
  onSaveWorkflow,
  onLoadWorkflow,
  onExecuteWorkflow,
  onClearCanvas,
  onToggleGrid,
  gridEnabled = true,
  isExecuting = false,
  disabled = false,
}: CanvasToolbarProps) {
  return (
    <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
      <div className="flex items-center gap-2 bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-2">
        {/* Zoom Controls */}
        <div className="flex items-center gap-1 pr-2 border-r border-gray-700">
          <button
            onClick={onZoomOut}
            disabled={disabled}
            className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Zoom Out"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          </button>

          <button
            onClick={onZoomIn}
            disabled={disabled}
            className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Zoom In"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>

          <button
            onClick={onFitView}
            disabled={disabled}
            className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Fit View"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
        </div>

        {/* Grid Toggle */}
        <div className="flex items-center gap-1 pr-2 border-r border-gray-700">
          <button
            onClick={onToggleGrid}
            disabled={disabled}
            className={`p-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              gridEnabled ? 'bg-blue-600 text-white' : 'hover:bg-gray-700 text-gray-400 hover:text-white'
            }`}
            title="Toggle Grid"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
          </button>
        </div>

        {/* Workflow Controls */}
        <div className="flex items-center gap-1 pr-2 border-r border-gray-700">
          <button
            onClick={onSaveWorkflow}
            disabled={disabled}
            className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Save Workflow"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
          </button>

          <button
            onClick={onLoadWorkflow}
            disabled={disabled}
            className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Load Workflow"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          </button>
        </div>

        {/* Execute & Clear */}
        <div className="flex items-center gap-1">
          <button
            onClick={onExecuteWorkflow}
            disabled={disabled || isExecuting}
            className={`
              px-4 py-2 rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed
              ${isExecuting
                ? 'bg-yellow-600 text-white animate-pulse'
                : 'bg-green-600 hover:bg-green-700 text-white'}
            `}
            title="Execute Workflow"
          >
            {isExecuting ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Running...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
                Execute
              </span>
            )}
          </button>

          <button
            onClick={onClearCanvas}
            disabled={disabled}
            className="p-2 hover:bg-red-900 rounded-lg text-gray-400 hover:text-red-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Clear Canvas"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default CanvasToolbar;
