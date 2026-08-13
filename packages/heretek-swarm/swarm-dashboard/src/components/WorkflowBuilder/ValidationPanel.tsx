/**
 * Validation Panel Component
 *
 * Displays workflow validation results with visual highlighting
 * and suggestions for fixing errors.
 *
 * Features:
 * - Error/warning/info categorization
 * - Click to highlight invalid nodes/edges
 * - Auto-scroll to problematic elements
 * - Suggestions for fixing issues
 */

import React, { useCallback, useMemo } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Validation error severity
 */
export type ValidationSeverity = 'error' | 'warning' | 'info';

/**
 * Validation error from API
 */
export interface ValidationError {
  severity: ValidationSeverity;
  code: string;
  message: string;
  node_id?: string;
  edge_id?: string;
  suggestion?: string;
}

/**
 * Validation result from API
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  info: ValidationError[];
}

/**
 * ValidationPanel props
 */
export interface ValidationPanelProps {
  /** Validation result */
  result: ValidationResult | null;
  /** Whether panel is visible */
  isOpen: boolean;
  /** Close handler */
  onClose: () => void;
  /** Click handler for node selection */
  onNodeSelect?: (nodeId: string) => void;
  /** Click handler for edge selection */
  onEdgeSelect?: (edgeId: string) => void;
}

// ============================================================================
// Icons
// ============================================================================

const SeverityIcon: React.FC<{ severity: ValidationSeverity }> = ({ severity }) => {
  switch (severity) {
    case 'error':
      return (
        <svg className="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
      );
    case 'warning':
      return (
        <svg className="w-5 h-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      );
    case 'info':
      return (
        <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
        </svg>
      );
  }
};

// ============================================================================
// Validation Item Component
// ============================================================================

interface ValidationItemProps {
  error: ValidationError;
  onNodeSelect?: (nodeId: string) => void;
  onEdgeSelect?: (edgeId: string) => void;
}

const ValidationItem: React.FC<ValidationItemProps> = ({
  error,
  onNodeSelect,
  onEdgeSelect,
}) => {
  const handleNodeClick = useCallback(() => {
    if (error.node_id && onNodeSelect) {
      onNodeSelect(error.node_id);
    }
  }, [error.node_id, onNodeSelect]);

  const handleEdgeClick = useCallback(() => {
    if (error.edge_id && onEdgeSelect) {
      onEdgeSelect(error.edge_id);
    }
  }, [error.edge_id, onEdgeSelect]);

  const severityColors = {
    error: 'bg-red-50 border-red-200',
    warning: 'bg-yellow-50 border-yellow-200',
    info: 'bg-blue-50 border-blue-200',
  };

  const textColors = {
    error: 'text-red-800',
    warning: 'text-yellow-800',
    info: 'text-blue-800',
  };

  return (
    <div
      className={`p-3 mb-2 rounded-lg border ${severityColors[error.severity]}`}
    >
      <div className="flex items-start gap-2">
        <SeverityIcon severity={error.severity} />
        <div className="flex-1">
          <div className={`font-semibold ${textColors[error.severity]}`}>
            {error.code}
          </div>
          <div className={`mt-1 ${textColors[error.severity]} text-sm`}>
            {error.message}
          </div>

          {/* Node/Edge reference */}
          {(error.node_id || error.edge_id) && (
            <div className="mt-2 flex gap-2">
              {error.node_id && (
                <button
                  onClick={handleNodeClick}
                  className="text-xs px-2 py-1 bg-white rounded border border-gray-300 hover:bg-gray-100 cursor-pointer"
                >
                  Node: {error.node_id}
                </button>
              )}
              {error.edge_id && (
                <button
                  onClick={handleEdgeClick}
                  className="text-xs px-2 py-1 bg-white rounded border border-gray-300 hover:bg-gray-100 cursor-pointer"
                >
                  Edge: {error.edge_id}
                </button>
              )}
            </div>
          )}

          {/* Suggestion */}
          {error.suggestion && (
            <div className={`mt-2 text-sm italic ${textColors[error.severity]} opacity-75`}>
              💡 {error.suggestion}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// Main ValidationPanel Component
// ============================================================================

/**
 * ValidationPanel displays workflow validation results
 */
export function ValidationPanel({
  result,
  isOpen,
  onClose,
  onNodeSelect,
  onEdgeSelect,
}: ValidationPanelProps) {
  // Group validation items by severity
  const allItems = useMemo(() => {
    if (!result) return { errors: [], warnings: [], info: [] };
    return {
      errors: result.errors || [],
      warnings: result.warnings || [],
      info: result.info || [],
    };
  }, [result]);

  const totalIssues = allItems.errors.length + allItems.warnings.length + allItems.info.length;

  if (!isOpen) return null;

  return (
    <div className="validation-panel fixed right-0 top-0 h-full w-96 bg-white shadow-2xl border-l border-gray-200 overflow-y-auto z-50">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            Validation Results
          </h2>
          {result && (
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-sm font-medium ${result.valid ? 'text-green-600' : 'text-red-600'}`}>
                {result.valid ? '✓ Valid' : '✗ Invalid'}
              </span>
              {totalIssues > 0 && (
                <span className="text-xs text-gray-500">
                  {totalIssues} issue{totalIssues !== 1 ? 's' : ''} found
                </span>
              )}
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          aria-label="Close validation panel"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {!result ? (
          <div className="text-center text-gray-500 py-8">
            <p>No validation results yet</p>
            <p className="text-sm mt-2">Run validation to check your workflow</p>
          </div>
        ) : result.valid && totalIssues === 0 ? (
          <div className="text-center text-green-600 py-8">
            <svg className="w-16 h-16 mx-auto mb-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <p className="text-lg font-semibold">Workflow is valid!</p>
            <p className="text-sm mt-2">No issues found</p>
          </div>
        ) : (
          <>
            {/* Errors */}
            {allItems.errors.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-red-800 mb-2 flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-red-100 rounded-full text-xs">
                    {allItems.errors.length}
                  </span>
                  Errors
                </h3>
                {allItems.errors.map((error, index) => (
                  <ValidationItem
                    key={`error-${index}`}
                    error={error}
                    onNodeSelect={onNodeSelect}
                    onEdgeSelect={onEdgeSelect}
                  />
                ))}
              </div>
            )}

            {/* Warnings */}
            {allItems.warnings.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-yellow-800 mb-2 flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-yellow-100 rounded-full text-xs">
                    {allItems.warnings.length}
                  </span>
                  Warnings
                </h3>
                {allItems.warnings.map((error, index) => (
                  <ValidationItem
                    key={`warning-${index}`}
                    error={error}
                    onNodeSelect={onNodeSelect}
                    onEdgeSelect={onEdgeSelect}
                  />
                ))}
              </div>
            )}

            {/* Info */}
            {allItems.info.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-blue-800 mb-2 flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-blue-100 rounded-full text-xs">
                    {allItems.info.length}
                  </span>
                  Information
                </h3>
                {allItems.info.map((error, index) => (
                  <ValidationItem
                    key={`info-${index}`}
                    error={error}
                    onNodeSelect={onNodeSelect}
                    onEdgeSelect={onEdgeSelect}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default ValidationPanel;
