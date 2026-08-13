/**
 * DynamicHandles - Render dynamic handles for AgentNode
 *
 * Renders input/output handles based on channel subscriptions.
 * Each handle is color-coded by channel type and shows a tooltip on hover.
 *
 * Features:
 * - Dynamic handle rendering based on channel subscriptions
 * - Color-coded handles by channel type (event, command, response, metric)
 * - Tooltip showing channel name and type on hover
 * - Support for multiple handles on each side
 * - Proper handle positioning based on count
 */

import React, { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { AgentHandle, ChannelType } from '../../hooks/useAgentHandles';
import { getHandleColor } from '../../hooks/useAgentHandles';

/**
 * Handle tooltip component
 */
interface HandleTooltipProps {
  channelName: string;
  channelType: ChannelType;
  dataType?: string;
  description?: string;
}

function HandleTooltip({ channelName, channelType, dataType, description }: HandleTooltipProps) {
  return (
    <div className="handle-tooltip">
      <div className="handle-tooltip-header">
        <span className="handle-tooltip-channel">{channelName}</span>
        <span
          className="handle-tooltip-type"
          style={{ backgroundColor: getHandleColor(channelType) }}
        >
          {channelType}
        </span>
      </div>
      {dataType && <div className="handle-tooltip-datatype">Type: {dataType}</div>}
      {description && <div className="handle-tooltip-description">{description}</div>}
    </div>
  );
}

/**
 * Dynamic handle props
 */
interface DynamicHandleProps {
  handle: AgentHandle;
  index: number;
  total: number;
  isSelected?: boolean;
  onClick?: (handleId: string) => void;
}

/**
 * Single dynamic handle component
 */
function DynamicHandleComponent({
  handle,
  index,
  total,
  isSelected = false,
  onClick,
}: DynamicHandleProps) {
  const color = getHandleColor(handle.channelType);
  const isInput = handle.type === 'target';

  // Calculate position offset for multiple handles
  const getPositionStyle = () => {
    if (total === 1) {
      return isInput
        ? { left: '50%', transform: 'translateX(-50%)' }
        : { left: '50%', transform: 'translateX(-50%)' };
    }

    // Distribute handles horizontally
    const offset = total === 1 ? 50 : (index / (total - 1)) * 100;
    return {
      left: `${offset}%`,
      transform: 'translateX(-50%)',
    };
  };

  const positionStyle = getPositionStyle();

  return (
    <div
      className="dynamic-handle-wrapper"
      style={{
        position: 'absolute',
        top: isInput ? '-10px' : 'auto',
        bottom: isInput ? 'auto' : '-10px',
        ...positionStyle,
        zIndex: 10,
      }}
    >
      <div className="handle-container" style={{ position: 'relative' }}>
        <Handle
          id={handle.id}
          type={handle.type}
          position={isInput ? Position.Top : Position.Bottom}
          className={`dynamic-handle ${isSelected ? 'selected' : ''}`}
          style={{
            backgroundColor: color,
            border: `2px solid ${color}`,
            width: '12px',
            height: '12px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onClick={(e) => {
            e.stopPropagation();
            onClick?.(handle.id);
          }}
        />

        {/* Tooltip - shown on hover */}
        <div className="handle-tooltip-container">
          <HandleTooltip
            channelName={handle.channelName}
            channelType={handle.channelType}
            dataType={handle.dataType}
            description={handle.description}
          />
        </div>
      </div>
    </div>
  );
}

/**
 * DynamicHandles group component
 */
interface DynamicHandlesGroupProps {
  handles: AgentHandle[];
  selectedHandleId?: string;
  onHandleClick?: (handleId: string) => void;
  className?: string;
}

/**
 * Main DynamicHandles component that renders all handles
 */
function DynamicHandles({ handles, selectedHandleId, onHandleClick }: DynamicHandlesGroupProps) {
  // Separate input and output handles
  const { inputHandles, outputHandles } = useMemo(() => {
    return {
      inputHandles: handles.filter((h) => h.type === 'target'),
      outputHandles: handles.filter((h) => h.type === 'source'),
    };
  }, [handles]);

  if (handles.length === 0) {
    // Render default handles when no subscriptions
    return (
      <>
        <Handle
          type="target"
          position={Position.Top}
          className="!bg-gray-600 !border-2 !border-gray-500"
        />
        <Handle
          type="source"
          position={Position.Bottom}
          className="!bg-gray-600 !border-2 !border-gray-500"
        />
      </>
    );
  }

  return (
    <>
      {/* Input handles */}
      {inputHandles.map((handle, index) => (
        <DynamicHandleComponent
          key={handle.id}
          handle={handle}
          index={index}
          total={inputHandles.length}
          isSelected={selectedHandleId === handle.id}
          onClick={onHandleClick}
        />
      ))}

      {/* Output handles */}
      {outputHandles.map((handle, index) => (
        <DynamicHandleComponent
          key={handle.id}
          handle={handle}
          index={index}
          total={outputHandles.length}
          isSelected={selectedHandleId === handle.id}
          onClick={onHandleClick}
        />
      ))}

      {/* CSS for tooltips */}
      <style>{`
        .handle-tooltip-container {
          position: absolute;
          top: -50px;
          left: 50%;
          transform: translateX(-50%);
          opacity: 0;
          visibility: hidden;
          transition: all 0.2s ease;
          pointer-events: none;
          z-index: 1000;
        }

        .handle-container:hover .handle-tooltip-container {
          opacity: 1;
          visibility: visible;
          top: -60px;
        }

        .handle-tooltip {
          background: rgba(17, 24, 39, 0.95);
          border: 1px solid rgba(75, 85, 99, 0.5);
          border-radius: 8px;
          padding: 10px 12px;
          min-width: 180px;
          max-width: 280px;
          box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
          backdrop-filter: blur(8px);
        }

        .handle-tooltip-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 8px;
          margin-bottom: 6px;
        }

        .handle-tooltip-channel {
          color: #F3F4F6;
          font-weight: 600;
          font-size: 13px;
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .handle-tooltip-type {
          color: #FFFFFF;
          font-size: 10px;
          font-weight: 700;
          padding: 2px 6px;
          border-radius: 4px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .handle-tooltip-datatype {
          color: #9CA3AF;
          font-size: 11px;
          margin-bottom: 4px;
        }

        .handle-tooltip-description {
          color: #6B7280;
          font-size: 11px;
          line-height: 1.4;
        }

        .dynamic-handle {
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .dynamic-handle:hover {
          transform: scale(1.3);
          box-shadow: 0 0 12px currentColor;
        }

        .dynamic-handle.selected {
          transform: scale(1.4);
          box-shadow: 0 0 16px currentColor, 0 0 24px currentColor;
          animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
          0%, 100% {
            box-shadow: 0 0 16px currentColor, 0 0 24px currentColor;
          }
          50% {
            box-shadow: 0 0 24px currentColor, 0 0 32px currentColor;
          }
        }
      `}</style>
    </>
  );
}

export default memo(DynamicHandles);
export { DynamicHandles, DynamicHandleComponent, HandleTooltip };
export type { DynamicHandlesGroupProps, DynamicHandleProps, HandleTooltipProps };
