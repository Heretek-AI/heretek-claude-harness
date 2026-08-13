/**
 * ConsciousnessGauge - Circular Gauge for GWT/IIT/AST/FEP Metrics
 *
 * Displays consciousness metrics as a circular/semi-circular gauge with
 * animated value transitions and tooltips.
 */

import React, { useState, useMemo } from 'react';

export type ConsciousnessTheory = 'GWT' | 'IIT' | 'AST' | 'FEP';

export interface ConsciousnessGaugeProps {
  gwtValue?: number;  // Global Workspace Theory (0-100)
  iitValue?: number;  // Integrated Information Theory (0-100)
  astValue?: number;  // Attention Schema Theory (0-100)
  fepValue?: number;  // Free Energy Principle (0-100)
  size?: number;
  showLabels?: boolean;
  animated?: boolean;
}

interface TheoryConfig {
  key: ConsciousnessTheory;
  label: string;
  description: string;
  color: string;
  bgColor: string;
}

const THEORY_CONFIG: TheoryConfig[] = [
  {
    key: 'GWT',
    label: 'GWT',
    description: 'Global Workspace Theory - Information integration across brain regions',
    color: '#3B82F6',    // Blue
    bgColor: 'bg-blue-500',
  },
  {
    key: 'IIT',
    label: 'IIT',
    description: 'Integrated Information Theory - Phi score measuring consciousness level',
    color: '#A855F7',    // Purple
    bgColor: 'bg-purple-500',
  },
  {
    key: 'AST',
    label: 'AST',
    description: 'Attention Schema Theory - Model of attention processes',
    color: '#22C55E',    // Green
    bgColor: 'bg-green-500',
  },
  {
    key: 'FEP',
    label: 'FEP',
    description: 'Free Energy Principle - Minimizing surprise and prediction error',
    color: '#F97316',    // Orange
    bgColor: 'bg-orange-500',
  },
];

