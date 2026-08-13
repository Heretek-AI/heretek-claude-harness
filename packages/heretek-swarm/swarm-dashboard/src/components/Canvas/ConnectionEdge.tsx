/**
 * ConnectionEdge - Custom Edge for Message Flow Visualization
 *
 * Displays animated edges between agents with color coding based on message type.
 * Uses XYFlow v12 BaseEdge for custom edge rendering.
 */

import React, { memo } from 'react';
import {
  BaseEdge,
  EdgeProps,
  getBezierPath,
  EdgeLabelRenderer,
} from '@xyflow/react';

export type MessageType = 'task' | 'consensus' | 'alert' | 'default';

export interface ConnectionEdgeData extends Record<string, unknown> {
  messageType?: MessageType;
  messageCount?: number;
  label?: string;
  animated?: boolean;
}

interface ConnectionEdgeProps extends EdgeProps {
  data?: ConnectionEdgeData;
}

const messageColors: Record<MessageType, string> = {
  task: '#3B82F6',      // Blue
  consensus: '#22C55E', // Green
  alert: '#EF4444',     // Red
  default: '#6B7280',   // Gray
};

const messageLabels: Record<MessageType, string> = {
  task: 'Task',
  consensus: 'Consensus',
  alert: 'Alert',
  default: 'Message',
};

function ConnectionEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  data,
  markerEnd,
}: ConnectionEdgeProps) {
  const messageType = data?.messageType || 'default';
  const color = messageColors[messageType];
  const messageCount = data?.messageCount || 0;
  const customLabel = data?.label;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          strokeWidth: 3,
          stroke: color,
          ...style,
        }}
      />

      {/* Animated dash for message flow */}
      <BaseEdge
        path={edgePath}
        style={{
          strokeWidth: 3,
          stroke: color,
          strokeDasharray: '5, 5',
          animation: 'dashAnimation 1s linear infinite',
          opacity: 0.5,
        }}
      />

      <EdgeLabelRenderer>
        <div
          className="nodrag nopan absolute transform -translate-x-1/2 -translate-y-1/2 pointer-events-none"
          style={{
            left: labelX,
            top: labelY,
            backgroundColor: 'rgba(31, 41, 55, 0.9)',
            borderRadius: '4px',
            padding: '4px 8px',
            fontSize: '11px',
            fontWeight: '600',
            color: color,
            border: `1px solid ${color}`,
            whiteSpace: 'nowrap',
          }}
        >
          {customLabel || (messageCount > 0 ? `${messageLabels[messageType]} (${messageCount})` : messageLabels[messageType])}
        </div>
      </EdgeLabelRenderer>

      <style>{`
        @keyframes dashAnimation {
          to {
            stroke-dashoffset: -10;
          }
        }
      `}</style>
    </>
  );
}

export default memo(ConnectionEdge);
