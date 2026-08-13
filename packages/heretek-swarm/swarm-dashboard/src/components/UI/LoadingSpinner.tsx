/**
 * LoadingSpinner Component
 *
 * Displays a loading animation with optional message.
 */

import React from 'react';

export interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  message?: string;
  fullScreen?: boolean;
  className?: string;
}

const sizeClasses = {
  sm: 'h-4 w-4',
  md: 'h-8 w-8',
  lg: 'h-12 w-12',
};

export function LoadingSpinner({
  size = 'md',
  message,
  fullScreen = false,
  className = '',
}: LoadingSpinnerProps) {
  const spinner = (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <div
        className={`${sizeClasses[size]} animate-spin rounded-full border-2 border-gray-600 border-t-blue-500`}
      />
      {message && (
        <p className="mt-4 text-sm text-gray-400 animate-pulse">{message}</p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 bg-gray-900/80 backdrop-blur-sm flex items-center justify-center z-50">
        {spinner}
      </div>
    );
  }

  return spinner;
}

/**
 * LoadingOverlay - Full page loading overlay
 */
export function LoadingOverlay({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="fixed inset-0 bg-gray-900/90 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="text-center">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-gray-700 border-t-blue-500 mx-auto" />
        <p className="mt-4 text-lg text-gray-300">{message}</p>
      </div>
    </div>
  );
}

/**
 * Skeleton - Placeholder for loading content
 */
export interface SkeletonProps {
  width?: string;
  height?: string;
  className?: string;
  rounded?: boolean;
}

export function Skeleton({ width = '100%', height = '1rem', className = '', rounded = false }: SkeletonProps) {
  return (
    <div
      className={`bg-gray-700 animate-pulse ${rounded ? 'rounded' : ''} ${className}`}
      style={{ width, height }}
    />
  );
}

/**
 * SkeletonText - Multiple skeleton lines for text content
 */
export interface SkeletonTextProps {
  lines?: number;
  className?: string;
}

export function SkeletonText({ lines = 3, className = '' }: SkeletonTextProps) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          height="0.875rem"
          className={i === lines - 1 ? 'w-3/4' : undefined}
          rounded
        />
      ))}
    </div>
  );
}

export default LoadingSpinner;
