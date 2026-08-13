/**
 * StatusBadge Component
 *
 * Displays status indicators with consistent styling across the application.
 * Supports multiple status types with appropriate colors and icons.
 */

import React from 'react';

export type StatusType =
  | 'healthy'
  | 'active'
  | 'success'
  | 'warning'
  | 'error'
  | 'inactive'
  | 'pending'
  | 'starting'
  | 'dormant'
  | 'emerging'
  | 'coherent'
  | 'transcendent';

export interface StatusBadgeProps {
  status: StatusType | string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

const statusConfig: Record<StatusType, { color: string; bgColor: string; icon: string }> = {
  healthy: { color: 'text-green-400', bgColor: 'bg-green-500', icon: '●' },
  active: { color: 'text-green-400', bgColor: 'bg-green-500', icon: '●' },
  success: { color: 'text-green-400', bgColor: 'bg-green-500', icon: '✓' },
  warning: { color: 'text-yellow-400', bgColor: 'bg-yellow-500', icon: '⚠' },
  error: { color: 'text-red-400', bgColor: 'bg-red-500', icon: '✕' },
  inactive: { color: 'text-gray-400', bgColor: 'bg-gray-500', icon: '○' },
  pending: { color: 'text-blue-400', bgColor: 'bg-blue-500', icon: '◌' },
  starting: { color: 'text-yellow-400', bgColor: 'bg-yellow-500', icon: '⟳' },
  dormant: { color: 'text-gray-400', bgColor: 'bg-gray-500', icon: '○' },
  emerging: { color: 'text-yellow-400', bgColor: 'bg-yellow-500', icon: '◐' },
  coherent: { color: 'text-blue-400', bgColor: 'bg-blue-500', icon: '●' },
  transcendent: { color: 'text-purple-400', bgColor: 'bg-purple-500', icon: '◎' },
};

const sizeClasses = {
  sm: { indicator: 'w-2 h-2', text: 'text-xs', gap: 'gap-1.5' },
  md: { indicator: 'w-2.5 h-2.5', text: 'text-sm', gap: 'gap-2' },
  lg: { indicator: 'w-3 h-3', text: 'text-base', gap: 'gap-2.5' },
};

export function StatusBadge({
  status,
  size = 'md',
  showLabel = true,
  className = ''
}: StatusBadgeProps) {
  const config = statusConfig[status.toLowerCase() as StatusType] || {
    color: 'text-gray-400',
    bgColor: 'bg-gray-500',
    icon: '○',
  };

  const sizes = sizeClasses[size];

  return (
    <span
      className={`inline-flex items-center ${sizes.gap} ${className}`}
      role="status"
    >
      <span
        className={`${sizes.indicator} ${config.bgColor} rounded-full animate-pulse`}
        aria-hidden="true"
      />
      {showLabel && (
        <span className={`${sizes.text} ${config.color} font-medium capitalize`}>
          {status}
        </span>
      )}
    </span>
  );
}

/**
 * StatusIndicator - A simpler version without label
 */
export function StatusIndicator({
  status,
  size = 'md',
  className = ''
}: Omit<StatusBadgeProps, 'showLabel'>) {
  const config = statusConfig[status.toLowerCase() as StatusType] || {
    color: 'text-gray-400',
    bgColor: 'bg-gray-500',
  };

  const sizes = {
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
    lg: 'w-3 h-3',
  };

  return (
    <span
      className={`${sizes[size]} ${config.bgColor} rounded-full ${className}`}
      aria-label={`Status: ${status}`}
      title={status}
    />
  );
}

export default StatusBadge;
