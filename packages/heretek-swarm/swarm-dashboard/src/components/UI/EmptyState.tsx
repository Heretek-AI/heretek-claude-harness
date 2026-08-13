/**
 * EmptyState Component
 *
 * Displays when there's no data to show, with optional actions.
 */

import React from 'react';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
  sm: { padding: 'p-6', icon: 'text-3xl', title: 'text-lg', description: 'text-sm' },
  md: { padding: 'p-8', icon: 'text-4xl', title: 'text-xl', description: 'text-base' },
  lg: { padding: 'p-12', icon: 'text-6xl', title: 'text-2xl', description: 'text-lg' },
};

const defaultIcons: Record<string, React.ReactNode> = {
  default: '📭',
  search: '🔍',
  filter: '🗂️',
  agents: '🤖',
  messages: '💬',
  tasks: '📋',
  settings: '⚙️',
};

export function EmptyState({
  icon = defaultIcons.default,
  title,
  description,
  action,
  secondaryAction,
  className = '',
  size = 'md',
}: EmptyStateProps) {
  const sizes = sizeClasses[size];

  return (
    <div className={`text-center ${sizes.padding} ${className}`}>
      <div className={`${sizes.icon} mb-4`}>{icon}</div>

      <h3 className={`${sizes.title} font-semibold text-white`}>
        {title}
      </h3>

      {description && (
        <p className={`${sizes.description} text-gray-400 mt-2 max-w-md mx-auto`}>
          {description}
        </p>
      )}

      {action && (
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            onClick={action.onClick}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium inline-flex items-center gap-2"
          >
            {action.icon}
            {action.label}
          </button>
          {secondaryAction && (
            <button
              onClick={secondaryAction.onClick}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors font-medium"
            >
              {secondaryAction.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * NoResultsEmptyState - Specialized for search/filter no results
 */
export function NoResultsEmptyState({
  searchTerm,
  onClear,
  className = '',
}: {
  searchTerm?: string;
  onClear?: () => void;
  className?: string;
}) {
  return (
    <EmptyState
      icon="🔍"
      title={searchTerm ? `No results for "${searchTerm}"` : 'No results found'}
      description="Try adjusting your search or filter criteria"
      action={
        onClear
          ? { label: 'Clear filters', onClick: onClear }
          : undefined
      }
      size="sm"
      className={className}
    />
  );
}

export default EmptyState;
