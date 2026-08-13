/**
 * Node Group Component
 *
 * Renders a visual group container for workflow nodes.
 * Provides collapsible headers, color coding, and statistics display.
 *
 * Features:
 * - Visual container with colored border
 * - Collapsible header with group name
 * - Statistics display (agent count, load, Phi)
 * - Drag handles for moving group
 * - Delete button
 * - Edit name functionality
 *
 * Based on XYFlow grouping patterns.
 */

import React, { memo, useCallback, useState } from 'react';
import { NodeGroup, GroupFunction, GROUP_COLOR_SCHEMES, type GroupColorScheme } from '../../hooks/useNodeGrouping';

// ============================================================================
// Types
// ============================================================================

export interface NodeGroupComponentProps {
  /** Group data */
  group: NodeGroup;
  /** Whether group is selected */
  selected?: boolean;
  /** Click handler */
  onClick?: () => void;
  /** Delete handler */
  onDelete?: () => void;
  /** Name change handler */
  onNameChange?: (newName: string) => void;
  /** Collapse toggle handler */
  onToggleCollapse?: () => void;
  /** Color scheme override */
  colorScheme?: keyof typeof GROUP_COLOR_SCHEMES;
}

// ============================================================================
// Icons
// ============================================================================

const CollapseIcon: React.FC<{ collapsed: boolean }> = ({ collapsed }) => (
  <svg
    className={`w-4 h-4 transition-transform ${collapsed ? '-rotate-90' : ''}`}
    fill="currentColor"
    viewBox="0 0 20 20"
  >
    <path
      fillRule="evenodd"
      d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
      clipRule="evenodd"
    />
  </svg>
);

const DeleteIcon: React.FC = () => (
  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
    <path
      fillRule="evenodd"
      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
      clipRule="evenodd"
    />
  </svg>
);

const EditIcon: React.FC = () => (
  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
    <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
  </svg>
);

// ============================================================================
// Statistics Display
// ============================================================================

interface GroupStatisticsProps {
  statistics: NodeGroup['statistics'];
  collapsed: boolean;
}

const GroupStatistics: React.FC<GroupStatisticsProps> = ({
  statistics,
  collapsed,
}) => {
  if (collapsed) return null;

  return (
    <div className="flex items-center gap-4 text-xs text-gray-600">
      {statistics.agentCount > 0 && (
        <span className="flex items-center gap-1">
          <span>👥</span>
          <span>{statistics.agentCount} agent{statistics.agentCount !== 1 ? 's' : ''}</span>
        </span>
      )}
      {statistics.totalLoad > 0 && (
        <span className="flex items-center gap-1">
          <span>⚡</span>
          <span>{(statistics.totalLoad * 100).toFixed(0)}% load</span>
        </span>
      )}
      {statistics.averagePhi > 0 && (
        <span className="flex items-center gap-1">
          <span>🧠</span>
          <span>Φ {statistics.averagePhi.toFixed(2)}</span>
        </span>
      )}
    </div>
  );
};

// ============================================================================
// Name Editor
// ============================================================================

interface NameEditorProps {
  name: string;
  color: string;
  onSave: (newName: string) => void;
  onCancel: () => void;
}

const NameEditor: React.FC<NameEditorProps> = ({ name, color, onSave, onCancel }) => {
  const [value, setValue] = useState(name);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (value.trim()) {
        onSave(value.trim());
      }
    },
    [value, onSave]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      }
    },
    [onCancel]
  );

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={onCancel}
        className="flex-1 px-2 py-1 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
        style={{ borderColor: color }}
        autoFocus
      />
    </form>
  );
};

// ============================================================================
// Main Component
// ============================================================================

/**
 * NodeGroup component renders a visual group container
 */
function NodeGroupComponent({
  group,
  selected = false,
  onClick,
  onDelete,
  onNameChange,
  onToggleCollapse,
  colorScheme = GroupFunction.CUSTOM,
}: NodeGroupComponentProps) {
  const [editing, setEditing] = useState(false);
  const [hovered, setHovered] = useState(false);

  // Get color scheme
  const colors = GROUP_COLOR_SCHEMES[colorScheme] || GROUP_COLOR_SCHEMES.custom;

  const handleClick = useCallback(() => {
    onClick?.();
  }, [onClick]);

  const handleDelete = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onDelete?.();
    },
    [onDelete]
  );

  const handleToggle = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onToggleCollapse?.();
    },
    [onToggleCollapse]
  );

  const handleNameClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setEditing(true);
    },
    []
  );

  const handleNameSave = useCallback(
    (newName: string) => {
      setEditing(false);
      onNameChange?.(newName);
    },
    [onNameChange]
  );

  const handleNameCancel = useCallback(() => {
    setEditing(false);
  }, []);

  return (
    <div
      className={`
        absolute rounded-lg border-2 transition-all duration-200
        ${selected ? 'ring-2 ring-blue-500 ring-offset-2' : ''}
        ${hovered ? 'shadow-lg' : 'shadow'}
      `}
      style={{
        left: group.position.x,
        top: group.position.y,
        width: group.size.width,
        height: group.collapsed ? 'auto' : group.size.height,
        backgroundColor: colors.background,
        borderColor: group.collapsed ? colors.border : colors.border,
      }}
      onClick={handleClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 border-b"
        style={{
          backgroundColor: group.collapsed ? colors.header : `${colors.header}20`,
          borderColor: colors.border,
        }}
      >
        {/* Collapse toggle */}
        <button
          onClick={handleToggle}
          className="p-1 hover:bg-white/50 rounded transition-colors"
          title={group.collapsed ? 'Expand' : 'Collapse'}
        >
          <CollapseIcon collapsed={group.collapsed} />
        </button>

        {/* Group name */}
        <div className="flex-1 min-w-0">
          {editing ? (
            <NameEditor
              name={group.name}
              color={colors.border}
              onSave={handleNameSave}
              onCancel={handleNameCancel}
            />
          ) : (
            <div
              className="font-semibold text-sm truncate cursor-pointer hover:underline"
              style={{ color: colors.text }}
              onClick={handleNameClick}
              title="Click to rename"
            >
              {group.name}
              <span className="ml-2 opacity-50">
                <EditIcon />
              </span>
            </div>
          )}

          {/* Statistics */}
          <GroupStatistics statistics={group.statistics} collapsed={group.collapsed} />
        </div>

        {/* Actions */}
        {(hovered || selected) && (
          <div className="flex items-center gap-1">
            <button
              onClick={handleDelete}
              className="p-1 hover:bg-red-100 rounded text-red-600 transition-colors"
              title="Delete group"
            >
              <DeleteIcon />
            </button>
          </div>
        )}
      </div>

      {/* Content area (when expanded) */}
      {!group.collapsed && (
        <div className="relative h-full" style={{ padding: '8px' }}>
          {/* Node slots - where child nodes render */}
          <div className="absolute inset-0" style={{ padding: '12px' }}>
            {/* Child nodes will be rendered here by ReactFlow */}
          </div>

          {/* Group boundary indicator */}
          <div
            className="absolute inset-0 pointer-events-none rounded border-2 border-dashed opacity-30"
            style={{ borderColor: colors.border }}
          />
        </div>
      )}

      {/* Node count badge */}
      <div
        className="absolute -top-3 -right-3 px-2 py-1 rounded-full text-xs font-bold text-white shadow"
        style={{ backgroundColor: colors.header }}
      >
        {group.nodes.length}
      </div>
    </div>
  );
}

export default memo(NodeGroupComponent);
export { NodeGroupComponent };
