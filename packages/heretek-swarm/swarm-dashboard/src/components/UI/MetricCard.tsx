/**
 * MetricCard Component
 *
 * Displays a single metric with optional sparkline visualization.
 * Used throughout the dashboard for showing statistics and KPIs.
 */

import React from 'react';

export interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: React.ReactNode;
  sparklineData?: number[];
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'gray';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  tooltip?: string;
}

const colorClasses = {
  blue: { text: 'text-blue-400', bg: 'bg-blue-500', gradient: 'from-blue-500/20' },
  green: { text: 'text-green-400', bg: 'bg-green-500', gradient: 'from-green-500/20' },
  yellow: { text: 'text-yellow-400', bg: 'bg-yellow-500', gradient: 'from-yellow-500/20' },
  red: { text: 'text-red-400', bg: 'bg-red-500', gradient: 'from-red-500/20' },
  purple: { text: 'text-purple-400', bg: 'bg-purple-500', gradient: 'from-purple-500/20' },
  gray: { text: 'text-gray-400', bg: 'bg-gray-500', gradient: 'from-gray-500/20' },
};

const sizeClasses = {
  sm: { padding: 'p-3', title: 'text-xs', value: 'text-xl', change: 'text-xs' },
  md: { padding: 'p-4', title: 'text-sm', value: 'text-2xl', change: 'text-sm' },
  lg: { padding: 'p-6', title: 'text-base', value: 'text-3xl', change: 'text-base' },
};

/**
 * Simple Sparkline SVG component
 */
function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length < 2) return null;

  const width = 100;
  const height = 40;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(' ');

  const areaPoints = `0,${height} ${points} ${width},${height}`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-10">
      <defs>
        <linearGradient id={`gradient-${color}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" className={`${colorClasses[color as keyof typeof colorClasses].text}`} stopOpacity="0.3" />
          <stop offset="100%" className={`${colorClasses[color as keyof typeof colorClasses].text}`} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={areaPoints}
        fill={`url(#gradient-${color})`}
      />
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        className={colorClasses[color as keyof typeof colorClasses].text}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function MetricCard({
  title,
  value,
  change,
  changeLabel,
  icon,
  sparklineData,
  color = 'blue',
  size = 'md',
  className = '',
  tooltip,
}: MetricCardProps) {
  const sizes = sizeClasses[size];
  const colors = colorClasses[color];

  const formattedValue = typeof value === 'number'
    ? value.toLocaleString()
    : value;

  const formattedChange = change !== undefined && (
    <span className={`${sizes.change} ${change >= 0 ? 'text-green-400' : 'text-red-400'} font-medium`}>
      {change >= 0 ? '↑' : '↓'} {Math.abs(change).toFixed(1)}%
    </span>
  );

  return (
    <div
      className={`bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl ${sizes.padding} ${className} hover:border-gray-600/50 transition-all duration-200 group`}
      title={tooltip}
    >
      <div className="flex items-start justify-between mb-2">
        <span className={`${sizes.title} text-gray-400 font-medium`}>{title}</span>
        {icon && (
          <span className={`${colors.text} opacity-70 group-hover:opacity-100 transition-opacity`}>
            {icon}
          </span>
        )}
      </div>

      <div className={`${sizes.value} font-bold text-white mb-2`}>
        {formattedValue}
      </div>

      {change !== undefined && (
        <div className="flex items-center gap-2">
          {formattedChange}
          {changeLabel && (
            <span className={`${sizes.change} text-gray-500`}>{changeLabel}</span>
          )}
        </div>
      )}

      {sparklineData && sparklineData.length > 0 && (
        <div className="mt-3">
          <Sparkline data={sparklineData} color={color} />
        </div>
      )}
    </div>
  );
}

/**
 * MetricCardGrid - Container for multiple metric cards
 */
export interface MetricCardGridProps {
  children: React.ReactNode;
  columns?: 2 | 3 | 4 | 5;
  className?: string;
}

export function MetricCardGrid({ children, columns = 4, className = '' }: MetricCardGridProps) {
  const gridClasses = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
    5: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-5',
  };

  return (
    <div className={`grid ${gridClasses[columns]} gap-4 ${className}`}>
      {children}
    </div>
  );
}

export default MetricCard;
