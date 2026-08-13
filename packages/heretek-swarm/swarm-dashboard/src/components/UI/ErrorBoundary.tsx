/**
 * ErrorBoundary Component
 *
 * React error boundary for catching and displaying errors gracefully.
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  className?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className={`min-h-screen bg-gray-900 flex items-center justify-center p-4 ${this.props.className}`}>
          <div className="max-w-md w-full bg-gray-800 border border-red-500/50 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                <span className="text-red-400 text-xl">!</span>
              </div>
              <h2 className="text-xl font-bold text-white">Something went wrong</h2>
            </div>

            <p className="text-gray-400 mb-4">
              An unexpected error occurred. Please try refreshing the page.
            </p>

            {this.state.error && (
              <details className="mb-4">
                <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-400">
                  Error details
                </summary>
                <pre className="mt-2 p-3 bg-gray-900 rounded-lg text-xs text-red-400 overflow-auto max-h-48">
                  {this.state.error.message}
                </pre>
              </details>
            )}

            <button
              onClick={this.handleReset}
              className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * SimpleErrorFallback - A simpler error display for inline use
 */
export interface SimpleErrorFallbackProps {
  error: Error;
  onRetry?: () => void;
  className?: string;
}

export function SimpleErrorFallback({ error, onRetry, className = '' }: SimpleErrorFallbackProps) {
  return (
    <div className={`bg-red-900/20 border border-red-500/50 rounded-lg p-4 ${className}`}>
      <div className="flex items-start gap-3">
        <span className="text-red-400 text-lg">⚠️</span>
        <div className="flex-1">
          <h4 className="text-red-400 font-semibold text-sm">Error</h4>
          <p className="text-gray-400 text-sm mt-1">{error.message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 text-sm text-red-400 hover:text-red-300 underline"
            >
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ErrorBoundary;