export function ConsciousnessGauge({
  gwtValue = 0,
  iitValue = 0,
  astValue = 0,
  fepValue = 0,
  size = 280,
  showLabels = true,
  animated = true,
}: ConsciousnessGaugeProps) {
  const [hoveredTheory, setHoveredTheory] = useState<ConsciousnessTheory | null>(null);

  const values = useMemo(() => ({
    GWT: Math.max(0, Math.min(100, gwtValue)),
    IIT: Math.max(0, Math.min(100, iitValue)),
    AST: Math.max(0, Math.min(100, astValue)),
    FEP: Math.max(0, Math.min(100, fepValue)),
  }), [gwtValue, iitValue, astValue, fepValue]);

  const centerX = size / 2;
  const centerY = size / 2;
  const radius = size * 0.35;
  const strokeWidth = (size * 0.15) / 4;
  const gapAngle = 5; // degrees between segments

  // Calculate arc path for a segment
  const getArcPath = (startAngle: number, endAngle: number, innerRadius: number, outerRadius: number) => {
    const toRad = (deg: number) => (deg * Math.PI) / 180;
    const startOuter = {
      x: centerX + outerRadius * Math.sin(toRad(startAngle)),
      y: centerY - outerRadius * Math.cos(toRad(startAngle)),
    };
    const endOuter = {
      x: centerX + outerRadius * Math.sin(toRad(endAngle)),
      y: centerY - outerRadius * Math.cos(toRad(endAngle)),
    };
    const endInner = {
      x: centerX + innerRadius * Math.sin(toRad(endAngle)),
      y: centerY - innerRadius * Math.cos(toRad(endAngle)),
    };
    const startInner = {
      x: centerX + innerRadius * Math.sin(toRad(startAngle)),
      y: centerY - innerRadius * Math.cos(toRad(startAngle)),
    };

    const largeArc = endAngle - startAngle > 180 ? 1 : 0;

    return `
      M ${startOuter.x} ${startOuter.y}
      A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${endOuter.x} ${endOuter.y}
      L ${endInner.x} ${endInner.y}
      A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${startInner.x} ${startInner.y}
      Z
    `;
  };

  // Calculate segment angles (360 degrees / 4 segments = 90 each, minus gaps)
  const segmentAngle = (360 - (gapAngle * 3)) / 4;
  const startAngle = -180 + 90; // Start from top

  const segments = THEORY_CONFIG.map((theory, index) => {
    const value = values[theory.key];
    const fillAngle = startAngle + (index * (segmentAngle + gapAngle));
    const filledEndAngle = fillAngle + (segmentAngle * (value / 100));

    return {
      ...theory,
      value,
      fillAngle,
      filledEndAngle,
      segmentAngle,
    };
  });

  const totalValue = Object.values(values).reduce((a, b) => a + b, 0);
  const averageValue = totalValue / 4;

  return (
    <div className="relative inline-block">
      <svg width={size} height={size} className="transform">
        {/* Background circles */}
        <circle
          cx={centerX}
          cy={centerY}
          r={radius + strokeWidth * 2}
          fill="none"
          stroke="#1F2937"
          strokeWidth="2"
        />

        {/* Empty background segments */}
        {segments.map((segment, index) => {
          const segmentStart = segment.fillAngle;
          const segmentEnd = segment.fillAngle + segment.segmentAngle;
          return (
            <path
              key={`bg-${segment.key}`}
              d={getArcPath(segmentStart, segmentEnd, radius, radius + strokeWidth * 4)}
              fill="#374151"
              opacity="0.3"
            />
          );
        })}

        {/* Filled value segments */}
        {segments.map((segment) => {
          if (segment.value <= 0) return null;
          return (
            <path
              key={`fill-${segment.key}`}
              d={getArcPath(
                segment.fillAngle,
                segment.filledEndAngle,
                radius,
                radius + strokeWidth * 4
              )}
              fill={segment.color}
              className={animated ? 'transition-all duration-500 ease-out' : ''}
              onMouseEnter={() => setHoveredTheory(segment.key)}
              onMouseLeave={() => setHoveredTheory(null)}
              style={{ cursor: 'pointer' }}
            />
          );
        })}

        {/* Center value display */}
        <g>
          <text
            x={centerX}
            y={centerY - 10}
            textAnchor="middle"
            className="fill-white text-3xl font-bold"
            style={{ fontSize: `${size * 0.1}px` }}
          >
            {averageValue.toFixed(1)}
          </text>
          <text
            x={centerX}
            y={centerY + 15}
            textAnchor="middle"
            className="fill-gray-400 text-xs"
            style={{ fontSize: `${size * 0.04}px` }}
          >
            Average
          </text>
        </g>

        {/* Segment labels */}
        {showLabels && segments.map((segment, index) => {
          const labelAngle = segment.fillAngle + segment.segmentAngle / 2;
          const labelRadius = radius + strokeWidth * 4 + 20;
          const toRad = (deg: number) => (deg * Math.PI) / 180;
          const labelX = centerX + labelRadius * Math.sin(toRad(labelAngle));
          const labelY = centerY - labelRadius * Math.cos(toRad(labelAngle));

          return (
            <g key={`label-${segment.key}`}>
              <circle
                cx={labelX}
                cy={labelY}
                r="8"
                fill={segment.color}
              />
              <text
                x={labelX}
                y={labelY + 4}
                textAnchor="middle"
                className="fill-white text-xs font-bold"
                style={{ fontSize: `${size * 0.035}px` }}
              >
                {segment.label}
              </text>
              <text
                x={labelX}
                y={labelY + 14}
                textAnchor="middle"
                className="fill-gray-400"
                style={{ fontSize: `${size * 0.03}px` }}
              >
                {segment.value.toFixed(0)}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hoveredTheory && (
        <div
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 pointer-events-none z-10"
          style={{
            backgroundColor: 'rgba(31, 41, 55, 0.95)',
            borderRadius: '8px',
            padding: '12px',
            maxWidth: '200px',
            textAlign: 'center',
            border: `2px solid ${THEORY_CONFIG.find(t => t.key === hoveredTheory)?.color}`,
          }}
        >
          <div className="text-white font-bold mb-1">
            {THEORY_CONFIG.find(t => t.key === hoveredTheory)?.label}
          </div>
          <div className="text-gray-300 text-xs">
            {THEORY_CONFIG.find(t => t.key === hoveredTheory)?.description}
          </div>
          <div className="text-white font-semibold mt-2">
            Value: {values[hoveredTheory].toFixed(1)}
          </div>
        </div>
      )}
    </div>
  );
}

export default ConsciousnessGauge;
