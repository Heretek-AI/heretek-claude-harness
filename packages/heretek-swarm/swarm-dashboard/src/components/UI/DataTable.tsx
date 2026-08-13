/**
 * DataTable Component
 *
 * A flexible, sortable, and filterable data table component.
 * Supports custom cell rendering, row selection, and pagination.
 */

import React, { useState, useMemo, useCallback } from 'react';

export type SortDirection = 'asc' | 'desc' | null;

export interface Column<T> {
  key: keyof T | string;
  title: string;
  sortable?: boolean;
  filterable?: boolean;
  width?: string;
  align?: 'left' | 'center' | 'right';
  render?: (value: T[keyof T], row: T, index: number) => React.ReactNode;
  formatValue?: (value: T[keyof T]) => string;
}

export interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string | number;
  onRowClick?: (row: T) => void;
  selectedRows?: (string | number)[];
  onSelectionChange?: (selectedKeys: (string | number)[]) => void;
  sortable?: boolean;
  filterable?: boolean;
  filterPlaceholder?: string;
  emptyMessage?: string;
  loading?: boolean;
  className?: string;
  rowClassName?: (row: T, index: number) => string;
  pageSize?: number;
  showPagination?: boolean;
}

export function DataTable<T>({
  data,
  columns,
  keyExtractor,
  onRowClick,
  selectedRows = [],
  onSelectionChange,
  sortable = true,
  filterable = true,
  filterPlaceholder = 'Filter...',
  emptyMessage = 'No data available',
  loading = false,
  className = '',
  rowClassName,
  pageSize = 10,
  showPagination = true,
}: DataTableProps<T>) {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);
  const [filterText, setFilterText] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // Filter and sort data
  const processedData = useMemo(() => {
    let result = [...data];

    // Apply filter
    if (filterText && filterable) {
      const lowerFilter = filterText.toLowerCase();
      result = result.filter((row) =>
        columns.some((col) => {
          const value = row[col.key as keyof T];
          return String(value).toLowerCase().includes(lowerFilter);
        })
      );
    }

    // Apply sort
    if (sortColumn && sortDirection && sortable) {
      const column = columns.find((col) => col.key === sortColumn);
      if (column) {
        result.sort((a, b) => {
          const aVal = a[column.key as keyof T];
          const bVal = b[column.key as keyof T];

          if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
          if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
          return 0;
        });
      }
    }

    return result;
  }, [data, filterText, sortColumn, sortDirection, columns, filterable, sortable]);

  // Pagination
  const totalPages = Math.ceil(processedData.length / pageSize);
  const paginatedData = showPagination
    ? processedData.slice((currentPage - 1) * pageSize, currentPage * pageSize)
    : processedData;

  const handleSort = useCallback((columnKey: string) => {
    if (!sortable) return;

    if (sortColumn === columnKey) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : sortDirection === 'desc' ? null : 'asc');
      if (sortDirection === 'desc') {
        setSortColumn(null);
        setSortDirection(null);
      }
    } else {
      setSortColumn(columnKey);
      setSortDirection('asc');
    }
  }, [sortColumn, sortDirection, sortable]);

  const handleSelectAll = useCallback((checked: boolean) => {
    if (!onSelectionChange) return;
    if (checked) {
      onSelectionChange(paginatedData.map(keyExtractor));
    } else {
      onSelectionChange([]);
    }
  }, [paginatedData, keyExtractor, onSelectionChange]);

  const handleSelectRow = useCallback((key: string | number) => {
    if (!onSelectionChange) return;
    if (selectedRows.includes(key)) {
      onSelectionChange(selectedRows.filter((k) => k !== key));
    } else {
      onSelectionChange([...selectedRows, key]);
    }
  }, [selectedRows, onSelectionChange]);

  const renderSortIcon = (column: Column<T>) => {
    if (!sortable || !column.sortable) return null;

    if (sortColumn !== column.key) {
      return <span className="opacity-0 group-hover:opacity-50">⇅</span>;
    }

    return sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '⇅';
  };

  if (loading) {
    return (
      <div className={`bg-gray-800 rounded-lg border border-gray-700 overflow-hidden ${className}`}>
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500" />
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-gray-800 rounded-lg border border-gray-700 overflow-hidden ${className}`}>
      {/* Filter Bar */}
      {filterable && (
        <div className="p-4 border-b border-gray-700">
          <input
            type="text"
            value={filterText}
            onChange={(e) => {
              setFilterText(e.target.value);
              setCurrentPage(1);
            }}
            placeholder={filterPlaceholder}
            className="w-full max-w-md px-4 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              {onSelectionChange && (
                <th className="px-4 py-3 w-12">
                  <input
                    type="checkbox"
                    checked={paginatedData.length > 0 && paginatedData.every((row) => selectedRows.includes(keyExtractor(row)))}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800"
                  />
                </th>
              )}
              {columns.map((column) => (
                <th
                  key={String(column.key)}
                  style={{ width: column.width }}
                  className={`px-4 py-3 text-${column.align || 'left'} text-gray-400 font-medium ${
                    sortable && column.sortable !== false
                      ? 'cursor-pointer group hover:text-white transition-colors'
                      : ''
                  }`}
                  onClick={() => column.sortable !== false && handleSort(String(column.key))}
                >
                  <div className={`flex items-center gap-2 ${
                    column.align === 'right' ? 'justify-end' : column.align === 'center' ? 'justify-center' : ''
                  }`}>
                    {column.title}
                    <span className="text-gray-500">{renderSortIcon(column)}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {paginatedData.map((row, index) => {
              const rowKey = keyExtractor(row);
              const isSelected = selectedRows.includes(rowKey);

              return (
                <tr
                  key={rowKey}
                  className={`${
                    isSelected ? 'bg-blue-900/20' : 'hover:bg-gray-750'
                  } ${onRowClick ? 'cursor-pointer' : ''} ${
                    rowClassName ? rowClassName(row, index) : ''
                  } transition-colors`}
                  onClick={() => onRowClick?.(row)}
                >
                  {onSelectionChange && (
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleSelectRow(rowKey)}
                        className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800"
                      />
                    </td>
                  )}
                  {columns.map((column) => {
                    const value = row[column.key as keyof T];
                    const content = column.render
                      ? column.render(value as T[keyof T], row, index)
                      : column.formatValue
                      ? column.formatValue(value as T[keyof T])
                      : String(value);

                    return (
                      <td
                        key={String(column.key)}
                        className={`px-4 py-3 text-${column.align || 'left'} text-gray-300`}
                      >
                        {content}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Empty State */}
        {paginatedData.length === 0 && (
          <div className="flex items-center justify-center p-8 text-gray-500">
            {emptyMessage}
          </div>
        )}
      </div>

      {/* Pagination */}
      {showPagination && totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700">
          <span className="text-sm text-gray-400">
            Showing {(currentPage - 1) * pageSize + 1} to {Math.min(currentPage * pageSize, processedData.length)} of {processedData.length} entries
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 rounded-lg border border-gray-600 text-gray-400 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <span className="text-sm text-gray-400">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1 rounded-lg border border-gray-600 text-gray-400 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default DataTable;
